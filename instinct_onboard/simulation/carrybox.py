"""MuJoCo Wall19 scene using captured training physics and the onboard agent.

URDF import, near-plane ray casting and COM inertia mapping follow the audited
wall11/wall18 s2s implementation in unitree_rl_lab_carrybox. No training modules
or ROS packages are imported by this backend.
"""

from __future__ import annotations

import json
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import mujoco
import numpy as np

from instinct_onboard.agents.carrybox_agent import CarryBoxAgent
from instinct_onboard.carrybox_policy import rotation_wxyz, sha256


def make_scene(bundle, cfg, box_xy):
    root = ET.parse(bundle / "robot/g1.urdf").getroot()
    compiler = root.find("mujoco/compiler")
    compiler.set("meshdir", str((bundle / "robot/meshes").resolve()))
    compiler.set("discardvisual", "false")
    compiler.set("fusestatic", "false")
    for mesh in root.findall(".//mesh"):
        mesh.set("filename", str((bundle / "robot" / mesh.get("filename")).resolve()))
    imported = mujoco.MjModel.from_xml_string(ET.tostring(root, encoding="unicode"))
    with tempfile.TemporaryDirectory(dir=bundle, prefix="scene-") as temporary:
        path = Path(temporary) / "robot.xml"
        mujoco.mj_saveLastXML(str(path), imported)
        scene = ET.parse(path).getroot()
    ET.SubElement(
        scene,
        "option",
        timestep=str(cfg["physics_dt"]),
        integrator="implicitfast",
        gravity="0 0 -9.81",
        iterations="100",
    )
    world = scene.find("worldbody")
    robot = world.find("body[@name='pelvis']")
    ET.SubElement(robot, "freejoint", name="robot_root")
    for geom in robot.iter("geom"):
        visual = geom.get("contype", "1") == "0" and geom.get("conaffinity", "1") == "0"
        geom.set("group", "1" if visual else "3")
        if not visual:
            geom.set("contype", "1")
            geom.set("conaffinity", "3")
            geom.set("friction", "1 .005 .0001")
            if geom.get("type") == "cylinder":
                geom.set("type", "capsule")
    actuator = ET.SubElement(scene, "actuator")
    for name, armature, effort in zip(cfg["joint_names"], cfg["armature"], cfg["effort"]):
        joint = robot.find(f".//joint[@name='{name}']")
        joint.set("armature", str(armature))
        joint.set("damping", "0")
        joint.set("frictionloss", "0")
        ET.SubElement(
            actuator,
            "motor",
            name=name,
            joint=name,
            gear="1",
            ctrllimited="true",
            ctrlrange=f"{-effort} {effort}",
            forcelimited="true",
            forcerange=f"{-effort} {effort}",
        )
    ET.SubElement(world, "light", pos="0 -3 5", dir="0 0 -1", directional="true")
    common = dict(contype="2", conaffinity="3", friction="1 .005 .0001", group="0")
    ET.SubElement(
        world,
        "geom",
        name="floor",
        type="plane",
        size="10 10 .1",
        rgba=".25 .3 .35 1",
        **dict(common, friction=".9 .005 .0001"),
    )
    box = ET.SubElement(world, "body", name="box", pos=f"{box_xy[0]} {box_xy[1]} .13")
    ET.SubElement(box, "freejoint", name="box_free")
    ET.SubElement(
        box, "geom", name="box_geom", type="box", size=".15 .15 .125", mass="1.125", rgba=".65 .4 .15 1", **common
    )
    return ET.tostring(scene, encoding="unicode")


def inertia_in_link(body):
    matrix = rotation_wxyz(np.asarray(body["com_quat_xyzw"])[[3, 0, 1, 2]])
    return matrix @ np.asarray(body["inertia_com_kg_m2"]) @ matrix.T


def apply_physics(model, profile):
    ids = []
    for name, body in profile["bodies"].items():
        index = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, name)
        if index < 0:
            raise ValueError(f"Captured body missing from MuJoCo: {name}")
        values, basis = np.linalg.eigh(inertia_in_link(body))
        if values.min() <= 0:
            raise ValueError(f"Invalid inertia for {name}")
        if np.linalg.det(basis) < 0:
            basis[:, 0] *= -1
        quat = np.empty(4)
        mujoco.mju_mat2Quat(quat, np.ascontiguousarray(basis).ravel())
        model.body_mass[index] = body["mass_kg"]
        model.body_ipos[index] = body["com_xyz"]
        model.body_inertia[index] = values
        model.body_iquat[index] = quat
        ids.append(index)
    mujoco.mj_setConst(model, mujoco.MjData(model))
    return np.asarray(ids)


