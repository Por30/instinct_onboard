"""Execute the ROS entry as a program with an in-process fake transport."""

import ast
import hashlib
import json
import runpy
import sys
import tempfile
import time
from pathlib import Path
from types import ModuleType, SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from instinct_onboard.carrybox_policy import rotation_wxyz
from instinct_onboard.robot_cfgs import G1_29Dof_CarryBox, G1_29Dof_TorsoBase

scenario = sys.argv[1]
result = dict(dryrun=None, commands=0, motor_off=0)


def module(name, **attrs):
    value = ModuleType(name)
    value.__dict__.update(attrs)
    sys.modules[name] = value


class FakeNode:
    def __init__(self, **kwargs):
        result["dryrun"] = kwargs["dryrun"]
        self.NUM_JOINTS = 29
        assert kwargs["robot_class_name"] == "G1_29Dof_TorsoBase"
        self.sim_joint_names = G1_29Dof_TorsoBase.sim_joint_names
        self.torque_limits = G1_29Dof_TorsoBase.torque_limits.copy()
        self.joint_pos_ = np.zeros(29, np.float32)
        self.joint_vel_ = np.zeros(29, np.float32)
        self.low_state_buffer = SimpleNamespace(imu_state=SimpleNamespace(quaternion=[1, 0, 0, 0], gyroscope=[0, 0, 0]))
        self.torso_imu_buffer = SimpleNamespace(quaternion=[0, 1, 0, 0], gyroscope=[3, 2, 1])
        self.last_sent_target_joint_state = None
        if scenario == "official_stand":
            self.torso_imu_buffer = SimpleNamespace(quaternion=[1, 0, 0, 0], gyroscope=[0, 0, 0])
            self.joint_vel_[:] = np.linspace(-0.2, 0.2, 29)

    def get_logger(self):
        return SimpleNamespace(info=lambda *a, **k: None)

    def start_ros_handlers(self):
        self.low_cmd_publisher = object()
        self.joint_pos_[:] = self.cold_start_agent.joint_target_pos
        for stream in ("state", "joystick"):
            self.watchdog.update(stream, time.monotonic())
        self.refresh_depth()
        if self.stand_agent is not None:
            self._torso_imu_state_callback(self.torso_imu_buffer)

    def _torso_imu_state_callback(self, msg):
        self.torso_imu_buffer = msg

    def _get_joint_pos_obs(self):
        return self.joint_pos_

    def _get_base_ang_vel_obs(self):
        return np.array(self.torso_imu_buffer.gyroscope, dtype=np.float32)

    def _get_projected_gravity_obs(self):
        return (rotation_wxyz(self.torso_imu_buffer.quaternion).T @ [0, 0, -1]).astype(np.float32)

    def create_timer(self, period, callback):
        return object()

    def send_target_joint_state(self, target):
        assert self.watchdog.fault is None
        result["commands"] += 1
        self.last_sent_target_joint_state = target.copy()
        return True

    def _turn_off_motors(self):
        result["motor_off"] += 1

    def destroy_node(self):
        pass


class FakeCamera:
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.depth_resolution = kwargs["depth_resolution"]
        self.depth_fps = kwargs["depth_fps"]
        self._depth_header = SimpleNamespace(writer_status=0, frame_counter=1, timestamp=time.time())
        self._depth_buffer = np.full((27, 48), 3.0, np.float32)

    def prevent_camera_process_dead(self):
        pass


class FakeJoystick:
    def __init__(self, node, safety_shutdown_callback):
        self._ros_node = node
        self.data = SimpleNamespace(R1=False, L1=False, B=False)


class FakeStand:
    def __init__(self, logdir, ros_node):
        np.testing.assert_array_equal(ros_node.base_velocity_cmd, np.zeros(3))
        assert ros_node.sim_joint_names == G1_29Dof_TorsoBase.sim_joint_names
        self.node = ros_node
        self.history_resets = 0
        self.obs_history_buffers = {"test": SimpleNamespace(reset=self.clear_history)}

    def clear_history(self):
        self.history_resets += 1

    def reset(self):
        pass

    def step(self):
        assert self.node.torso_imu_buffer.gyroscope == [3, 2, 1]
        return self.node.pose_stand_agent.step()


