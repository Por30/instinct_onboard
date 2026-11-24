"""G1 carrybox: automatic cold start, R1 stand, L1 carrybox, L2/R2/B motor-off.

Default ROS commands go only to a dry-run topic. --offline exercises inference
without ROS, RealSense or robot communication.
"""

from __future__ import annotations

import argparse
import json
import multiprocessing.shared_memory as shared_memory
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from instinct_onboard.agents.carrybox_agent import CarryBoxAgent
from instinct_onboard.carrybox_policy import (
    CarryBoxWatchdog,
    resample_depth,
    rotation_wxyz,
)
from instinct_onboard.robot_cfgs import G1_29Dof_CarryBox, G1_29Dof_TorsoBase
from instinct_onboard.target_joint_state import TargetJointState

CARRYBOX_TO_TORSO = np.array(
    [G1_29Dof_CarryBox.sim_joint_names.index(name) for name in G1_29Dof_TorsoBase.sim_joint_names]
)
TORSO_TO_CARRYBOX = np.argsort(CARRYBOX_TO_TORSO)


def torso_target(target):
    """Map a pelvis-rooted carrybox target into the original stand node's convention."""
    fields = {}
    for name in ("position", "velocity", "effort", "kp", "kd"):
        values = getattr(target, name)[CARRYBOX_TO_TORSO]
        if name in ("position", "velocity", "effort"):
            values = values * G1_29Dof_TorsoBase.joint_signs
        fields[name] = values
    return TargetJointState(**fields)


def camera_process(
    camera_cls, depth_resolution, color_resolution, camera_kwargs, depth_shm_name, color_shm_name, affinity
):
    """Reuse the camera process protocol while sampling actual calibrated depth rays."""
    from instinct_onboard.ros_nodes.camera_base import (
        SIZE_OF_MP_SHARED_HEADER,
        MpSharedHeader,
        _release_barrier,
    )

    camera = None
    memory = shared_memory.SharedMemory(name=depth_shm_name)
    header = MpSharedHeader.from_buffer(memory.buf)
    output = np.ndarray(depth_resolution[::-1], dtype=np.float32, buffer=memory.buf, offset=SIZE_OF_MP_SHARED_HEADER)
    try:
        camera = camera_cls(depth_resolution=(480, 270), depth_fps=60, camera_serial=camera_kwargs["camera_serial"])
        import pyrealsense2 as rs

        intrinsics = camera.profile.get_stream(rs.stream.depth).as_video_stream_profile().get_intrinsics()
        if any(abs(c) > 1e-8 for c in intrinsics.coeffs):
            raise ValueError("Carrybox requires rectified depth; nonzero distortion needs calibrated rectification")
        while not header.writer_termination_signal:
            if not camera.refresh_camera_data():
                continue
            received = time.time()
            frame = resample_depth(
                camera.get_depth_image(),
                [intrinsics.fx, intrinsics.fy, intrinsics.ppx, intrinsics.ppy],
                camera_kwargs["training_camera"],
            )
            header.writer_status = 1
            output[:] = frame
            header.timestamp = received
            header.frame_counter += 1
            _release_barrier()
            header.writer_status = 0
    finally:
        if camera is not None:
            camera.destroy_node()
        del output, header
        memory.close()


def offline(bundle, steps):
    class OfflineState:
        NUM_JOINTS = 29
        sim_joint_names = G1_29Dof_CarryBox.sim_joint_names

    agent = CarryBoxAgent(bundle, OfflineState())
    for step in range(steps):
        target = agent.act(
            agent.default_joint_pos,
            np.zeros(29),
            np.zeros(3),
            [1, 0, 0, 0],
            np.full((27, 48), 3, np.float32),
            step * 0.02,
            step * 0.02,
        )
        if not all(np.isfinite(getattr(target, key)).all() for key in ("position", "velocity", "effort", "kp", "kd")):
            raise ValueError("Nonfinite offline target")
    print(
        json.dumps(
            dict(
                mode="offline",
                steps=steps,
                motor_messages=0,
                checkpoint_sha256=agent.policy.config["checkpoint_sha256"],
            )
        )
    )


