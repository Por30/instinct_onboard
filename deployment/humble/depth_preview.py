import json
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import pyrealsense2 as rs

from instinct_onboard.carrybox_policy import CarryBoxPolicy, resample_depth
from instinct_onboard.ros_nodes.realsense import RealsenseCamera

policy = CarryBoxPolicy("models/carrybox_wall19")
camera = RealsenseCamera(depth_resolution=(480, 270), depth_fps=60)
stop = threading.Event()
latest = None
error = None


def capture():
    global latest, error
    try:
        intr = camera.profile.get_stream(rs.stream.depth).as_video_stream_profile().get_intrinsics()
        if any(abs(x) > 1e-8 for x in intr.coeffs):
            raise ValueError("Carrybox requires rectified depth")
        while not stop.is_set():
            if camera.refresh_camera_data():
                stamp = time.monotonic()
                raw = camera.get_depth_image()
                image = resample_depth(raw, [intr.fx, intr.fy, intr.ppx, intr.ppy], policy.config["camera"])
                latest = (stamp, raw, image)
    except Exception as exc:
        error = exc


worker = threading.Thread(target=capture)
worker.start()
samples = []
try:
    until = time.monotonic() + 2
    while latest is None and error is None and time.monotonic() < until:
        time.sleep(0.005)
    if error:
        raise error
    if latest is None:
        raise RuntimeError("No camera frames received")
    deadline = time.monotonic()
    for _ in range(12):
        time.sleep(max(0, deadline - time.monotonic()))
        if error:
            raise error
        stamp, raw, depth = latest
        tick = time.monotonic()
        _, history = policy.observe(
            policy.default_joint_pos, np.zeros(29), np.zeros(3), [1, 0, 0, 0], depth, tick, stamp
        )
        samples.append((tick, stamp))
        deadline += 0.02
finally:
    stop.set()
    worker.join()
    camera.destroy_node()

output = Path("/capture")
np.save(output / "depth-policy-input.npy", history)
canvas = np.full((603, 824, 3), 248, dtype=np.uint8)
font = cv2.FONT_HERSHEY_SIMPLEX
cv2.putText(canvas, "G1 carrybox: live D435i depth input", (20, 35), font, 0.8, (34, 34, 34), 2, cv2.LINE_AA)
cv2.putText(
    canvas,
    "4 x 27 x 48, optical depth in metres  |  oldest to newest",
    (20, 62),
    font,
    0.53,
    (70, 70, 70),
    1,
    cv2.LINE_AA,
)
for i, frame in enumerate(history[0]):
    x, y = 20 + i % 2 * 400, 104 + i // 2 * 250
    greys = np.rint((frame - 0.1) * 255 / 2.9).clip(0, 255).astype(np.uint8)
    canvas[y : y + 216, x : x + 384] = cv2.cvtColor(
        cv2.resize(greys, (384, 216), interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR
    )
    cv2.rectangle(canvas, (x, y), (x + 383, y + 215), (110, 110, 110), 1)
    delta = (samples[-4 + i][0] - samples[-1][0]) * 1000
    cv2.putText(canvas, f"Frame {i+1}    {delta:+.0f} ms", (x, y - 9), font, 0.49, (45, 45, 45), 1, cv2.LINE_AA)
scale = np.tile(np.round(np.linspace(0, 255, 384)).astype(np.uint8), (13, 1))
canvas[585:598, 120:504] = cv2.cvtColor(scale, cv2.COLOR_GRAY2BGR)
cv2.putText(canvas, "0.1 m", (20, 596), font, 0.48, (45, 45, 45), 1, cv2.LINE_AA)
cv2.putText(canvas, "3.0 m / missing", (518, 596), font, 0.48, (45, 45, 45), 1, cv2.LINE_AA)
assert cv2.imwrite(str(output / "depth-policy-input.png"), canvas)

print(
    json.dumps(
        {
            "input_shape": list(history.shape),
            "dtype": str(history.dtype),
            "sampled_distinct_camera_frames": len({stamp for _, stamp in samples[-4:]}),
            "value_range_m": [float(history.min()), float(history.max())],
            "latest_max_or_missing_pixels": int(np.count_nonzero(history[0, -1] == 3.0)),
            "latest_raw_invalid_fraction": float(np.mean(raw <= 0)),
            "raw_resolution": list(raw.shape),
            "last_camera_age_ms": round((samples[-1][0] - samples[-1][1]) * 1000, 1),
            "checkpoint_sha256": policy.config["checkpoint_sha256"],
        },
        ensure_ascii=False,
    )
)
