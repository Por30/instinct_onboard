"""Fixed-scene diagnostic: training limits, deployment limit values, and target clipping."""

import ast
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import imageio.v2 as imageio
import matplotlib
import mujoco
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from instinct_onboard.carrybox_policy import rotation_wxyz
from instinct_onboard.robot_cfgs import G1_29Dof_TorsoBase
from instinct_onboard.simulation.carrybox import CarryBoxSim

OUT = Path(__file__).resolve().parent
DURATION = 60.0


def deployment_clip():
    path = ROOT / "instinct_onboard/ros_nodes/base.py"
    node = next(n for n in ast.parse(path.read_text()).body if isinstance(n, ast.ClassDef) and n.name == "RealNode")
    method = next(n for n in node.body if isinstance(n, ast.FunctionDef) and n.name == "clip_by_torque_limit")
    scope = {"np": np}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), "exec"), scope)
    return scope[method.name]


def longest_run(records, field):
    count = longest = 0
    for record in records:
        count = count + 1 if record[field] else 0
        longest = max(longest, count)
    return longest * 0.02


def first_hold(records, field, seconds):
    count = 0
    for record in records:
        count = count + 1 if record[field] else 0
        if count * 0.02 >= seconds:
            return record["time_s"]
    return None


def training_diagnostics(sim, record):
    velocity = np.empty(6)
    mujoco.mj_objectVelocity(sim.model, sim.data, mujoco.mjtObj.mjOBJ_XBODY, sim.model.body("pelvis").id, velocity, 1)
    net_forces = np.zeros((2, 3))
    for index in range(sim.data.ncon):
        contact = sim.data.contact[index]
        bodies = [int(sim.model.geom_bodyid[g]) for g in (contact.geom1, contact.geom2)]
        for side, hand in enumerate(sim.hands):
            if set(bodies) == {sim.box, hand}:
                force = np.empty(6)
                mujoco.mj_contactForce(sim.model, sim.data, index, force)
                net_forces[side] += contact.frame[:3] * force[0] * (1 if bodies[1] == hand else -1)
    contact_norm = np.linalg.norm(net_forces, axis=1)
    root_r = rotation_wxyz(sim.data.qpos[3:7])
    box_r = rotation_wxyz(sim.data.qpos[sim.bq + 3 : sim.bq + 7])
    head = float(sim.data.xpos[sim.head, 2])
    hip_height = [float(sim.data.xpos[sim.model.body(f"{side}_hip_yaw_link").id, 2]) for side in ("left", "right")]
    criteria = dict(
        contacts=bool((contact_norm > 1).all()),
        clearance=record["box_bottom_m"] > 0.1,
        box_upright=box_r[2, 2] > 0.8,
        robot_upright=root_r[2, 2] > 0.95,
        head=head > 1.05,
        box_height=record["box_position"][2] >= 0.7,
        root_speed=np.linalg.norm(sim.data.qvel[:2]) < 0.15,
        yaw_speed=abs(velocity[2]) < 0.3,
        box_speed=record["box_speed_mps"] < 0.15,
        drift=record["box_xy_displacement_m"] < 0.35,
    )
    return dict(
        local_yaw_rate_rps=float(velocity[2]),
        training_root_speed_xy_mps=float(np.linalg.norm(sim.data.qvel[:2])),
        training_hip_height_m=hip_height,
        training_fell_hip=bool(min(hip_height) < 0.15),
        net_hand_forces_N=contact_norm.tolist(),
        training_pickup_valid=bool(
            criteria["contacts"]
            and criteria["clearance"]
            and root_r[2, 2] > 0.8
            and head > 0.8
            and record["box_speed_mps"] < 1.5
        ),
        training_strict_valid=all(criteria.values()),
        strict_failed_criteria=[key for key, valid in criteria.items() if not valid],
    )


def frame(renderer, sim, camera, mode, record):
    camera.lookat[:] = [sim.data.qpos[0] + 0.45, sim.data.qpos[1], 0.7]
    options = mujoco.MjvOption()
    options.geomgroup[:] = [1, 1, 0, 0, 0, 0]
    renderer.update_scene(sim.data, camera=camera, scene_option=options)
    picture = Image.fromarray(renderer.render())
    draw = ImageDraw.Draw(picture)
    draw.rectangle((0, 0, 640, 44), fill=(255, 255, 255))
    draw.text((8, 4), f"{mode} | t={record['time_s']:.2f}s | box clearance={record['box_bottom_m']:.2f}m", fill="black")
    draw.text(
        (8, 22),
        f"pickup now={record['current_pickup_valid']} | strict hold now={record['current_strict_valid']}",
        fill="black",
    )
    depth = (
        sim.agent.policy.depth_history[-1]
        if sim.agent.policy.depth_history is not None
        else sim.camera.render(sim.data)
    )
    inset = Image.fromarray(np.rint(np.clip(depth / 3, 0, 1) * 255).astype(np.uint8)).resize((192, 108))
    picture.paste(inset.convert("RGB"), (440, 365))
    draw.text((440, 349), "Policy depth: 0-3m", fill="white", stroke_width=1, stroke_fill="black")
    return np.asarray(picture)


