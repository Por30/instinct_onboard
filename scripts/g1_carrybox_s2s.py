"""Run G1 modes in MuJoCo: S stand, A carrybox, Space/Esc/B stop, R reset."""

import argparse
import contextlib
import json
import sys
import time
from pathlib import Path

import mujoco
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from instinct_onboard.robot_cfgs import G1_29Dof_TorsoBase
from instinct_onboard.simulation.carrybox import OBJECT_SHAPES, CarryBoxSim
from instinct_onboard.simulation.stand import StandPolicy
from instinct_onboard.target_joint_state import TargetJointState


class ModeController:
    def __init__(self, sim, standdir, start_mode="cold_start", startup_step_size=0.2, kpkd_factor=2.0):
        self.sim = sim
        self.stand = StandPolicy(standdir)
        self.to_stand = np.array([sim.sim_joint_names.index(n) for n in self.stand.joint_names])
        self.to_carry = np.argsort(self.to_stand)
        self.signs = G1_29Dof_TorsoBase.joint_signs
        self.torso = sim.model.body("torso_link").id
        self.startup_step_size, self.kpkd_factor = startup_step_size, kpkd_factor
        sim.effort = np.minimum(sim.effort, G1_29Dof_TorsoBase.torque_limits[self.to_carry])
        self.phase = start_mode
        self.last_target = None
        self.message = "S: stand when ready; A: carrybox from stand"

    @property
    def cold_ready(self):
        return bool(
            np.all(abs(self.sim.data.qpos[self.sim.qadr] - self.sim.agent.default_joint_pos) <= self.startup_step_size)
        )

    def reset(self):
        self.sim.reset()
        self.stand.reset()
        self.phase = "cold_start"
        self.last_target = None
        self.message = "Reset: cold_start with simulated support"

    def request(self, phase):
        if self.sim.stop_reason:
            self.message = "Stopped: press R to reset"
            return
        if phase == "stand" and (
            self.phase == "carrybox"
            or (self.phase == "cold_start" and self.last_target is not None and self.cold_ready)
        ):
            self.stand.reset()
        elif phase == "carrybox" and self.phase == "stand":
            self.sim.agent.reset()
        else:
            self.message = "S requires cold-start pose ready; A requires stand"
            return
        self.phase = phase
        self.sim.data.xfrc_applied[:] = 0
        self.message = f"Entered {phase}; simulated support OFF"

    def stand_target(self):
        sim = self.sim
        q = (sim.data.qpos[sim.qadr][self.to_stand] * self.signs).astype(np.float32)
        dq = (sim.data.qvel[sim.vadr][self.to_stand] * self.signs).astype(np.float32)
        velocity = np.empty(6)
        mujoco.mj_objectVelocity(sim.model, sim.data, mujoco.mjtObj.mjOBJ_BODY, self.torso, velocity, 0)
        rotation = sim.data.xmat[self.torso].reshape(3, 3)
        # mjOBJ_BODY's local frame is the inertia frame, not the torso IMU/link frame.
        gyro = rotation.T @ velocity[:3]
        gravity = rotation.T @ [0, 0, -1]
        previous = None
        if self.last_target is not None:
            previous = TargetJointState(
                **{
                    field: (
                        getattr(self.last_target, field)[self.to_stand]
                        * (self.signs if field in ("position", "velocity", "effort") else 1)
                    )
                    for field in ("position", "velocity", "effort", "kp", "kd")
                }
            )
        target = self.stand.act(q, dq, gyro, gravity, previous)
        return TargetJointState(
            **{
                field: (getattr(target, field) * (self.signs if field in ("position", "velocity", "effort") else 1))[
                    self.to_carry
                ]
                for field in ("position", "velocity", "effort", "kp", "kd")
            }
        )

    def step(self, external_force=None):
        sim = self.sim
        if sim.stop_reason:
            raise RuntimeError(f"Simulation stopped: {sim.stop_reason}; R reset required")
        try:
            if self.phase == "cold_start":
                q = sim.data.qpos[sim.qadr]
                position = q + np.clip(sim.agent.default_joint_pos - q, -self.startup_step_size, self.startup_step_size)
                target = TargetJointState(
                    position,
                    np.zeros(29),
                    np.zeros(29),
                    sim.agent.p_gains * self.kpkd_factor,
                    sim.agent.d_gains * self.kpkd_factor,
                )
            elif self.phase == "stand":
                target = self.stand_target()
            elif self.phase == "carrybox":
                target = sim.agent.act(*sim.observations(), sim.data.time, sim.data.time)
            else:
                raise RuntimeError(f"Unknown simulation phase: {self.phase}")
            record = sim.step(external_force, target=target, support_root=self.phase == "cold_start")
            self.last_target = target.copy()
            return dict(record, phase=self.phase, simulated_support=self.phase == "cold_start")
        except Exception:
            sim.stop("runtime_fault")
            raise