def run_ros(args):
    import rclpy

    from instinct_onboard.agents.base import AgentStatus, ColdStartAgent
    from instinct_onboard.joystick import UnitreeJoyStick
    from instinct_onboard.ros_nodes.camera_base import (
        CameraProcessSpawner,
        _acquire_barrier,
    )
    from instinct_onboard.ros_nodes.realsense import RealsenseCamera
    from instinct_onboard.ros_nodes.unitree import UnitreeNode

    class CarryBoxJoystick(UnitreeJoyStick):
        def _parse_message(self, msg):
            super()._parse_message(msg)
            self._ros_node.watchdog.update("joystick", time.monotonic())

        def _check_safety_shutdown(self, msg):
            return super()._check_safety_shutdown(msg) or self.data.B

        def _handle_safety_shutdown(self):
            self._ros_node.stop("joystick e-stop")
            raise SystemExit("Joystick e-stop")

    class G1CarryBoxNode(CameraProcessSpawner, UnitreeNode):
        def __init__(self):
            self.watchdog = CarryBoxWatchdog(time.monotonic())
            self.publish_lock = threading.RLock()
            self.exit_event = threading.Event()
            cfg = json.loads((args.bundle / "manifest.json").read_text())
            self.policy_depth = None
            self.depth_time = None
            self.phase = None
            self.last_buttons = (False, False)
            super().__init__(
                camera_cls=RealsenseCamera,
                subprocess_func=camera_process,
                camera_kwargs={"training_camera": cfg["camera"]},
                depth_resolution=(48, 27),
                depth_fps=60,
                camera_serial=args.camera_serial,
                camera_dead_behavior="raise_error",
                robot_class_name="G1_29Dof_TorsoBase",
                dryrun=not args.nodryrun,
            )
            self.agent = CarryBoxAgent(
                args.bundle, SimpleNamespace(NUM_JOINTS=29, sim_joint_names=G1_29Dof_CarryBox.sim_joint_names)
            )
            self.torque_limits = np.minimum(self.torque_limits, np.asarray(cfg["effort"])[CARRYBOX_TO_TORSO])
            self.base_velocity_cmd = np.zeros(3, dtype=np.float32)
            self.stand_agent = None
            if args.standdir:
                from instinct_onboard.agents.parkour_agent import ParkourStandAgent

                class StandAgent(ParkourStandAgent):
                    def _get_joint_vel_rel_obs(self):
                        """Keep the stand observation's in-place scale out of the shared state."""
                        return super()._get_joint_vel_rel_obs().copy()

                self.stand_agent = StandAgent(logdir=str(args.standdir), ros_node=self)
                self.watchdog.limits = {**self.watchdog.limits, "torso": 0.1}
            pose = torso_target(
                TargetJointState(
                    self.agent.default_joint_pos, np.zeros(29), np.zeros(29), self.agent.p_gains, self.agent.d_gains
                )
            )
            self.cold_start_agent = ColdStartAgent(
                startup_step_size=args.startup_step_size,
                ros_node=self,
                joint_target_pos=pose.position,
                p_gains=pose.kp * args.kpkd_factor,
                d_gains=pose.kd * args.kpkd_factor,
            )
            self.pose_stand_agent = ColdStartAgent(
                startup_step_size=args.startup_step_size,
                ros_node=self,
                joint_target_pos=pose.position,
                p_gains=pose.kp,
                d_gains=pose.kd,
            )
            self.joystick = CarryBoxJoystick(self, safety_shutdown_callback=lambda: self.stop("joystick e-stop"))
            self.monitor = threading.Thread(target=self.monitor_streams, daemon=True)
            self.monitor.start()

        def _torso_imu_state_callback(self, msg):
            super()._torso_imu_state_callback(msg)
            if self.stand_agent is not None:
                rotation_wxyz(msg.quaternion)
                if not np.isfinite(msg.gyroscope).all():
                    self.stop("nonfinite torso IMU")
                    raise ValueError(self.watchdog.fault)
                self.watchdog.update("torso", time.monotonic())

        def _low_state_callback(self, msg):
            super()._low_state_callback(msg)
            rotation_wxyz(msg.imu_state.quaternion)
            if not np.isfinite(np.r_[self.joint_pos_, self.joint_vel_, msg.imu_state.gyroscope]).all():
                self.stop("nonfinite robot state")
                raise ValueError(self.watchdog.fault)
            self.watchdog.update("state", time.monotonic())

        def refresh_depth(self):
            self.prevent_camera_process_dead()
            header = self._depth_header
            if header.writer_status or not header.frame_counter:
                return
            _acquire_barrier()
            count, stamp = header.frame_counter, header.timestamp
            frame = self._depth_buffer.copy()
            _acquire_barrier()
            if header.writer_status or count != header.frame_counter:
                return
            age = time.time() - stamp
            if not np.isfinite(age) or age < 0 or age > 0.1:
                raise ValueError("Camera production timestamp stale or invalid")
            self.policy_depth = frame
            self.depth_time = time.monotonic() - age
            self.watchdog.update("depth", self.depth_time)

        def check_buffers_ready(self):
            self.watchdog.check(time.monotonic())
            self.refresh_depth()
            return (
                hasattr(self, "low_state_buffer")
                and "joystick" in self.watchdog.times
                and self.policy_depth is not None
                and (self.stand_agent is None or "torso" in self.watchdog.times)
            )

        def monitor_streams(self):
            while not self.exit_event.wait(0.01):
                try:
                    self.watchdog.check(time.monotonic())
                except RuntimeError as exc:
                    self.stop(str(exc))
                    return

        def stop(self, reason):
            with self.publish_lock:
                self.watchdog.fault = reason
                self.phase = "stopped"
                if hasattr(self, "low_cmd_publisher"):
                    self._turn_off_motors()

        def start_ros_handlers(self):
            super().start_ros_handlers()
            if self.stand_agent is not None:
                target, _ = self.checked_agent_step(self.stand_agent)
                self.check_target(target)
                for history in self.stand_agent.obs_history_buffers.values():
                    history.reset()
                self.watchdog.check(time.monotonic())
            self.watchdog.update("control", time.monotonic())
            self.watchdog.armed = True
            self.timer = self.create_timer(0.02, self.tick)
            self.get_logger().info(
                "Automatic cold start; R1: stand; L1: carrybox; R1: return to stand. L2/R2/B: motor-off."
            )
            if self.stand_agent is None:
                self.get_logger().info("DRY-RUN pose stand only: no learned balancing policy loaded.")

        @staticmethod
        def checked_agent_step(agent):
            target, status = agent.step()
            if status not in (AgentStatus.Working, AgentStatus.Reached):
                raise RuntimeError(f"Agent refused or failed: {status}")
            return target, status

        @staticmethod
        def check_target(target):
            for key in ("position", "velocity", "effort", "kp", "kd"):
                values = getattr(target, key)
                if values.shape != (29,) or not np.isfinite(values).all():
                    raise ValueError(f"Invalid joint target: {key}")

        def switch_phase(self, phase):
            self.phase = phase
            if phase == "carrybox":
                self.agent.reset()
            elif phase == "stand":
                (self.stand_agent or self.pose_stand_agent).reset()
                if self.stand_agent is not None:
                    for history in self.stand_agent.obs_history_buffers.values():
                        history.reset()
            else:
                self.cold_start_agent.reset()
            self.get_logger().info(f"Switched to {phase}.")

        def carrybox_step(self):
            signs = G1_29Dof_TorsoBase.joint_signs
            imu = self.low_state_buffer.imu_state
            return torso_target(
                self.agent.act(
                    (self.joint_pos_ * signs)[TORSO_TO_CARRYBOX],
                    (self.joint_vel_ * signs)[TORSO_TO_CARRYBOX],
                    imu.gyroscope,
                    imu.quaternion,
                    self.policy_depth,
                    self.policy_time,
                    self.depth_time,
                )
            )

        def tick(self):
            started = time.monotonic()
            try:
                self.refresh_depth()
                self.watchdog.check(time.monotonic())
                self.policy_time = time.monotonic()
                buttons = (bool(self.joystick.data.R1), bool(self.joystick.data.L1))
                pressed = tuple(a and not b for a, b in zip(buttons, self.last_buttons))
                self.last_buttons = buttons
                target = None
                next_phase = None
                if self.phase is None:
                    self.switch_phase("cold_start")
                elif self.phase == "cold_start":
                    target, status = self.checked_agent_step(self.cold_start_agent)
                    if status == AgentStatus.Reached and pressed[0] and not buttons[1]:
                        next_phase = "stand"
                elif self.phase == "stand":
                    target, _ = self.checked_agent_step(self.stand_agent or self.pose_stand_agent)
                    if pressed[1] and not buttons[0]:
                        next_phase = "carrybox"
                elif self.phase == "carrybox":
                    if pressed[0]:
                        self.switch_phase("stand")
                        target, _ = self.checked_agent_step(self.stand_agent or self.pose_stand_agent)
                    else:
                        target = self.carrybox_step()
                else:
                    raise RuntimeError(f"Invalid control phase: {self.phase}")
                with self.publish_lock:
                    now = time.monotonic()
                    self.watchdog.check(now)
                    if now - started > 0.02:
                        raise RuntimeError("Control step missed its 20 ms deadline")
                    if target is not None:
                        self.check_target(target)
                        if not self.send_target_joint_state(target):
                            raise RuntimeError("Motor target rejected")
                    self.watchdog.update("control", now)
                    if next_phase is not None:
                        self.switch_phase(next_phase)
            except Exception as exc:
                self.stop(str(exc))
                raise

    rclpy.init()
    node = None
    try:
        node = G1CarryBoxNode.__new__(G1CarryBoxNode)
        node.__init__()
        node.start_ros_handlers()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.stop(node.watchdog.fault or "shutdown")
            node.exit_event.set()
            if hasattr(node, "monitor"):
                node.monitor.join(timeout=1)
            if hasattr(node, "camera_process"):
                node.destroy_node()
        rclpy.shutdown()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=Path("models/carrybox_wall19"))
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--steps", type=int, default=50)
    parser.add_argument("--camera-serial")
    stand = parser.add_mutually_exclusive_group()
    stand.add_argument("--standdir", type=Path, help="Original ParkourStandAgent model directory")
    stand.add_argument(
        "--pose-stand", action="store_true", help="Dry-run only: bounded pose hold instead of a stand model"
    )
    parser.add_argument("--startup_step_size", type=float, default=0.2, help="Cold-start target step in radians")
    parser.add_argument("--kpkd_factor", type=float, default=2.0, help="Cold-start PD gain multiplier")
    parser.add_argument("--nodryrun", action="store_true", help="Explicitly enable real motor commands")
    args = parser.parse_args()
    if args.offline and args.nodryrun:
        parser.error("--offline cannot be combined with --nodryrun")
    if args.steps <= 0:
        parser.error("--steps must be positive")
    if (
        not np.isfinite([args.startup_step_size, args.kpkd_factor]).all()
        or min(args.startup_step_size, args.kpkd_factor) <= 0
    ):
        parser.error("--startup_step_size and --kpkd_factor must be finite and positive")
    if args.pose_stand and args.nodryrun:
        parser.error("--pose-stand is dry-run only; real control requires --standdir")
    if not args.offline and not (args.standdir or args.pose_stand):
        parser.error("ROS mode requires --standdir, or explicit --pose-stand for dry-run checks")
    if args.standdir:
        for name in ("params/env.yaml", "params/agent.yaml", "exported/actor.onnx", "exported/0-depth_encoder.onnx"):
            if not (args.standdir / name).is_file():
                parser.error(f"Incomplete original stand model: missing {args.standdir / name}")
    if args.offline:
        offline(args.bundle, args.steps)
    else:
        run_ros(args)


if __name__ == "__main__":
    main()