def evaluate(mode):
    sim = CarryBoxSim(ROOT / "models/carrybox_wall19")
    if mode != "baseline":
        order = [G1_29Dof_TorsoBase.sim_joint_names.index(name) for name in sim.sim_joint_names]
        sim.effort = np.minimum(sim.effort, G1_29Dof_TorsoBase.torque_limits[order])
        sim.model.actuator_ctrlrange[sim.actuators] = np.column_stack((-sim.effort, sim.effort))
        sim.model.actuator_forcerange[sim.actuators] = np.column_stack((-sim.effort, sim.effort))
    timing, clip_counts = [], []
    act = sim.agent.act
    clip = deployment_clip()

    def timed_act(*args):
        started = time.perf_counter()
        target = act(*args)
        timing.append(time.perf_counter() - started)
        if mode == "target_clipped":
            node = SimpleNamespace(
                joint_pos_=sim.data.qpos[sim.qadr].copy(),
                joint_vel_=sim.data.qvel[sim.vadr].copy(),
                torque_limits=sim.effort,
            )
            clipped = clip(node, target.position, target.kp, target.kd)
            clip_counts.append(int(np.count_nonzero(clipped != target.position)))
            target.position = clipped
        return target

    sim.agent.act = timed_act
    records, snapshots = [], []
    camera = mujoco.MjvCamera()
    camera.distance, camera.azimuth, camera.elevation = 3.0, 125, -12
    sample_times = [0, 2, 5, 10, 20, 30, 45, 60]
    renderer = mujoco.Renderer(sim.model, height=480, width=640)
    writer = imageio.get_writer(OUT / f"{mode}.mp4", fps=10, codec="libx264", quality=7, macro_block_size=None)
    started = time.monotonic()
    failure = None
    try:
        initial = sim.metrics()
        initial_frame = frame(renderer, sim, camera, mode, initial)
        snapshots.append((0.0, initial_frame))
        writer.append_data(initial_frame)
        sample_times.pop(0)
        while sim.data.time < DURATION and not sim.stop_reason:
            try:
                record = sim.step()
            except Exception as exc:
                failure = f"{type(exc).__name__}: {exc}"
                break
            velocity = np.empty(6)
            mujoco.mj_objectVelocity(
                sim.model, sim.data, mujoco.mjtObj.mjOBJ_BODY, sim.model.body("pelvis").id, velocity, 0
            )
            record.update(
                pelvis_height_m=float(sim.data.qpos[2]),
                root_speed_xy_mps=float(np.linalg.norm(velocity[3:5])),
                yaw_rate_rps=float(velocity[2]),
                box_speed_mps=float(np.linalg.norm(sim.data.qvel[sim.bv : sim.bv + 3])),
                box_xy_displacement_m=float(np.linalg.norm(sim.data.qpos[sim.bq : sim.bq + 2] - sim.box_xy)),
            )
            record.update(training_diagnostics(sim, record))
            if record["training_fell_hip"] and not sim.stop_reason:
                sim.stop("training_fell_hip")
                record["stop_reason"] = sim.stop_reason
            records.append(record)
            if sim.steps % 5 == 0 or sim.stop_reason:
                picture = frame(renderer, sim, camera, mode, record)
                writer.append_data(picture)
                if sample_times and sim.data.time + 1e-8 >= sample_times[0]:
                    snapshots.append((sim.data.time, picture))
                    sample_times.pop(0)
        final = sim.metrics()
        picture = frame(renderer, sim, camera, mode, final)
        snapshots.append((sim.data.time, picture))
        writer.append_data(picture)
    finally:
        sim.data.ctrl[:] = 0
        writer.close()
        renderer.close()
    first_pickup = first_hold(records, "training_pickup_valid", 1.0)
    ground_events = []
    for record in records:
        if first_pickup is None or record["time_s"] < first_pickup:
            continue
        if record["box_bottom_m"] < 0.05:
            if not ground_events or record["time_s"] - ground_events[-1][1] > 0.1:
                ground_events.append([record["time_s"], record["time_s"]])
            else:
                ground_events[-1][1] = record["time_s"]
    result = dict(
        mode=mode,
        requested_duration_s=DURATION,
        actual_duration_s=float(sim.data.time),
        end_reason=sim.stop_reason or "duration",
        runtime_error=failure,
        checkpoint_sha256=sim.cfg["checkpoint_sha256"],
        control_dt=sim.dt,
        physics_dt=sim.model.opt.timestep,
        box_xy=sim.box_xy.tolist(),
        effort_limits=sim.effort.tolist(),
        first_pickup_s=next((r["time_s"] for r in records if r["pickup_1s"]), None),
        first_strict_hold_s=next((r["time_s"] for r in records if r["strict_hold_2s"]), None),
        longest_pickup_valid_s=longest_run(records, "current_pickup_valid"),
        longest_strict_valid_s=longest_run(records, "current_strict_valid"),
        training_first_pickup_s=first_pickup,
        training_first_strict_hold_s=first_hold(records, "training_strict_valid", 2.0),
        training_longest_pickup_valid_s=longest_run(records, "training_pickup_valid"),
        training_longest_strict_valid_s=longest_run(records, "training_strict_valid"),
        strict_metric_disagreement_steps=sum(r["current_strict_valid"] != r["training_strict_valid"] for r in records),
        pickup_metric_disagreement_steps=sum(r["current_pickup_valid"] != r["training_pickup_valid"] for r in records),
        post_pickup_ground_intervals_s=ground_events,
        final=records[-1] if records else final,
        inference_ms=dict(zip(("p50", "p95", "max"), np.percentile(timing, [50, 95, 100]) * 1000)),
        clipped_steps=sum(c > 0 for c in clip_counts),
        wall_time_s=time.monotonic() - started,
        trajectory=records,
        limitations=[
            "One nominal deterministic scene; no hardware or success-rate claim",
            "No real-camera noise, latency, extrinsic error or stand-to-carrybox dynamics",
            "target_clipped uses the real 50Hz target clip helper but retains MuJoCo 200Hz PD and hard torque limits",
            "training diagnostics use net normal hand contact vectors, link-local pelvis yaw, link-origin speed and hip_yaw links; contact dynamics still differ by simulator",
        ],
    )
    (OUT / f"{mode}.json").write_text(json.dumps(result, indent=2) + "\n")
    figure, axes = plt.subplots(2, 4, figsize=(16, 7))
    for ax, (t, picture) in zip(axes.flat, snapshots[:7] + snapshots[-1:]):
        ax.imshow(picture)
        ax.set_title(f"{t:.2f} s")
    for ax in axes.flat:
        ax.axis("off")
    figure.tight_layout()
    figure.savefig(OUT / f"{mode}_frames.png", dpi=130)
    plt.close(figure)
    if ground_events:
        reader = imageio.get_reader(OUT / f"{mode}.mp4")
        figure, axes = plt.subplots(len(ground_events), 4, figsize=(16, 3.5 * len(ground_events)), squeeze=False)
        for row, (start, end) in zip(axes, ground_events):
            for ax, t in zip(row, (start - 0.4, start + 0.4, end, end + 1.0)):
                ax.imshow(reader.get_data(round(min(sim.data.time, t) * 10)))
                ax.set_title(f"{t:.2f} s")
                ax.axis("off")
        reader.close()
        figure.tight_layout()
        figure.savefig(OUT / f"{mode}_drops.png", dpi=130)
        plt.close(figure)
    print(json.dumps({k: v for k, v in result.items() if k not in ("trajectory", "effort_limits")}), flush=True)
    return result