def transition_checks(node):
    def tick(r1=False, l1=False):
        node.joystick.data.R1, node.joystick.data.L1 = r1, l1
        node._depth_header.timestamp = time.time()
        for stream in node.watchdog.limits:
            node.watchdog.update(stream, time.monotonic())
        node.tick()

    node.joint_pos_[:] = node.cold_start_agent.joint_target_pos + 0.5
    tick()
    assert node.phase == "cold_start" and result["commands"] == 0
    tick(l1=True)
    assert node.phase == "cold_start"
    np.testing.assert_allclose(np.abs(node.last_sent_target_joint_state.position - node.joint_pos_), 0.2, atol=1e-6)
    np.testing.assert_allclose(node.last_sent_target_joint_state.kp, node.pose_stand_agent.p_gains * 2)
    tick(r1=True)
    assert node.phase == "cold_start", "R1 cannot skip measured pose convergence"
    node.joint_pos_[:] = node.cold_start_agent.joint_target_pos
    tick(r1=True)
    assert node.phase == "cold_start", "Held buttons must not carry into the next mode"
    tick()
    tick(r1=True)
    assert node.phase == "stand"
    tick(r1=True, l1=True)
    assert node.phase == "stand", "Both buttons must not enable the task"
    tick()
    tick(l1=True)
    assert node.phase == "carrybox"
    np.testing.assert_array_equal(node.agent.policy.previous_action, 0)
    tick()
    assert np.any(node.agent.policy.previous_action != 0)
    old_step = node.carrybox_step
    node.carrybox_step = lambda: (_ for _ in ()).throw(AssertionError("R1 ran the old carrybox policy"))
    tick(r1=True, l1=True)
    node.carrybox_step = old_step
    assert node.phase == "stand", "R1 must return from the task"
    tick(l1=True)
    assert node.phase == "stand", "Held L1 must not bounce back into the task"
    tick()
    tick(l1=True)
    assert node.phase == "carrybox"
    np.testing.assert_array_equal(node.agent.policy.previous_action, 0)
    if isinstance(node.stand_agent, FakeStand):
        assert node.stand_agent.history_resets == 3
    elif node.stand_agent is not None:
        agent = node.stand_agent
        assert agent.ort_sessions["depth_encoder"].get_inputs()[0].shape == [1, 8, 18, 32]
        assert agent.ort_sessions["depth_encoder"].get_outputs()[0].shape == [1, 128]
        assert agent.ort_sessions["actor"].get_inputs()[0].shape == [1, 896]
        assert agent.ort_sessions["actor"].get_outputs()[0].shape == [1, 29]
        assert agent.policy_action_dim == 29
        np.testing.assert_array_equal(node.joint_vel_, np.linspace(-0.2, 0.2, 29, dtype=np.float32))
        np.testing.assert_array_equal(agent._get_depth_image_downsample_obs(), np.zeros((8, 18, 32)))
        node.switch_phase("stand")
        assert all(history._num_pushes == 0 for history in agent.obs_history_buffers.values())
        original_session = agent.ort_sessions["actor"]

        def failed_inference(*args):
            raise RuntimeError("Official stand failure injection")

        agent.ort_sessions["actor"] = SimpleNamespace(get_inputs=original_session.get_inputs, run=failed_inference)
        q, dq = node.joint_pos_.copy(), node.joint_vel_.copy()
        commands = result["commands"]
        try:
            tick()
        except RuntimeError as exc:
            assert "Official stand failure" in str(exc)
        else:
            raise AssertionError("Stand inference error did not stop the entry")
        np.testing.assert_array_equal(node.joint_pos_, q)
        np.testing.assert_array_equal(node.joint_vel_, dq)
        assert node.phase == "stopped" and result["commands"] == commands
        result["official_stand"] = dict(actor_input=896, depth_shape=[8, 18, 32], action_dim=29)
    result["transitions"] = True


def mapping_checks(node):
    canonical = np.linspace(-0.3, 0.3, 29, dtype=np.float32)
    names = G1_29Dof_CarryBox.sim_joint_names
    permutation = [names.index(name) for name in node.sim_joint_names]
    node.joint_pos_[:] = canonical[permutation] * G1_29Dof_TorsoBase.joint_signs
    node.joint_vel_[:] = 2 * node.joint_pos_
    original = node.agent.act
    targets = []

    def checked(q, dq, gyro, quat, *args):
        np.testing.assert_allclose(q, canonical)
        np.testing.assert_allclose(dq, 2 * canonical)
        np.testing.assert_array_equal(gyro, [0, 0, 0])
        np.testing.assert_array_equal(quat, [1, 0, 0, 0])
        target = original(q, dq, gyro, quat, *args)
        targets.append(target)
        return target

    node.agent.act = checked
    node.policy_time = time.monotonic()
    converted = node.carrybox_step()
    for field in ("position", "velocity", "effort", "kp", "kd"):
        source = getattr(targets[0], field)
        for i, name in enumerate(node.sim_joint_names):
            sign = G1_29Dof_TorsoBase.joint_signs[i] if field in ("position", "velocity", "effort") else 1
            assert getattr(converted, field)[i] == source[names.index(name)] * sign
    np.testing.assert_array_equal(
        node.torque_limits, np.minimum(G1_29Dof_TorsoBase.torque_limits, G1_29Dof_CarryBox.torque_limits[permutation])
    )
    result["mapping"] = True