class DepthCamera:
    def __init__(self, model, config):
        self.model, self.config = model, config
        self.parent = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, "torso_link")
        self.offset_rotation = rotation_wxyz(config["quaternion_wxyz"])
        v, u = np.mgrid[:27, :48]
        rays = np.stack(
            (np.ones_like(u), -(u + 0.5 - 24) / config["fx"], -(v + 0.5 - 13.5) / config["fy"]), -1
        ).reshape(-1, 3)
        self.rays = rays / np.linalg.norm(rays, axis=-1, keepdims=True)
        self.groups = np.array([1, 1, 0, 0, 0, 0], dtype=np.uint8)
        self.hits = np.empty(len(rays), dtype=np.int32)

    def render(self, data):
        parent_rotation = data.xmat[self.parent].reshape(3, 3)
        origin = data.xpos[self.parent] + parent_rotation @ self.config["position"]
        directions = self.rays @ (parent_rotation @ self.offset_rotation).T
        depth = np.full(len(self.rays), 3.0, dtype=np.float32)
        hit = np.empty(1, dtype=np.int32)
        for pixel, direction in enumerate(directions):
            cosine = self.rays[pixel, 0]
            start = origin + direction * (0.1 / cosine)
            distance = mujoco.mj_ray(self.model, data, start, direction, self.groups, 1, -1, hit)
            optical = 0.1 + distance * cosine
            self.hits[pixel] = -1
            if distance >= 0 and optical <= 3.0:
                depth[pixel], self.hits[pixel] = optical, hit[0]
        return depth.reshape(27, 48)


