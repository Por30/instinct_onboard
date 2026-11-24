"""Wall19 observations and split ONNX inference, shared by ROS and MuJoCo."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rotation_wxyz(quaternion):
    q = np.asarray(quaternion, dtype=np.float64)
    if q.shape != (4,) or not np.isfinite(q).all() or abs(np.linalg.norm(q) - 1) > 0.01:
        raise ValueError("Expected a finite unit quaternion in wxyz order")
    w, x, y, z = q / np.linalg.norm(q)
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
            [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
            [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
        ]
    )


def depth_metres(depth):
    image = np.asarray(depth, dtype=np.float32)
    if image.shape != (27, 48):
        raise ValueError(f"Expected optical depth (27, 48) in metres, got {image.shape}")
    valid = np.isfinite(image) & (image > 0)
    if not valid.any():
        raise ValueError("Depth frame has no valid measurements")
    return np.clip(np.where(valid, image, 3.0), 0.1, 3.0)


def resample_depth(depth, intrinsics, camera):
    """Sample rectified real-camera pixels along the training pinhole rays."""
    image = np.asarray(depth, dtype=np.float32)
    fx, fy, cx, cy = np.asarray(intrinsics, dtype=float)
    if image.ndim != 2 or not np.isfinite([fx, fy, cx, cy]).all() or min(fx, fy) <= 0:
        raise ValueError("Invalid depth image or rectified camera intrinsics")
    tx, ty = camera["fx"], camera["fy"]
    v, u = np.mgrid[:27, :48]
    x = np.rint((u + 0.5 - 24) / tx * fx + cx).astype(int)
    y = np.rint((v + 0.5 - 13.5) / ty * fy + cy).astype(int)
    if x.min() < 0 or y.min() < 0 or x.max() >= image.shape[1] or y.max() >= image.shape[0]:
        raise ValueError("Real camera field of view does not cover the training rays")
    return depth_metres(image[y, x])


class CarryBoxWatchdog:
    """Latch loss of any required stream; caller owns the motor-off operation."""

    limits = {"state": 0.1, "joystick": 0.5, "depth": 0.1, "control": 0.1}

    def __init__(self, started):
        self.started = started
        self.times = {}
        self.armed = False
        self.fault = None

    def update(self, stream, timestamp):
        self.times[stream] = timestamp

    def check(self, now):
        if self.fault:
            raise RuntimeError(self.fault)
        if not self.armed:
            if now - self.started > 10:
                self.fault = "Startup timed out waiting for robot, joystick and depth"
        else:
            for name, limit in self.limits.items():
                stamp = self.times.get(name, float("nan"))
                if not np.isfinite([now, stamp]).all() or not 0 <= now - stamp <= limit:
                    self.fault = f"Stale or invalid {name} timestamp"
                    break
        if self.fault:
            raise RuntimeError(self.fault)


class CarryBoxPolicy:
    def __init__(self, bundle):
        self.bundle = Path(bundle)
        self.config = json.loads((self.bundle / "manifest.json").read_text())
        cfg = self.config
        if (
            cfg["schema"] != "instinct_carrybox_wall19_v1"
            or cfg["environment_contract"]["variant"] != "walled19"
            or cfg["environment_contract"]["depth"]["normalization"] != "none"
            or cfg["history_order"] != "whole_frames_oldest_to_newest"
            or cfg["control_dt"] != 0.02
            or len(set(cfg["joint_names"])) != 29
        ):
            raise ValueError("Unsupported carrybox deployment contract")
        self.default_joint_pos = np.asarray(cfg["default_joint_pos"], dtype=np.float32)
        for name in ("default_joint_pos", "kp", "kd", "effort", "joint_lower", "joint_upper"):
            values = np.asarray(cfg[name], dtype=np.float32)
            if values.shape != (29,) or not np.isfinite(values).all():
                raise ValueError(f"Invalid deployment parameter: {name}")
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self.sessions = {}
        for name in ("depth_encoder", "actor"):
            path = self.bundle / "exported" / f"{name}.onnx"
            if sha256(path) != cfg["onnx_sha256"][name]:
                raise ValueError(f"ONNX hash mismatch: {name}")
            self.sessions[name] = ort.InferenceSession(
                str(path), sess_options=options, providers=["CPUExecutionProvider"]
            )
        for name, expected in (("depth_encoder", [["batch", 4, 27, 48]]), ("actor", [["batch", 558], ["batch", 128]])):
            inputs = self.sessions[name].get_inputs()
            if [i.shape for i in inputs] != expected or any(i.type != "tensor(float)" for i in inputs):
                raise ValueError(f"Invalid ONNX inputs: {name}")
        self.reset()

    def reset(self):
        self.previous_action = np.zeros(29, dtype=np.float32)
        self.proprio_history = None
        self.depth_history = None
        self.last_time = None

    def observe(self, q, dq, gyro, quaternion, depth, timestamp, depth_timestamp):
        now, captured = float(timestamp), float(depth_timestamp)
        if not np.isfinite([now, captured]).all() or captured > now + 1e-6 or now - captured > 0.1:
            raise ValueError("Depth timestamp is invalid, future or older than 100 ms")
        if self.last_time is not None and (now <= self.last_time or now - self.last_time > 0.1):
            raise ValueError("Policy clock stalled, moved backwards or skipped more than 100 ms; reset required")
        q, dq, gyro = (np.asarray(v, dtype=np.float32) for v in (q, dq, gyro))
        if q.shape != (29,) or dq.shape != (29,) or gyro.shape != (3,):
            raise ValueError("Invalid joint/IMU observation shape")
        gravity = rotation_wxyz(quaternion).T @ np.array([0, 0, -1.0])
        frame = np.concatenate((gyro * 0.25, gravity, q - self.default_joint_pos, dq * 0.05, self.previous_action))
        if not np.isfinite(frame).all():
            raise ValueError("Nonfinite proprioception")
        frame = np.clip(frame, -100, 100).astype(np.float32)
        image = depth_metres(depth)
        if self.proprio_history is None:
            self.proprio_history = np.repeat(frame[None], 6, axis=0)
            self.depth_history = np.repeat(image[None], 4, axis=0)
        else:
            self.proprio_history[:-1] = self.proprio_history[1:]
            self.proprio_history[-1] = frame
            self.depth_history[:-1] = self.depth_history[1:]
            self.depth_history[-1] = image
        self.last_time = now
        return self.proprio_history.reshape(1, 558).copy(), self.depth_history[None].copy()

    def infer(self, proprio, depth):
        for value, shape in ((proprio, (1, 558)), (depth, (1, 4, 27, 48))):
            if value.shape != shape or value.dtype != np.float32 or not np.isfinite(value).all():
                raise ValueError("Invalid policy input")
        latent = self.sessions["depth_encoder"].run(None, {"depth": depth})[0]
        action = self.sessions["actor"].run(None, {"proprio": proprio, "latent": latent})[0]
        if action.shape != (1, 29) or not np.isfinite(action).all():
            raise ValueError("Invalid policy action")
        self.previous_action = np.clip(action[0], -100, 100)
        return self.previous_action.copy()
