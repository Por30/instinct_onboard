import time

import cv2
import numpy as np
import onnxruntime
import pyrealsense2
import quaternion
import rclpy
import ros2_numpy
from crc_module import get_crc
from unitree_go.msg import WirelessController
from unitree_hg.msg import IMUState, LowCmd, LowState

from instinct_onboard.agents.parkour_agent import ParkourStandAgent
from instinct_onboard.simulation.stand import StandPolicy

stand = StandPolicy("models/stand_onboard")
previous_action = None
target = stand.act(np.zeros(29), np.zeros(29), np.zeros(3), np.array([0, 0, -1]), previous_action)
assert np.isfinite(target.position).all()
print("Official stand inference: OK", flush=True)

rclpy.init()
node = rclpy.create_node("carrybox_environment_check")
try:
    received = []
    topic = "/carrybox_environment_check"
    sub = node.create_subscription(LowCmd, topic, lambda msg: received.append(msg.crc), 10)
    pub = node.create_publisher(LowCmd, topic, 10)
    msg = LowCmd()
    msg.crc = get_crc(msg)
    deadline = time.monotonic() + 3
    while not received and time.monotonic() < deadline:
        pub.publish(msg)
        rclpy.spin_once(node, timeout_sec=0.1)
    assert received == [msg.crc], received
    print("Humble, CycloneDDS loopback, Unitree messages, CRC: OK", flush=True)
finally:
    node.destroy_node()
    rclpy.shutdown()
print("Dependency imports including pyrealsense2: OK", flush=True)