class DepthWindow:
    """Show carrybox input history, or an unused camera preview in cold_start/stand."""

    def __init__(self, on_key):
        import tkinter as tk

        self.tk = tk
        self.root = tk.Tk()
        self.root.title("G1 carrybox - policy depth input")
        self.root.resizable(False, False)
        self.closed = False
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        for key, code in (
            ("space", 32),
            ("Escape", 256),
            ("r", 82),
            ("R", 82),
            ("BackSpace", 259),
            ("s", 83),
            ("S", 83),
            ("a", 65),
            ("A", 65),
            ("b", 66),
            ("B", 66),
        ):
            self.root.bind(f"<{key}>", lambda event, code=code: on_key(code))
        for key in "123456":
            self.root.bind(f"<KeyPress-{key}>", lambda event, code=ord(key): on_key(code))
        self.status = tk.Label(self.root, text="Waiting for the first policy input", anchor="w")
        self.status.grid(row=0, column=0, columnspan=2, sticky="ew", padx=8, pady=4)
        self.panels, self.titles = [], []
        for index, title in enumerate(("History 1 (oldest)", "History 2", "History 3", "History 4 (latest)")):
            row, column = divmod(index, 2)
            label = tk.Label(self.root, text=title)
            label.grid(row=1 + row * 2, column=column)
            self.titles.append(label)
            panel = tk.Label(self.root)
            panel.grid(row=2 + row * 2, column=column, padx=4, pady=2)
            self.panels.append(panel)
        tk.Label(self.root, text="Optical depth: black = 0.1 m, white = 3.0 m | 27 x 48 pixels per frame").grid(
            row=5, column=0, columnspan=2, pady=4
        )
        tk.Label(self.root, text="S: stand | A: carrybox | Space / Esc / B: stop | R: cold_start | Close: exit").grid(
            row=6, column=0, columnspan=2, pady=4
        )
        tk.Label(self.root, text="1 cuboid | 2 cube | 3 sphere | 4 cylinder | 5 capsule | 6 ellipsoid").grid(
            row=7, column=0, columnspan=2, pady=4
        )

    def update(self, sim, controller=None):
        if self.closed:
            return False
        policy = sim.agent.policy
        phase = controller.phase if controller is not None else "carrybox"
        if phase == "carrybox" and policy.depth_history is not None:
            for title, text in zip(self.titles, ("History 1 (oldest)", "History 2", "History 3", "History 4 (latest)")):
                title.configure(text=text)
            for panel, depth in zip(self.panels, policy.depth_history):
                gray = np.rint(np.clip((depth - 0.1) / 2.9, 0, 1) * 255).astype(np.uint8)
                rgb = np.repeat(gray[:, :, None], 3, axis=2)
                picture = self.tk.PhotoImage(data=b"P6\n48 27\n255\n" + rgb.tobytes(), format="PPM").zoom(8)
                panel.configure(image=picture)
                panel.image = picture
            latest = policy.depth_history[-1]
            self.status.configure(
                text=f"Input t = {policy.last_time:.2f} s | latest min/max = {latest.min():.2f}/{latest.max():.2f} m"
                f" | {phase} | {sim.object_shape} | {sim.stop_reason or 'running'}"
            )
        else:
            depth = sim.camera.render(sim.data)
            gray = np.rint(np.clip((depth - 0.1) / 2.9, 0, 1) * 255).astype(np.uint8)
            rgb = np.repeat(gray[:, :, None], 3, axis=2)
            picture = self.tk.PhotoImage(data=b"P6\n48 27\n255\n" + rgb.tobytes(), format="PPM").zoom(8)
            self.panels[0].configure(image=picture)
            self.panels[0].image = picture
            self.titles[0].configure(text="Live camera preview (not consumed by policy)")
            for title, panel in zip(self.titles[1:], self.panels[1:]):
                title.configure(text="")
                panel.configure(image="")
            support = "ON" if phase == "cold_start" else "OFF"
            detail = "stand input: 8 x 18 x 32 zeros" if phase == "stand" else f"pose ready: {controller.cold_ready}"
            self.status.configure(
                text=f"{phase} | support {support} | {detail} | {sim.stop_reason or sim.object_shape}"
            )
        if controller is not None:
            self.root.title(f"G1 {phase} - {controller.message}")
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
    parser.add_argument("--object-shape", choices=OBJECT_SHAPES, default="cuboid")
    parser.add_argument("--standdir", type=Path, default=Path("models/stand_onboard"))
    parser.add_argument("--start-mode", choices=("cold_start", "stand", "carrybox"), default="cold_start")
    parser.add_argument("--startup_step_size", type=float, default=0.2)
    parser.add_argument("--kpkd_factor", type=float, default=2.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 0 < args.duration < float("inf"):
        parser.error("--duration must be positive and finite")
    if (
        not np.isfinite([args.startup_step_size, args.kpkd_factor]).all()
        or min(args.startup_step_size, args.kpkd_factor) <= 0
    ):
        parser.error("Cold-start step size and gain factor must be positive and finite")
    sim = CarryBoxSim(args.bundle, args.box_xy)
    if args.object_shape != "cuboid":
        sim.set_object_shape(args.object_shape)
    initial_mode = "cold_start" if args.start_mode == "stand" else args.start_mode
    controller = ModeController(sim, args.standdir, initial_mode, args.startup_step_size, args.kpkd_factor)
    records, pending = [], []
    viewer = None
    depth_window = None
    last_overlay = None
    started = time.monotonic()
    try:
        if args.start_mode == "stand":
            # Execute cold_start once so stand sees an accepted target in its action history.
            records.append(controller.step())
            controller.request("stand")
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
            keys = []
            while pending:
                keys.append(pending.pop(0))
            if any(key in (32, 256, 66) for key in keys):
                keys = [66]
            elif any(key in (82, 259) for key in keys):
                keys = [82]
            elif 83 in keys:
                keys = [83]
            for key in keys:
                if key not in (32, 256, 66, 82, 259, 83, 65, 49, 50, 51, 52, 53, 54):
                    continue
                if sim.stop_reason and key not in (82, 259):
                    controller.message = "Stopped: press R to reset"
                    continue
                with viewer.lock() if viewer is not None else contextlib.nullcontext():
                    if viewer is not None:
                        viewer.perturb.active = 0
                        viewer.perturb.select = 0
                    sim.data.xfrc_applied[:] = 0
                    if key in (32, 256, 66):
                        sim.stop()
                        controller.message = "Stopped: press R to reset"
                    elif key in (82, 259):
                        controller.reset()
                        records = []
                    elif key in (83, 65):
                        controller.request("stand" if key == 83 else "carrybox")
                    else:
                        sim.set_object_shape(tuple(OBJECT_SHAPES)[key - 49])
                        controller.reset()
                        if viewer is not None:
                            # Reserve digit keys for objects instead of native geom-group toggles.
                            viewer.opt.geomgroup[:] = (1, 1, 1, 0, 0, 0)
                        records = []
            if not sim.stop_reason:
                mouse_force = sim.data.xfrc_applied.copy() if viewer is not None else None
                records.append(controller.step(mouse_force))
            elif args.headless:
                break
            if viewer is not None:
                overlay = f"Mode: {controller.phase} | support: {'ON' if controller.phase == 'cold_start' else 'OFF'} | {sim.stop_reason or sim.object_shape}\n{controller.message}"
                if overlay != last_overlay:
                    viewer.set_texts(
                        (
                            None,
                            None,
                            overlay
                            + "\nS stand | A carrybox | Space/Esc/B stop | R cold_start\n1 cuboid | 2 cube | 3 sphere | 4 cylinder | 5 capsule | 6 ellipsoid\nDouble-click select; Ctrl + right drag object; Shift = horizontal",
                            None,
                        )
                    )
                    last_overlay = overlay
                viewer.sync()
                if sim.stop_reason:
                    sim.data.xfrc_applied[:] = 0
                if depth_window is not None and not depth_window.update(sim, controller):
                    sim.stop("depth_window_closed")
                    break
                time.sleep(max(0.0, sim.dt - (time.monotonic() - tick)))
    except KeyboardInterrupt:
        sim.stop("keyboard_interrupt")
    finally:
        sim.data.ctrl[:] = 0
        sim.data.xfrc_applied[:] = 0
        if viewer is not None:
            viewer.close()
        if depth_window is not None:
            depth_window.close()
    result = dict(
        checkpoint_sha256=sim.cfg["checkpoint_sha256"],
        object_shape=sim.object_shape,
        phase=controller.phase,
        simulated_support=controller.phase == "cold_start",
        requested_duration_s=args.duration,
        run_end_reason=sim.stop_reason or ("duration" if sim.data.time >= args.duration else "viewer_closed"),
        wall_time_s=time.monotonic() - started,
        robot_bodies=len(sim.robot_bodies),
        robot_mass_kg=float(sim.model.body_mass[sim.robot_bodies].sum()),
        summary=records[-1] if records else {"stop_reason": sim.stop_reason},
        limitations=[
            "Fixed-mass primitive object scene, no training randomization or paired RSI",
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
