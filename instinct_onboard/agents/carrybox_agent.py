"""Carrybox agent using the same action terms and TargetJointState as locomotion."""

import numpy as np

from instinct_onboard.agents.action_term import (
    JointPositionAction,
    pack_policy_action_to_target_joint_state,
)
from instinct_onboard.carrybox_policy import CarryBoxPolicy


class CarryBoxAgent:
    def __init__(self, bundle, ros_node):
        self.ros_node = ros_node
        self.policy = CarryBoxPolicy(bundle)
        cfg = self.policy.config
        if list(ros_node.sim_joint_names) != cfg["joint_names"]:
            raise ValueError("Carrybox requires the training pelvis-rooted joint order")
        self.default_joint_pos = self.policy.default_joint_pos
        self.p_gains = np.asarray(cfg["kp"], dtype=np.float32)
        self.d_gains = np.asarray(cfg["kd"], dtype=np.float32)
        self.action_terms = [
            JointPositionAction(
                name="joint_pos",
                action_cfg={"joint_names": [".*"], "scale": 0.25, "use_default_offset": True},
                ros_node=ros_node,
                default_joint_pos=self.default_joint_pos,
                p_gains=self.p_gains,
                d_gains=self.d_gains,
            )
        ]

    def reset(self):
        self.policy.reset()

    def act(self, q, dq, gyro, quaternion, depth, timestamp, depth_timestamp):
        proprio, images = self.policy.observe(q, dq, gyro, quaternion, depth, timestamp, depth_timestamp)
        action = self.policy.infer(proprio, images)
        return pack_policy_action_to_target_joint_state(action, self.action_terms)

    def step(self):
        from instinct_onboard.agents.base import AgentStatus

        node = self.ros_node
        target = self.act(
            node.joint_pos_,
            node.joint_vel_,
            node._get_base_ang_vel_obs(),
            node._get_quat_w_obs(),
            node.policy_depth,
            node.policy_time,
            node.depth_time,
        )
        return target, AgentStatus.Working
