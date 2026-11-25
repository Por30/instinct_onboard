"""Exercise S/A modes through native Tk and MuJoCo keyboard events."""

import contextlib
import importlib.util
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
spec = importlib.util.spec_from_file_location(
    "xinput_helper", ROOT / "agent/receipts/carrybox-interaction-20261125/smoke.py"
)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


def gui_case(close_from):
    viewers, sims, keys, records = [], [], [], []
    inputs = None
    updates = 0
    original_sim, original_launch = entry.CarryBoxSim, mujoco.viewer.launch_passive

    def make_sim(*args, **kwargs):
        sim = original_sim(*args, **kwargs)
        sims.append(sim)
        return sim

    def launch(*args, **kwargs):
        callback = kwargs["key_callback"]

        def on_key(key):
            callback(key)
            keys.append(key)

        kwargs["key_callback"] = on_key
        viewer = original_launch(*args, **kwargs)
        viewers.append(viewer)
        return viewer

    class Window(entry.DepthWindow):
        def update(self, sim, controller=None):
            nonlocal inputs, updates
            updates += 1
            running = super().update(sim, controller)
            phase = controller.phase
            records.append(
                dict(update=updates, phase=phase, steps=sim.steps, stop=sim.stop_reason, support=phase == "cold_start")
            )
            assert phase in self.status.cget("text"), self.status.cget("text")
            if updates == 1:
                inputs = helper.XInput(keys)
                self.root.focus_force()
                self.root.update()
                self.root.event_generate("<KeyPress-a>")
            elif updates == 2:
                assert phase == "cold_start"
                self.root.event_generate("<KeyPress-s>")
            elif updates == 3:
                assert phase == "stand" and sim.agent.policy.depth_history is None
                assert "zeros" in self.status.cget("text")
                self.root.event_generate("<KeyPress-a>")
            elif updates == 4:
                assert phase == "carrybox" and sim.agent.policy.depth_history is not None
                self.root.event_generate("<KeyPress-s>")
            elif updates == 5:
                assert phase == "stand" and "not consumed" in self.titles[0].cget("text")
                inputs.focus()
                inputs.key("a")
            elif updates == 6:
                assert phase == "carrybox"
                inputs.key("s")
            elif updates == 7:
                assert phase == "stand"
                inputs.key("b")
            elif updates == 8:
                assert sim.stop_reason == "user_stop"
                np.testing.assert_array_equal(sim.data.ctrl, 0)
                np.testing.assert_array_equal(sim.data.xfrc_applied, 0)
                inputs.key("a")
                inputs.key("3")
            elif updates == 9:
                assert sim.stop_reason == "user_stop" and phase == "stand" and sim.object_shape == "cuboid"
                assert sim.steps == records[-2]["steps"]
                inputs.key("r")
            elif updates == 10:
                assert phase == "cold_start" and sim.stop_reason is None and sim.steps == 1
                inputs.key("s")
                inputs.key("a")
                inputs.key("b")
            elif updates == 11:
                assert phase == "cold_start" and sim.stop_reason == "user_stop", "E-stop must win the key batch"
                inputs.key("r")
            elif updates == 12:
                assert phase == "cold_start" and sim.stop_reason is None
                inputs.key("3")
            elif updates == 13:
                assert phase == "cold_start" and sim.object_shape == "sphere" and sim.steps == 1
                self.root.lift()
                self.root.update()
                if close_from == "depth":
                    ImageGrab.grab().save(OUT / "modes.png")
                    self.close()
                    return False
                viewers[0].close()
            return running

    output = io.StringIO()
    try:
        with patch.object(entry, "CarryBoxSim", make_sim), patch.object(entry, "DepthWindow", Window), patch.object(
            mujoco.viewer, "launch_passive", launch
        ), patch.object(sys, "argv", ["s2s", "--duration", "5"]), contextlib.redirect_stdout(output):
            entry.main()
    finally:
        if inputs is not None:
            inputs.close()
    result = json.loads(output.getvalue())
    assert result["run_end_reason"] == ("depth_window_closed" if close_from == "depth" else "viewer_closed")
    np.testing.assert_array_equal(sims[0].data.ctrl, 0)
    np.testing.assert_array_equal(sims[0].data.xfrc_applied, 0)
    assert not viewers[0].is_running()
    return dict(result=result, transitions=records, native_keys=keys)


def main():
    results = {}
    for source in ("depth", "viewer"):
        completed = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), source],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=45,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        results[source] = json.loads(completed.stdout)
        (OUT / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    for mode, duration in [("cold_start", 1), ("stand", 10), ("carrybox", 0.2)]:
        code = (
            "import runpy,sys; sys.argv="
            + repr(["scripts/g1_carrybox_s2s.py", "--headless", "--start-mode", mode, "--duration", str(duration)])
            + "; runpy.run_path(sys.argv[0],run_name='__main__'); assert 'tkinter' not in sys.modules"
        )
        completed = subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env={**os.environ, "DISPLAY": "", "MUJOCO_GL": "egl"},
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stdout + completed.stderr
        result = json.loads(completed.stdout)
        results["headless_" + mode] = result
        (OUT / "results.json").write_text(json.dumps(results, indent=2) + "\n")
        assert result["phase"] == mode and result["run_end_reason"] == "duration", result
        assert result["simulated_support"] == (mode == "cold_start")
    (OUT / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                gui_modes=True,
                estop_latched=True,
                headless_modes=3,
                free_stand_s=results["headless_stand"]["summary"]["time_s"] - 0.02,
            )
        )
    )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(json.dumps(gui_case(sys.argv[1])))
    else:
        main()
