"""Run the onboard Wall19 agent in MuJoCo. Space/Esc stops, R resets."""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from instinct_onboard.simulation.carrybox import CarryBoxSim


class DepthWindow:
    """Show the four depth frames actually consumed by the latest policy step."""

    def __init__(self, on_key):
        import tkinter as tk

        self.tk = tk
        self.root = tk.Tk()
        self.root.title("G1 carrybox - policy depth input")
        self.root.resizable(False, False)
        self.closed = False
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        for key, code in (("space", 32), ("Escape", 256), ("r", 82), ("R", 82), ("BackSpace", 259)):
            self.root.bind(f"<{key}>", lambda event, code=code: on_key(code))
        self.status = tk.Label(self.root, text="Waiting for the first policy input", anchor="w")
        self.status.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=4)
        self.panels = []
        for index, title in enumerate(("History 1 (oldest)", "History 2", "History 3", "History 4 (latest)")):
            row, column = divmod(index, 2)
            tk.Label(self.root, text=title).grid(row=1 + row * 2, column=column)
            panel = tk.Label(self.root)
            panel.grid(row=2 + row * 2, column=column, padx=4, pady=2)
            self.panels.append(panel)
        tk.Label(self.root, text="Optical depth: black = 0.1 m, white = 3.0 m | 27 x 48 pixels per frame").grid(
            row=5, column=0, columnspan=2, pady=4
        )
        tk.Label(self.root, text="Space / Esc: stop | R / Backspace: reset | Close either window: exit").grid(
            row=6, column=0, columnspan=2, pady=4
        )

    def update(self, sim):
        if self.closed:
            return False
        policy = sim.agent.policy
        if policy.depth_history is not None:
            for panel, depth in zip(self.panels, policy.depth_history):
                gray = np.rint(np.clip((depth - 0.1) / 2.9, 0, 1) * 255).astype(np.uint8)
                rgb = np.repeat(gray[:, :, None], 3, axis=2)
                picture = self.tk.PhotoImage(data=b"P6\n48 27\n255\n" + rgb.tobytes(), format="PPM").zoom(8)
                panel.configure(image=picture)
                panel.image = picture
            latest = policy.depth_history[-1]
            self.status.configure(
                text=f"Input t = {policy.last_time:.2f} s | latest min/max = {latest.min():.2f}/{latest.max():.2f} m"
                f" | {sim.stop_reason or 'running'}"
            )
        self.root.update()
        return not self.closed

    def close(self):
        if not self.closed:
            self.closed = True
            self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=Path("models/carrybox_wall19"))
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--no-depth-view", action="store_true", help="Show only the MuJoCo window")
    parser.add_argument("--duration", type=float, default=20.0)
    parser.add_argument("--box-xy", type=float, nargs=2, default=(1.0, 0.0))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 0 < args.duration < float("inf"):
        parser.error("--duration must be positive and finite")
    sim = CarryBoxSim(args.bundle, args.box_xy)
    records, pending = [], []
    viewer = None
    depth_window = None
    started = time.monotonic()
    try:
        if not args.headless:
            import mujoco.viewer

            if not args.no_depth_view:
                depth_window = DepthWindow(pending.append)
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
                if depth_window is not None and not depth_window.update(sim):
                    sim.stop("depth_window_closed")
                    break
                time.sleep(max(0.0, sim.dt - (time.monotonic() - tick)))
    except KeyboardInterrupt:
        sim.stop("keyboard_interrupt")
    finally:
        sim.data.ctrl[:] = 0
        if viewer is not None:
            viewer.close()
        if depth_window is not None:
            depth_window.close()
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
