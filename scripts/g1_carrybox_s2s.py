"""Run the onboard Wall19 agent in MuJoCo. Space/Esc stops, R resets."""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from instinct_onboard.simulation.carrybox import CarryBoxSim


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=Path("models/carrybox_wall19"))
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--duration", type=float, default=20.0)
    parser.add_argument("--box-xy", type=float, nargs=2, default=(1.0, 0.0))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 0 < args.duration < float("inf"):
        parser.error("--duration must be positive and finite")
    sim = CarryBoxSim(args.bundle, args.box_xy)
    records, pending = [], []
    viewer = None
    started = time.monotonic()
    try:
        if not args.headless:
            import mujoco.viewer

            viewer = mujoco.viewer.launch_passive(sim.model, sim.data, key_callback=pending.append)
            viewer.cam.distance = 3.0
            viewer.cam.azimuth = 135
            viewer.cam.elevation = -15
            viewer.cam.lookat[:] = [0.6, 0, 0.7]
        while sim.data.time < args.duration and (viewer is None or viewer.is_running()):
            tick = time.monotonic()
            while pending:
                key = pending.pop(0)
                if key in (32, 256):
                    sim.stop()
                elif key in (82, 259):
                    sim.reset()
                    records = []
            if not sim.stop_reason:
                records.append(sim.step())
            elif args.headless:
                break
            if viewer is not None:
                viewer.sync()
                time.sleep(max(0.0, sim.dt - (time.monotonic() - tick)))
    except KeyboardInterrupt:
        sim.stop("keyboard_interrupt")
    finally:
        sim.data.ctrl[:] = 0
        if viewer is not None:
            viewer.close()
    result = dict(
        checkpoint_sha256=sim.cfg["checkpoint_sha256"],
        requested_duration_s=args.duration,
        run_end_reason=sim.stop_reason or ("duration" if sim.data.time >= args.duration else "viewer_closed"),
        wall_time_s=time.monotonic() - started,
        robot_bodies=len(sim.robot_bodies),
        robot_mass_kg=float(sim.model.body_mass[sim.robot_bodies].sum()),
        summary=records[-1] if records else {"stop_reason": sim.stop_reason},
        limitations=[
            "Nominal cuboid scene, no training randomization or paired RSI",
            "MuJoCo/PhysX contact and friction differ; no hardware validation",
        ],
        trajectory=records[::50] + records[-1:],
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "trajectory"}, indent=2))


if __name__ == "__main__":
    main()
