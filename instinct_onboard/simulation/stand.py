"""ROS-free execution of the official TorsoBase stand bundle for MuJoCo."""

import re
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import onnxruntime as ort
import yaml

from instinct_onboard.agents.action_term import (
    action_term_to_policy_action,
    pack_policy_action_to_target_joint_state,
    parse_action_cfgs,
)
from instinct_onboard.robot_cfgs import G1_29Dof_TorsoBase


class StandPolicy:
    def __init__(self, bundle):
        bundle = Path(bundle)
        with (bundle / "params/env.yaml").open() as stream:
            cfg = yaml.unsafe_load(stream)
        self.joint_names = G1_29Dof_TorsoBase.sim_joint_names
        robot = cfg["scene"]["robot"]
        self.default_joint_pos = self.joint_values(robot["init_state"]["joint_pos"])
        self.kp, self.kd = np.zeros(29, np.float32), np.zeros(29, np.float32)
        for actuator in robot["actuators"].values():
            mask = [any(re.search(p, n) for p in actuator["joint_names_expr"]) for n in self.joint_names]
            for gains, field in ((self.kp, "stiffness"), (self.kd, "damping")):
                value = actuator[field]
                resolved = self.joint_values(value) if isinstance(value, dict) else np.full(29, value)
                gains[mask] = resolved[mask]
        self.action_terms = parse_action_cfgs(
            cfg["actions"],
            SimpleNamespace(NUM_JOINTS=29, sim_joint_names=self.joint_names),
            self.default_joint_pos,
            self.kp,
            self.kd,
            default_joint_vel=self.joint_values(robot["init_state"]["joint_vel"]),
        )
        names = ("base_ang_vel", "projected_gravity", "velocity_commands", "joint_pos", "joint_vel", "actions")
        terms = {k: v for k, v in cfg["observations"]["policy"].items() if isinstance(v, dict)}
        if tuple(terms) != (*names, "depth_image") or any(terms[n]["history_length"] != 8 for n in names):
            raise ValueError("Stand requires the official six-term, eight-frame observation contract")
        self.terms = {name: terms[name] for name in names}
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        self.encoder = ort.InferenceSession(
            str(bundle / "exported/0-depth_encoder.onnx"), options, providers=["CPUExecutionProvider"]
        )
        self.actor = ort.InferenceSession(
            str(bundle / "exported/actor.onnx"), options, providers=["CPUExecutionProvider"]
        )
        if (
            self.encoder.get_inputs()[0].shape != [1, 8, 18, 32]
            or self.encoder.get_outputs()[0].shape != [1, 128]
            or self.actor.get_inputs()[0].shape != [1, 896]
            or self.actor.get_outputs()[0].shape != [1, 29]
        ):
            raise ValueError("Official stand ONNX input/output shapes do not match")
        self.depth_latent = self.encoder.run(
            None, {self.encoder.get_inputs()[0].name: np.zeros((1, 8, 18, 32), np.float32)}
        )[0]
        self.reset()

    def joint_values(self, patterns):
        values = np.zeros(29, np.float32)
        for pattern, value in patterns.items():
            for index, name in enumerate(self.joint_names):
                if re.search(pattern, name):
                    values[index] = value
        return values

    def reset(self):
        self.history = {}
        self.actor_input = None

    def act(self, q, dq, gyro, gravity, last_target):
        values = dict(
            base_ang_vel=np.array(gyro, np.float32),
            projected_gravity=np.array(gravity, np.float32),
            velocity_commands=np.zeros(3, np.float32),
            joint_pos=np.array(q, np.float32) - self.default_joint_pos,
            joint_vel=np.array(dq, np.float32),
            actions=action_term_to_policy_action(last_target, self.action_terms),
        )
        observations = []
        for name, term in self.terms.items():
            value = values[name]
            if term.get("clip") is not None:
                value = np.clip(value, -term["clip"], term["clip"])
            if term.get("scale") is not None:
                value *= term["scale"]
            if name not in self.history:
                self.history[name] = np.repeat(value[None], 8, axis=0)
            else:
                self.history[name] = np.roll(self.history[name], -1, axis=0)
                self.history[name][-1] = value
            observations.append(self.history[name].reshape(1, -1))
        self.actor_input = np.concatenate([*observations, self.depth_latent], axis=1).astype(np.float32)
        if not np.isfinite(self.actor_input).all():
            raise ValueError("Nonfinite stand observation")
        action = self.actor.run(None, {self.actor.get_inputs()[0].name: self.actor_input})[0].reshape(-1)
        if action.shape != (29,) or not np.isfinite(action).all():
            raise ValueError("Invalid stand action")
        return pack_policy_action_to_target_joint_state(action, self.action_terms)
