"""Compare the simulation stand runtime against the real ParkourStandAgent."""

import ast
import contextlib
import io
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from instinct_onboard.carrybox_policy import rotation_wxyz
from instinct_onboard.robot_cfgs import G1_29Dof_TorsoBase
from instinct_onboard.simulation.stand import StandPolicy
from instinct_onboard.target_joint_state import TargetJointState


def module(name, **values):
    result = ModuleType(name)
    result.__dict__.update(values)
    sys.modules[name] = result


class State:
    NUM_JOINTS = 29
    sim_joint_names = G1_29Dof_TorsoBase.sim_joint_names
    depth_resolution = (48, 27)
    depth_fps = 60
    base_velocity_cmd = np.zeros(3, np.float32)
    last_sent_target_joint_state = None

    def get_logger(self):
        return SimpleNamespace(info=lambda *a, **k: None)

    def _get_base_ang_vel_obs(self):
        return self.gyro.copy()

    def _get_projected_gravity_obs(self):
        return self.gravity.copy()


source = ast.parse((ROOT / "instinct_onboard/utils.py").read_text())
node = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == "CircularBuffer")
scope = {"np": np}
exec(compile(ast.Module(body=[node], type_ignores=[]), "instinct_onboard/utils.py", "exec"), scope)
module("instinct_onboard.utils", CircularBuffer=scope["CircularBuffer"])
module("instinct_onboard.ros_nodes.base", RealNode=State)
module("cv2")
module("ros2_numpy")
module("geometry_msgs.msg", TransformStamped=object)
module("sensor_msgs.msg", CameraInfo=object, Image=object, PointCloud2=object, PointField=object)
module("tf2_ros", StaticTransformBroadcaster=object)

from instinct_onboard.agents.parkour_agent import ParkourStandAgent


class ReferenceStand(ParkourStandAgent):
    def _get_joint_vel_rel_obs(self):
        return super()._get_joint_vel_rel_obs().copy()


state = State()
with contextlib.redirect_stdout(io.StringIO()):
    reference = ReferenceStand(str(ROOT / "models/stand_onboard"), state)
runtime = StandPolicy(ROOT / "models/stand_onboard")
actor = reference.ort_sessions["actor"]
captured = []


def infer(outputs, inputs):
    captured.append(next(iter(inputs.values())).copy())
    return actor.run(outputs, inputs)


reference.ort_sessions["actor"] = SimpleNamespace(get_inputs=actor.get_inputs, run=infer)
rng = np.random.default_rng(20261125)
max_error = 0.0
for index in range(15):
    if index in (0, 8):
        runtime.reset()
        for history in reference.obs_history_buffers.values():
            history.reset()
        state.last_sent_target_joint_state = TargetJointState(
            rng.normal(0, 0.3, 29).astype(np.float32),
            np.zeros(29, np.float32),
            np.zeros(29, np.float32),
            np.ones(29, np.float32) * 40,
            np.ones(29, np.float32) * 2,
        )
    state.joint_pos_ = runtime.default_joint_pos + rng.normal(0, 0.2, 29).astype(np.float32)
    state.joint_vel_ = rng.normal(0, 0.3, 29).astype(np.float32)
    state.gyro = rng.normal(0, 0.2, 3).astype(np.float32)
    quat = np.array([1.0, 0.1, -0.08, 0.2])
    quat /= np.linalg.norm(quat)
    state.gravity = (rotation_wxyz(quat).T @ [0, 0, -1]).astype(np.float32)
    q, dq = state.joint_pos_.copy(), state.joint_vel_.copy()
    expected, _ = reference.step()
    actual = runtime.act(q, dq, state.gyro, state.gravity, state.last_sent_target_joint_state)
    np.testing.assert_allclose(runtime.actor_input, captured[-1], atol=1e-6, rtol=0)
    for field in ("position", "velocity", "effort", "kp", "kd"):
        np.testing.assert_allclose(getattr(actual, field), getattr(expected, field), atol=1e-5, rtol=1e-5)
        max_error = max(max_error, float(np.max(abs(getattr(actual, field) - getattr(expected, field)))))
    np.testing.assert_array_equal(q, state.joint_pos_)
    np.testing.assert_array_equal(dq, state.joint_vel_)
    state.last_sent_target_joint_state = expected
print(json.dumps(dict(steps=15, actor_input_match=True, max_target_error=max_error)))
