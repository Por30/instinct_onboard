"""Physics checks for interactive primitive objects and mouse perturbations."""

import unittest
from pathlib import Path

import mujoco
import numpy as np

from instinct_onboard.simulation.carrybox import OBJECT_SHAPES, CarryBoxSim

BUNDLE = Path(__file__).resolve().parents[1] / "models/carrybox_wall19"


class InteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sim = CarryBoxSim(BUNDLE)

    def test_shape_depth_contact_and_history(self):
        sim = self.sim
        images = []
        heights = [0.125, 0.15, 0.15, 0.125, 0.175, 0.125]
        sideways = [0.15, 0.15, 0.15, 0.15, 0.1, 0.18]
        for shape, height, side in zip(OBJECT_SHAPES, heights, sideways):
            with self.subTest(shape=shape):
                sim.set_object_shape(shape)
                self.assertIsNone(sim.agent.policy.depth_history)
                self.assertIsNone(sim.agent.policy.last_time)
                self.assertEqual(sim.data.time, 0)
                np.testing.assert_array_equal(sim.data.xfrc_applied, 0)
                self.assertAlmostEqual(sim.data.qpos[sim.bq + 2], height + 0.005)
                self.assertAlmostEqual(sim.object_half_height(np.array([1, 0, 0])), side)
                self.assertAlmostEqual(sim.model.body_mass[sim.box], 1.125)
                self.assertTrue((sim.model.body_inertia[sim.box] > 0).all())
                self.assertAlmostEqual(sim.metrics()["box_bottom_m"], 0.005)
                depth = sim.camera.render(sim.data)
                self.assertGreater((sim.camera.hits == sim.object_geom).sum(), 0)
                images.append(depth.copy())
                sim.step()
                np.testing.assert_array_equal(sim.agent.policy.depth_history, np.repeat(depth[None], 4, axis=0))
                sim.data.qpos[sim.bq : sim.bq + 3] = [3, 0, height - 0.001]
                sim.data.qvel[:] = 0
                mujoco.mj_forward(sim.model, sim.data)
                floor = sim.model.geom("floor").id
                contacts = [c for c in sim.data.contact if {c.geom1, c.geom2} == {sim.object_geom, floor}]
                self.assertTrue(contacts, "Changed collision shape did not contact the floor")
                self.assertAlmostEqual(min(c.dist for c in contacts), -0.001, places=5)
                for _ in range(100):
                    sim.data.ctrl[:] = 0
                    sim.data.xfrc_applied[:] = 0
                    mujoco.mj_step(sim.model, sim.data)
                self.assertTrue(np.isfinite(sim.data.qpos).all())
                self.assertGreater(sim.data.qpos[sim.bq + 2], height - 0.005)
        self.assertEqual(len({d.tobytes() for d in images}), 6)

    def test_return_to_cuboid_preserves_baseline_trajectory(self):
        sim = CarryBoxSim(BUNDLE)
        expected = []
        for _ in range(12):
            sim.step()
            expected.append(np.concatenate((sim.data.qpos, sim.data.qvel)).copy())
        for shape in reversed(OBJECT_SHAPES):
            sim.set_object_shape(shape)
        for state in expected:
            sim.step()
            np.testing.assert_allclose(np.concatenate((sim.data.qpos, sim.data.qvel)), state, atol=1e-12, rtol=0)

    def test_external_force_reaches_every_substep_and_release(self):
        sim = self.sim
        sim.set_object_shape("cuboid")
        sim.data.qpos[sim.bq : sim.bq + 3] = [2, 0, 0.7]
        mujoco.mj_forward(sim.model, sim.data)
        force = np.zeros_like(sim.data.xfrc_applied)
        force[sim.box, 0] = 10
        original = force.copy()
        sim.step(force)
        expected_velocity = 10 / 1.125 * sim.dt
        self.assertAlmostEqual(sim.data.qvel[sim.bv], expected_velocity, delta=1e-4)
        np.testing.assert_array_equal(force, original)
        velocity = sim.data.qvel[sim.bv]
        sim.step(np.zeros_like(force))
        self.assertAlmostEqual(sim.data.qvel[sim.bv], velocity, delta=1e-4)
        sim.stop()
        np.testing.assert_array_equal(sim.data.xfrc_applied, 0)
        np.testing.assert_array_equal(sim.data.ctrl, 0)
        sim.reset()
        np.testing.assert_array_equal(sim.data.xfrc_applied, 0)
        np.testing.assert_array_equal(sim.data.qvel, 0)
        with self.assertRaises(KeyError):
            sim.set_object_shape("unsupported")
        self.assertEqual(sim.object_shape, "cuboid")


if __name__ == "__main__":
    unittest.main()