class CarryBoxSim:
    NUM_JOINTS = 29

    def __init__(self, bundle, box_xy=(1.0, 0.0)):
        self.bundle = Path(bundle)
        cfg = json.loads((self.bundle / "manifest.json").read_text())
        for path, digest in cfg["asset_sha256"].items():
            if sha256(self.bundle / path) != digest:
                raise ValueError(f"Simulation asset hash mismatch: {path}")
        self.sim_joint_names = cfg["joint_names"]
        self.agent = CarryBoxAgent(bundle, self)
        self.cfg = cfg
        self.profile = json.loads((self.bundle / "physics.json").read_text())
        self.model = mujoco.MjModel.from_xml_string(make_scene(self.bundle, cfg, box_xy))
        self.robot_bodies = apply_physics(self.model, self.profile)
        self.data = mujoco.MjData(self.model)
        joints = [self.model.joint(name).id for name in self.sim_joint_names]
        self.qadr = self.model.jnt_qposadr[joints]
        self.vadr = self.model.jnt_dofadr[joints]
        self.actuators = [self.model.actuator(name).id for name in self.sim_joint_names]
        self.box = self.model.body("box").id
        box_joint = self.model.joint("box_free").id
        self.bq = self.model.jnt_qposadr[box_joint]
        self.bv = self.model.jnt_dofadr[box_joint]
        self.hands = [self.model.body(f"{side}_rubber_hand").id for side in ("left", "right")]
        self.head = self.model.body("mid360_link").id
        self.hips = [self.model.body(f"{side}_hip_pitch_link").id for side in ("left", "right")]
        self.effort = np.asarray(cfg["effort"])
        self.camera = DepthCamera(self.model, cfg["camera"])
        self.box_xy = np.asarray(box_xy)
        self.dt = cfg["control_dt"]
        self.reset()

    def reset(self):
        mujoco.mj_resetData(self.model, self.data)
        self.data.qpos[:7] = self.cfg["default_root_pose"]
        self.data.qpos[self.qadr] = self.agent.default_joint_pos
        self.data.qpos[self.bq : self.bq + 7] = [*self.box_xy, 0.13, 1, 0, 0, 0]
        self.agent.reset()
        self.steps = self.pickup_steps = self.strict_steps = 0
        self.pickup_success = self.strict_success = False
        self.metric_step = None
        self.max_torque_ratio = 0.0
        self.stop_reason = None
        mujoco.mj_forward(self.model, self.data)

    def stop(self, reason="user_stop"):
        self.stop_reason = reason
        self.data.ctrl[:] = 0
        self.data.xfrc_applied[:] = 0

    def observations(self):
        return (
            self.data.qpos[self.qadr].copy(),
            self.data.qvel[self.vadr].copy(),
            self.data.qvel[3:6].copy(),
            self.data.qpos[3:7].copy(),
            self.camera.render(self.data),
        )

    def apply_damping(self):
        self.data.xfrc_applied[:] = 0
        for body in np.flatnonzero(self.model.body_mass > 0):
            velocity = np.empty(6)
            mujoco.mj_objectVelocity(self.model, self.data, mujoco.mjtObj.mjOBJ_BODY, body, velocity, 0)
            self.data.xfrc_applied[body, :3] = -0.01 * self.model.body_mass[body] * velocity[3:]
            matrix = self.data.ximat[body].reshape(3, 3)
            self.data.xfrc_applied[body, 3:] = (
                -0.01 * matrix @ (self.model.body_inertia[body] * (matrix.T @ velocity[:3]))
            )

    def step(self):
        if self.stop_reason:
            raise RuntimeError(f"Simulation is stopped: {self.stop_reason}; reset required")
        try:
            target = self.agent.act(*self.observations(), self.data.time, self.data.time)
            for _ in range(round(self.dt / self.model.opt.timestep)):
                torque = (
                    target.kp * (target.position - self.data.qpos[self.qadr]) - target.kd * self.data.qvel[self.vadr]
                )
                if not np.isfinite(torque).all():
                    raise FloatingPointError("Nonfinite PD torque")
                self.data.ctrl[self.actuators] = np.clip(torque, -self.effort, self.effort)
                self.apply_damping()
                mujoco.mj_step(self.model, self.data)
                if not np.isfinite(np.concatenate((self.data.qpos, self.data.qvel, self.data.qacc))).all():
                    raise FloatingPointError("Nonfinite MuJoCo state")
                for warning in (
                    mujoco.mjtWarning.mjWARN_BADQPOS,
                    mujoco.mjtWarning.mjWARN_BADQVEL,
                    mujoco.mjtWarning.mjWARN_BADQACC,
                ):
                    if self.data.warning[warning].number:
                        raise RuntimeError("MuJoCo reported unstable dynamics")
                ratio = float(np.max(abs(self.data.actuator_force[self.actuators]) / self.effort))
                self.max_torque_ratio = max(ratio, self.max_torque_ratio)
                if ratio > 1 + 1e-6:
                    raise RuntimeError("Actuator torque exceeded its limit")
                q = self.data.qpos[self.qadr]
                if np.any(q < np.asarray(self.cfg["joint_lower"]) - 0.15) or np.any(
                    q > np.asarray(self.cfg["joint_upper"]) + 0.15
                ):
                    raise RuntimeError("Joint state exceeded URDF limits by more than 0.15 rad")
            mujoco.mj_forward(self.model, self.data)
            self.steps += 1
            return self.metrics()
        except Exception:
            self.stop("runtime_fault")
            raise

    def metrics(self):
        forces = np.zeros(2)
        for contact_index in range(self.data.ncon):
            contact = self.data.contact[contact_index]
            bodies = {int(self.model.geom_bodyid[g]) for g in (contact.geom1, contact.geom2)}
            for side, hand in enumerate(self.hands):
                if bodies == {self.box, hand}:
                    force = np.empty(6)
                    mujoco.mj_contactForce(self.model, self.data, contact_index, force)
                    forces[side] += abs(force[0])
        box_r = rotation_wxyz(self.data.qpos[self.bq + 3 : self.bq + 7])
        root_r = rotation_wxyz(self.data.qpos[3:7])
        height = float(self.data.qpos[self.bq + 2])
        clearance = height - float(abs(box_r[2]) @ np.array([0.15, 0.15, 0.125]))
        speed = float(np.linalg.norm(self.data.qvel[self.bv : self.bv + 3]))
        head = float(self.data.xpos[self.head, 2])
        roll = float(np.arctan2(root_r[2, 1], root_r[2, 2]))
        pitch = float(np.arcsin(np.clip(-root_r[2, 0], -1, 1)))
        root_velocity = np.empty(6)
        mujoco.mj_objectVelocity(
            self.model, self.data, mujoco.mjtObj.mjOBJ_BODY, self.model.body("pelvis").id, root_velocity, 0
        )
        pickup = bool((forces > 1).all() and clearance > 0.1 and root_r[2, 2] > 0.8 and head > 0.8 and speed < 1.5)
        strict = bool(
            pickup
            and height > 0.7
            and box_r[2, 2] > 0.8
            and root_r[2, 2] > 0.95
            and head > 1.05
            and np.linalg.norm(root_velocity[3:5]) < 0.15
            and abs(root_velocity[2]) < 0.3
            and speed < 0.15
            and np.linalg.norm(self.data.qpos[self.bq : self.bq + 2] - self.box_xy) < 0.35
        )
        if self.metric_step != self.steps:
            self.pickup_steps = self.pickup_steps + 1 if pickup else 0
            self.strict_steps = self.strict_steps + 1 if strict else 0
            self.pickup_success |= self.pickup_steps * self.dt >= 1.0
            self.strict_success |= self.strict_steps * self.dt >= 2.0
            self.metric_step = self.steps
        conditions = {
            "tipped": abs(roll) > 0.5 or abs(pitch) > 1.1,
            "fell_pelvis": self.data.qpos[2] < 0.2,
            "fell_head": head < 0.6,
            "fell_hip": (self.data.xpos[self.hips, 2] < 0.15).any(),
            "box_speed": np.linalg.norm(self.data.qvel[self.bv : self.bv + 2]) > 3.0,
        }
        for name, triggered in conditions.items():
            if triggered:
                self.stop(name)
                break
        return dict(
            time_s=float(self.data.time),
            steps=self.steps,
            stop_reason=self.stop_reason,
            pickup_1s=bool(self.pickup_success),
            strict_hold_2s=bool(self.strict_success),
            current_pickup_valid=pickup,
            current_strict_valid=strict,
            box_bottom_m=clearance,
            box_position=self.data.qpos[self.bq : self.bq + 3].tolist(),
            hand_forces_N=forces.tolist(),
            roll_rad=roll,
            pitch_rad=pitch,
            max_torque_limit_ratio=self.max_torque_ratio,
        )
