"""Exercise native Tk/MuJoCo windows, input history and lifecycle under Xvfb."""

import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import mujoco.viewer
import numpy as np
from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts import g1_carrybox_s2s as entry

OUT = Path(__file__).resolve().parent


def gui_case(mode):
    sims, windows, viewers = [], [], []
    updates = 0
    original_sim, original_launch = entry.CarryBoxSim, mujoco.viewer.launch_passive

    def make_sim(*args, **kwargs):
        sim = original_sim(*args, **kwargs)
        sims.append(sim)
        return sim

    def launch(*args, **kwargs):
        viewer = original_launch(*args, **kwargs)
        viewers.append(viewer)
        return viewer

    class ObservedWindow(entry.DepthWindow):
        def __init__(self, on_key):
            assert mode != "disabled", "--no-depth-view created a depth window"
            super().__init__(on_key)
            self.root.geometry("+0+0")
            windows.append(self)

        def update(self, sim):
            nonlocal updates
            updates += 1
            policy = sim.agent.policy
            history = policy.depth_history.copy()
            qpos, qvel, previous = sim.data.qpos.copy(), sim.data.qvel.copy(), policy.previous_action.copy()
            last_time = policy.last_time
            if mode == "controls":
                if updates == 10:
                    self.root.focus_force()
                    self.root.update()
                    self.root.event_generate("<KeyPress-space>")
                elif updates == 11:
                    assert sim.steps == 10 and sim.stop_reason == "user_stop"
                    self.root.event_generate("<KeyPress-r>")
                elif updates == 12:
                    assert sim.steps == 1 and sim.stop_reason is None and last_time == 0
                    np.testing.assert_array_equal(history, np.repeat(history[-1:], 4, axis=0))
            running = super().update(sim)
            np.testing.assert_array_equal(policy.depth_history, history)
            np.testing.assert_array_equal(policy.previous_action, previous)
            np.testing.assert_array_equal(sim.data.qpos, qpos)
            np.testing.assert_array_equal(sim.data.qvel, qvel)
            assert policy.last_time == last_time
            assert self.status.cget("text").startswith(f"Input t = {last_time:.2f} s")
            assert len(self.panels) == 4 and all(
                p.image.width() == 384 and p.image.height() == 216 for p in self.panels
            )
            for panel, depth in zip(self.panels, history):
                row, col = np.unravel_index(np.argmin(depth), depth.shape)
                expected = int(round(float(np.clip((depth[row, col] - 0.1) / 2.9, 0, 1) * 255)))
                assert panel.image.get(col * 8, row * 8) == (expected,) * 3
            if mode == "controls" and updates == 20:
                assert not np.array_equal(history[0], history[-1]), "History did not advance after reset"
                self.root.lift()
                self.root.update()
                x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
                ImageGrab.grab(bbox=(x, y, x + self.root.winfo_width(), y + self.root.winfo_height())).save(
                    OUT / "depth_window.png"
                )
                np.save(OUT / "displayed_history.npy", history)
            if mode == "controls" and updates == 25:
                self.root.tk.call(self.root.protocol("WM_DELETE_WINDOW"))
                return False
            if mode == "viewer_closed" and updates == 8:
                viewers[-1].close()
            return running

    args = [str(ROOT / "scripts/g1_carrybox_s2s.py"), "--duration", "0.2" if mode == "disabled" else "2"]
    if mode == "disabled":
        args.append("--no-depth-view")
    output = io.StringIO()
    with (
        patch.object(entry, "CarryBoxSim", make_sim),
        patch.object(entry, "DepthWindow", ObservedWindow),
        patch.object(mujoco.viewer, "launch_passive", launch),
        patch.object(sys, "argv", args),
        contextlib.redirect_stdout(output),
    ):
        entry.main()
    assert len(sims) == 1 and len(viewers) == 1 and not viewers[0].is_running()
    assert all(window.closed for window in windows)
    np.testing.assert_array_equal(sims[0].data.ctrl, 0)
    result = json.loads(output.getvalue())
    expected = {"controls": "depth_window_closed", "viewer_closed": "viewer_closed", "disabled": "duration"}[mode]
    assert result["run_end_reason"] == expected, result
    result.update(case=mode, depth_updates=updates)
    return result


def main():
    results = []
    for mode in ("controls", "viewer_closed", "disabled"):
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), mode],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        results.append(json.loads(completed.stdout))
    code = (
        "import runpy,sys; "
        "sys.argv=['scripts/g1_carrybox_s2s.py','--headless','--duration','0.2']; "
        "runpy.run_path(sys.argv[0],run_name='__main__'); "
        "assert 'tkinter' not in sys.modules"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env={**os.environ, "DISPLAY": "", "MUJOCO_GL": "egl"},
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    result = json.loads(completed.stdout)
    assert result["run_end_reason"] == "duration"
    result.update(case="headless_without_display", tkinter_loaded=False)
    results.append(result)
    (OUT / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps([dict(case=r["case"], end=r["run_end_reason"]) for r in results]))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(json.dumps(gui_case(sys.argv[1])))
    else:
        main()
