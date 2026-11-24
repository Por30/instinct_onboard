"""Contract, numerical parity, simulation and mocked ROS entry checks."""

import ast
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import mujoco
import numpy as np
import onnxruntime as ort
import torch

from instinct_onboard.agents.carrybox_agent import CarryBoxAgent
from instinct_onboard.carrybox_export import (
    DEFAULT_CHECKPOINT,
    DEFAULT_SOURCE,
    CarryBoxActor,
)
from instinct_onboard.carrybox_policy import (
    CarryBoxPolicy,
    CarryBoxWatchdog,
    depth_metres,
    resample_depth,
    rotation_wxyz,
)
from instinct_onboard.robot_cfgs import G1_29Dof_CarryBox
from instinct_onboard.simulation.carrybox import (
    CarryBoxSim,
    DepthCamera,
    inertia_in_link,
)

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "models/carrybox_wall19"


class PolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        cls.actor = CarryBoxActor(DEFAULT_SOURCE).eval()
        state = torch.load(DEFAULT_CHECKPOINT, map_location="cpu", weights_only=False)["model_state_dict"]
        cls.actor.load_state_dict({k: v for k, v in state.items() if not (k.startswith("critic.") or k == "log_std")})
        cls.runtime = CarryBoxPolicy(BUNDLE)
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        cls.full = ort.InferenceSession(
            str(BUNDLE / "exported/policy.onnx"), options, providers=["CPUExecutionProvider"]
        )
        cls.reference = ort.InferenceSession(
            "/home/cao/unitree_rl_lab_carrybox/docs/sim2sim_wall19/export/policy.onnx",
            options,
            providers=["CPUExecutionProvider"],
        )

    def setUp(self):
        self.runtime.reset()

    def test_training_forward_and_independent_onnx_batch_parity(self):
        # Execute the actual training feature function, not the exporter wrapper.
        path = DEFAULT_SOURCE / "rsl_rl_extensions/carrybox_wall14.py"
        definition = next(
            n
            for n in ast.parse(path.read_text()).body
            if isinstance(n, ast.ClassDef) and n.name == "CarryBoxWall14ActorCritic"
        )
        functions = [
            n
            for n in definition.body
            if isinstance(n, ast.FunctionDef) and n.name in ("predict_geometry_grasp", "_features")
        ]
        namespace = {"torch": torch}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), namespace)
        reference_self = SimpleNamespace(
            perception_encoder=self.actor.perception_encoder,
            pose_head=self.actor.pose_head,
            grasp_head=self.actor.grasp_head,
        )
        reference_self.predict_geometry_grasp = lambda obs: namespace["predict_geometry_grasp"](reference_self, obs)
        rng = np.random.default_rng(18)
        for batch in (1, 3):
            p = rng.normal(0, 0.5, (batch, 558)).astype(np.float32)
            d = rng.uniform(0.1, 3, (batch, 4, 27, 48)).astype(np.float32)
            with torch.inference_mode():
                obs = dict(proprio=torch.from_numpy(p), perception=torch.from_numpy(d))
                expected = self.actor.actor(namespace["_features"](reference_self, obs)).numpy()
            actual = self.full.run(None, {"proprio": p, "depth": d})[0]
            independent = self.reference.run(None, {"proprio": p, "depth": d})[0]
            np.testing.assert_allclose(actual, expected, atol=2e-5, rtol=1e-5)
            np.testing.assert_allclose(actual, independent, atol=2e-5, rtol=1e-5)
            for row in range(batch):
                np.testing.assert_allclose(
                    self.runtime.infer(p[row : row + 1], d[row : row + 1]),
                    np.clip(expected[row], -100, 100),
                    atol=2e-5,
                    rtol=1e-5,
                )

    def test_latest_proprio_and_normal_fallback(self):
        import copy

        grasp = copy.deepcopy(self.actor.grasp_head)
        latent, geometry, proprio = torch.randn(2, 128), torch.randn(2, 12), torch.randn(2, 558)
        with torch.inference_mode():
            original = grasp(latent, geometry, proprio)
            proprio[:, :-93] += 100
            torch.testing.assert_close(grasp(latent, geometry, proprio), original, atol=0, rtol=0)
            for parameter in grasp.parameters():
                parameter.zero_()
            actual = grasp(latent, geometry, proprio)
        np.testing.assert_array_equal(actual[:, 6:], [[-1, 0, 0, 1, 0, 0]] * 2)
        np.testing.assert_allclose(actual[:, :6], geometry[:, :3].repeat(1, 2), atol=0, rtol=0)

    def test_whole_frame_history_reset_and_raw_previous_action(self):
        cfg = self.runtime.config
        agent = CarryBoxAgent(BUNDLE, SimpleNamespace(NUM_JOINTS=29, sim_joint_names=cfg["joint_names"]))
        q = agent.default_joint_pos.copy()
        for tick in range(8):
            frame = np.full((27, 48), 0.5 + tick * 0.1, np.float32)
            previous = agent.policy.previous_action.copy()
            target = agent.act(q, np.zeros(29), np.array([tick, 0, 0]), [1, 0, 0, 0], frame, tick * 0.02, tick * 0.02)
            np.testing.assert_array_equal(agent.policy.proprio_history[-1, -29:], previous)
            np.testing.assert_allclose(target.position, q + 0.25 * agent.policy.previous_action)
            target.position[:] = q  # A transport limit must not change the raw previous action.
        np.testing.assert_allclose(agent.policy.proprio_history[:, 0], np.arange(2, 8) * 0.25)
        np.testing.assert_allclose(agent.policy.depth_history[:, 0, 0], np.arange(4, 8) * 0.1 + 0.5)
        agent.reset()
        p, d = agent.policy.observe(q, np.zeros(29), np.zeros(3), [1, 0, 0, 0], frame, 0, 0)
        np.testing.assert_array_equal(p.reshape(6, 93)[:, -29:], 0)
        np.testing.assert_array_equal(p.reshape(6, 93), np.repeat(p.reshape(6, 93)[:1], 6, 0))
        np.testing.assert_array_equal(d[0], np.repeat(frame[None], 4, 0))

    def test_depth_metres_invalid_and_projection(self):
        frame = np.full((27, 48), 1.5, np.float32)
        frame[0, :5] = [0, np.nan, np.inf, 0.05, 10]
        np.testing.assert_allclose(depth_metres(frame)[0, :6], [3, 3, 3, 0.1, 3, 1.5])
        cfg = self.runtime.config["camera"]
        sampled = resample_depth(frame, [cfg["fx"], cfg["fy"], 23.5, 13], cfg)
        np.testing.assert_array_equal(sampled, depth_metres(frame))
        with self.assertRaises(ValueError):
            depth_metres(np.zeros((27, 48)))
        with self.assertRaises(ValueError):
            depth_metres(frame.T)
        with self.assertRaises(ValueError):
            resample_depth(frame, [100, 100, 24, 13.5], cfg)

    def test_bad_observations_and_hash_rejected(self):
        args = (self.runtime.default_joint_pos, np.zeros(29), np.zeros(3), [1, 0, 0, 0], np.ones((27, 48)))
        for now, capture in ((1, 0.8), (1, 1.1), (np.nan, 0)):
            with self.assertRaises(ValueError):
                self.runtime.observe(*args, now, capture)
        with self.assertRaises(ValueError):
            self.runtime.observe(*args[:3], [0, 0, 0, 0], args[4], 0, 0)
        with self.assertRaises(ValueError):
            self.runtime.infer(np.zeros((1, 557), np.float32), np.ones((1, 4, 27, 48), np.float32))
        with tempfile.TemporaryDirectory(dir=ROOT / ".cache") as tmp:
            path = Path(tmp)
            cfg = dict(self.runtime.config)
            cfg["onnx_sha256"] = dict(cfg["onnx_sha256"], depth_encoder="0" * 64)
            (path / "manifest.json").write_text(json.dumps(cfg))
            (path / "exported").symlink_to(BUNDLE / "exported", target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                CarryBoxPolicy(path)

    def test_hardware_mapping_and_pelvis_observation(self):
        cfg, robot = self.runtime.config, G1_29Dof_CarryBox
        self.assertEqual(cfg["joint_names"], robot.sim_joint_names)
        self.assertEqual([robot.real_joint_names[i] for i in robot.joint_map], robot.sim_joint_names)
        np.testing.assert_array_equal(robot.joint_signs, 1)
        np.testing.assert_allclose(robot.torque_limits, cfg["effort"])
        np.testing.assert_allclose(robot.joint_limits_low, cfg["joint_lower"])
        q = self.runtime.default_joint_pos.copy()
        q[robot.sim_joint_names.index("waist_pitch_joint")] = 0.5
        proprio, _ = self.runtime.observe(q, np.zeros(29), [1, 2, 3], [1, 0, 0, 0], np.ones((27, 48)), 0, 0)
        np.testing.assert_allclose(proprio[0, -93:-87], [0.25, 0.5, 0.75, 0, 0, -1])


class SimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sim = CarryBoxSim(BUNDLE)

    def setUp(self):
        self.sim.reset()

    def test_captured_inertia_and_motor_limits(self):
        sim = self.sim
        self.assertEqual(len(sim.robot_bodies), 44)
        self.assertAlmostEqual(sim.model.body_mass[sim.robot_bodies].sum(), 42.341142404591665, places=8)
        for name, body in sim.profile["bodies"].items():
            index = sim.model.body(name).id
            matrix = rotation_wxyz(sim.model.body_iquat[index])
            np.testing.assert_allclose(
                matrix @ np.diag(sim.model.body_inertia[index]) @ matrix.T, inertia_in_link(body), atol=1e-9, rtol=1e-6
            )
            np.testing.assert_allclose(sim.model.body_ipos[index], body["com_xyz"], atol=1e-12)
        np.testing.assert_allclose(sim.model.actuator_ctrlrange[:, 1], sim.cfg["effort"])
        for _ in range(10):
            result = sim.step()
        self.assertLessEqual(result["max_torque_limit_ratio"], 1 + 1e-6)
        sim.stop()
        with self.assertRaisesRegex(RuntimeError, "stopped"):
            sim.step()
        np.testing.assert_array_equal(sim.data.ctrl, 0)

    def test_near_plane_exit_surface_and_optical_depth(self):
        model = mujoco.MjModel.from_xml_string(
            '<mujoco><worldbody><body name="torso_link"/>'
            '<geom type="sphere" size=".1" pos=".15 0 0" group="0"/></worldbody></mujoco>'
        )
        data = mujoco.MjData(model)
        mujoco.mj_forward(model, data)
        camera = DepthCamera(model, dict(position=[0, 0, 0], quaternion_wxyz=[1, 0, 0, 0], fx=24, fy=24))
        image = camera.render(data).ravel()
        for index in (13 * 48 + 23, 13 * 48 + 28):
            ray = camera.rays[index]
            projection = 0.15 * ray[0]
            distance = projection + np.sqrt(projection**2 - (0.15**2 - 0.1**2))
            self.assertAlmostEqual(image[index], distance * ray[0], places=6)
            self.assertGreater(image[index], 0.1)


class SafetyTests(unittest.TestCase):
    def test_watchdog_latches_every_stream_and_startup(self):
        for stream, limit in CarryBoxWatchdog.limits.items():
            watchdog = CarryBoxWatchdog(0)
            watchdog.armed = True
            watchdog.times = {name: 1 for name in watchdog.limits}
            watchdog.times[stream] = 1 - limit - 0.01
            with self.assertRaisesRegex(RuntimeError, stream):
                watchdog.check(1)
            watchdog.update(stream, 1)
            with self.assertRaises(RuntimeError):
                watchdog.check(1)
        with self.assertRaisesRegex(RuntimeError, "Startup"):
            CarryBoxWatchdog(0).check(11)

    def test_ros_entry_with_stub_transport(self):
        for scenario in (
            "dryrun",
            "estop",
            "state",
            "joystick",
            "depth",
            "torso",
            "inference",
            "deadline",
            "illegal",
            "stand_fail",
        ):
            completed = subprocess.run(
                [sys.executable, "tests/ros_carrybox_harness.py", scenario],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            result = json.loads(completed.stdout.strip().splitlines()[-1])
            self.assertTrue(result["dryrun"])
            self.assertGreaterEqual(result["motor_off"], 1)
            self.assertEqual(result["commands"], 1 if scenario == "dryrun" else 0)

    def test_original_modes_and_joint_frame_conversion(self):
        for scenario in ("transitions", "stand", "mapping", "official_stand"):
            completed = subprocess.run(
                [sys.executable, "tests/ros_carrybox_harness.py", scenario],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=20,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            result = json.loads(completed.stdout.strip().splitlines()[-1])
            self.assertTrue(result["mapping" if scenario == "mapping" else "transitions"])
            self.assertTrue(result["dryrun"])
            self.assertGreaterEqual(result["motor_off"], 1)

    def test_offline_entry_and_conflicting_flags(self):
        command = [sys.executable, "scripts/g1_carrybox.py", "--offline", "--steps", "3"]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(result.stdout)["motor_messages"], 0)
        result = subprocess.run(command + ["--nodryrun"], cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        for flags in (
            ["--pose-stand", "--nodryrun"],
            [],
            ["--standdir", "/missing/stand"],
            ["--offline", "--startup_step_size", "nan"],
        ):
            result = subprocess.run(
                [sys.executable, "scripts/g1_carrybox.py", *flags], cwd=ROOT, capture_output=True, text=True
            )
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
