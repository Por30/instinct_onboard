"""Mode transitions, official stand parity, frame conversion and stop boundaries."""

import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import mujoco
import numpy as np

from instinct_onboard.robot_cfgs import G1_29Dof_TorsoBase
from instinct_onboard.simulation.carrybox import CarryBoxSim
from instinct_onboard.target_joint_state import TargetJointState
from scripts.g1_carrybox_s2s import ModeController

ROOT = Path(__file__).resolve().parents[1]


class ModeTests(unittest.TestCase):
    def setUp(self):
        self.sim = CarryBoxSim(ROOT / "models/carrybox_wall19")
        self.controller = ModeController(self.sim, ROOT / "models/stand_onboard")

    def test_transitions_support_history_and_stop(self):
        sim, control = self.sim, self.controller
        control.request("stand")
        self.assertEqual(control.phase, "cold_start", "S cannot skip the first cold-start command")
        control.request("carrybox")
        self.assertEqual(control.phase, "cold_start")
        sim.data.qpos[sim.qadr[0]] += 0.4
        control.request("stand")
        self.assertEqual(control.phase, "cold_start")
        control.step()
        self.assertLessEqual(abs(control.last_target.position[0] - (sim.agent.default_joint_pos[0] + 0.4)), 0.200001)
        np.testing.assert_allclose(control.last_target.kp, sim.agent.p_gains * 2)
        sim.data.qpos[sim.qadr] = sim.agent.default_joint_pos
        mujoco.mj_forward(sim.model, sim.data)
        record = control.step()
        self.assertEqual(control.phase, "cold_start", "An earlier S must not become a delayed transition")
        self.assertTrue(record["simulated_support"])
        np.testing.assert_array_equal(sim.data.qpos[:7], sim.cfg["default_root_pose"])
        control.request("stand")
        self.assertEqual(control.phase, "stand")
        record = control.step()
        self.assertFalse(record["simulated_support"])
        self.assertFalse(np.array_equal(sim.data.qpos[:7], sim.cfg["default_root_pose"]))
        self.assertIsNone(sim.agent.policy.depth_history)
        control.request("carrybox")
        self.assertIsNone(sim.agent.policy.depth_history)
        control.step()
        self.assertIsNotNone(sim.agent.policy.depth_history)
        control.request("stand")
        self.assertEqual(control.stand.history, {})
        with patch.object(sim.agent, "act", side_effect=AssertionError("Old carrybox policy ran on return to stand")):
            control.step()
        for history in control.stand.history.values():
            np.testing.assert_array_equal(history, np.repeat(history[-1:], 8, axis=0))
        sim.stop()
        control.request("carrybox")
        control.request("stand")
        self.assertEqual(sim.stop_reason, "user_stop")
        np.testing.assert_array_equal(sim.data.ctrl, 0)
        np.testing.assert_array_equal(sim.data.xfrc_applied, 0)
        control.reset()
        self.assertEqual(control.phase, "cold_start")
        self.assertIsNone(sim.stop_reason)
        self.assertIsNone(control.last_target)

    def test_named_mapping_torso_imu_and_last_target(self):
        sim, control = self.sim, self.controller
        sim.data.qpos[sim.qadr] = np.linspace(-0.1, 0.1, 29)
        sim.data.qvel[sim.vadr] = np.linspace(-0.2, 0.3, 29)
        sim.data.qvel[3:6] = [0.1, 0.2, -0.3]
        mujoco.mj_forward(sim.model, sim.data)
        fields = ("position", "velocity", "effort", "kp", "kd")
        control.last_target = TargetJointState(
            *(np.arange(29, dtype=np.float32) * (index + 1) / 100 for index in range(5))
        )
        previous = control.last_target.copy()
        expected_torso = TargetJointState(*(np.arange(29, dtype=np.float32) * (index + 2) / 100 for index in range(5)))
        world_velocity = np.empty(6)
        mujoco.mj_objectVelocity(sim.model, sim.data, mujoco.mjtObj.mjOBJ_BODY, control.torso, world_velocity, 0)
        rotation = sim.data.xmat[control.torso].reshape(3, 3)
        q0, dq0 = sim.data.qpos.copy(), sim.data.qvel.copy()

        def check(q, dq, gyro, gravity, last):
            for j, name in enumerate(G1_29Dof_TorsoBase.sim_joint_names):
                i = sim.sim_joint_names.index(name)
                sign = G1_29Dof_TorsoBase.joint_signs[j]
                self.assertAlmostEqual(q[j], q0[sim.qadr[i]] * sign, places=6)
                self.assertAlmostEqual(dq[j], dq0[sim.vadr[i]] * sign, places=6)
                for field in fields:
                    self.assertAlmostEqual(
                        getattr(last, field)[j],
                        getattr(previous, field)[i] * (sign if field in fields[:3] else 1),
                        places=6,
                    )
            np.testing.assert_allclose(gyro, rotation.T @ world_velocity[:3], atol=1e-12)
            np.testing.assert_allclose(gravity, rotation.T @ [0, 0, -1], atol=1e-12)
            return expected_torso

        with patch.object(control.stand, "act", side_effect=check):
            target = control.stand_target()
        for i, name in enumerate(sim.sim_joint_names):
            j = G1_29Dof_TorsoBase.sim_joint_names.index(name)
            for field in fields:
                sign = G1_29Dof_TorsoBase.joint_signs[j] if field in fields[:3] else 1
                self.assertAlmostEqual(getattr(target, field)[i], getattr(expected_torso, field)[j] * sign, places=6)
        np.testing.assert_array_equal(sim.data.qpos, q0)
        np.testing.assert_array_equal(sim.data.qvel, dq0)

    def test_inference_fault_stops(self):
        control, sim = self.controller, self.sim
        control.step()
        control.request("stand")
        with patch.object(control.stand, "act", side_effect=ValueError("injected stand fault")):
            with self.assertRaisesRegex(ValueError, "injected stand fault"):
                control.step()
        self.assertEqual(sim.stop_reason, "runtime_fault")
        np.testing.assert_array_equal(sim.data.ctrl, 0)
        np.testing.assert_array_equal(sim.data.xfrc_applied, 0)

    def test_official_agent_numerical_parity(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tests/stand_parity_harness.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=45,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["actor_input_match"])


if __name__ == "__main__":
    unittest.main()