def spin(node):
    if scenario in ("transitions", "stand", "official_stand"):
        if scenario == "official_stand":
            np.testing.assert_array_equal(node.joint_vel_, np.linspace(-0.2, 0.2, 29, dtype=np.float32))
        transition_checks(node)
        return
    if scenario == "mapping":
        mapping_checks(node)
        return
    node.phase = "carrybox"
    node.agent.reset()
    node._depth_header.timestamp = time.time()
    for stream in node.watchdog.limits:
        node.watchdog.update(stream, time.monotonic())
    if scenario in ("state", "joystick", "torso"):
        node.watchdog.update(scenario, time.monotonic() - 1)
    elif scenario == "depth":
        node._depth_header.timestamp = time.time() - 1
    elif scenario == "estop":
        try:
            node.joystick._handle_safety_shutdown()
        except SystemExit:
            try:
                node.tick()
            except RuntimeError:
                return
            raise AssertionError("E-stop did not latch")
    elif scenario == "inference":

        def failed(*args):
            raise ValueError("Injected inference error")

        node.agent.act = failed
    elif scenario == "deadline":
        original = node.carrybox_step

        def delayed():
            value = original()
            time.sleep(0.03)
            return value

        node.carrybox_step = delayed
    elif scenario == "illegal":
        node.phase = "invalid"
    elif scenario == "stand_fail":
        node.phase = "stand"
        node.stand_agent.step = lambda: (None, -1)
    try:
        node.tick()
    except (RuntimeError, ValueError):
        if scenario == "dryrun":
            raise
    else:
        assert scenario == "dryrun", "Fault injection did not stop the entry"


module("rclpy", init=lambda: None, shutdown=lambda: None, spin=spin)
module("instinct_onboard.joystick", UnitreeJoyStick=FakeJoystick)
module("instinct_onboard.ros_nodes.camera_base", CameraProcessSpawner=FakeCamera, _acquire_barrier=lambda: None)
module("instinct_onboard.ros_nodes.realsense", RealsenseCamera=object)
module("instinct_onboard.ros_nodes.unitree", UnitreeNode=FakeNode)
module("instinct_onboard.ros_nodes.base", RealNode=FakeNode)
if scenario == "official_stand":
    bundle = Path("models/stand_onboard")
    provenance = json.loads((bundle / "provenance.json").read_text())
    for name, record in provenance["files"].items():
        assert hashlib.sha256((bundle / name).read_bytes()).hexdigest() == record["sha256"]
    source = ast.parse(Path("instinct_onboard/utils.py").read_text())
    buffer_class = next(x for x in source.body if isinstance(x, ast.ClassDef) and x.name == "CircularBuffer")
    scope = {"np": np}
    exec(compile(ast.Module(body=[buffer_class], type_ignores=[]), "instinct_onboard/utils.py", "exec"), scope)
    module("instinct_onboard.utils", CircularBuffer=scope["CircularBuffer"])
    module("cv2")
    module("ros2_numpy")
    module("geometry_msgs.msg", TransformStamped=object)
    module("sensor_msgs.msg", CameraInfo=object, Image=object, PointCloud2=object, PointField=object)
    module("tf2_ros", StaticTransformBroadcaster=object)
else:
    module("instinct_onboard.utils", CircularBuffer=object)
    module("instinct_onboard.agents.parkour_agent", ParkourStandAgent=FakeStand)
with tempfile.TemporaryDirectory(dir=".cache") as standdir:
    sys.argv = ["scripts/g1_carrybox.py", "--bundle", "models/carrybox_wall19"]
    if scenario == "official_stand":
        sys.argv += ["--standdir", "models/stand_onboard"]
    elif scenario in ("stand", "torso", "stand_fail"):
        for name in ("params/env.yaml", "params/agent.yaml", "exported/actor.onnx", "exported/0-depth_encoder.onnx"):
            path = Path(standdir) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        sys.argv += ["--standdir", standdir]
    else:
        sys.argv += ["--pose-stand"]
    runpy.run_path("scripts/g1_carrybox.py", run_name="__main__")
print(json.dumps(result))