def main():
    results = [evaluate(mode) for mode in ("baseline", "deployment_limits", "target_clipped")]
    figure, axes = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    for result in results:
        rows = result["trajectory"]
        t = [r["time_s"] for r in rows]
        for ax, field in zip(axes, ("box_bottom_m", "training_root_speed_xy_mps", "box_speed_mps")):
            ax.plot(t, [r[field] for r in rows], label=result["mode"], linewidth=1)
    for ax, label in zip(axes, ("Box bottom clearance (m)", "Pelvis link planar speed (m/s)", "Box speed (m/s)")):
        ax.set_ylabel(label)
        ax.grid(alpha=0.3)
        ax.legend()
    axes[0].axhline(0.1, color="gray", linestyle="--")
    for ax in axes[1:]:
        ax.axhline(0.15, color="gray", linestyle="--")
    axes[-1].set_xlabel("Simulation time (s)")
    figure.tight_layout()
    figure.savefig(OUT / "comparison.png", dpi=150)
    plt.close(figure)
    (OUT / "summary.json").write_text(
        json.dumps([{k: v for k, v in r.items() if k != "trajectory"} for r in results], indent=2) + "\n"
    )
    if any(r["runtime_error"] for r in results):
        raise SystemExit("A rollout encountered a runtime error; inspect the saved record")


if __name__ == "__main__":
    main()
