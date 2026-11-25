"""Native MuJoCo/Tk key and mouse integration under an isolated Xvfb display."""

import contextlib
import ctypes
import io
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import mujoco
import mujoco.viewer
import numpy as np
from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from scripts import g1_carrybox_s2s as entry

OUT = Path(__file__).resolve().parent


class XInput:
    def __init__(self, keys):
        self.keys = keys
        self.x = ctypes.CDLL("libX11.so.6")
        self.xt = ctypes.CDLL("libXtst.so.6")
        self.x.XOpenDisplay.restype = ctypes.c_void_p
        self.x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        self.display = self.x.XOpenDisplay(None)
        assert self.display
        self.x.XStringToKeysym.argtypes = [ctypes.c_char_p]
        self.x.XStringToKeysym.restype = ctypes.c_ulong
        self.x.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.x.XKeysymToKeycode.restype = ctypes.c_uint
        self.x.XSetInputFocus.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        self.x.XRaiseWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.x.XSync.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.x.XCloseDisplay.argtypes = [ctypes.c_void_p]
        self.xt.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        self.xt.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        self.xt.XTestFakeMotionEvent.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_ulong,
        ]
        listing = subprocess.check_output(["xwininfo", "-root", "-tree"], text=True)
        match = re.search(r'(0x[0-9a-f]+) "MuJoCo', listing)
        assert match, listing
        self.window = int(match[1], 16)
        self.focus()
        info = subprocess.check_output(["xwininfo", "-id", match[1]], text=True)
        self.left = int(re.search(r"Absolute upper-left X:\s+(-?\d+)", info)[1])
        self.top = int(re.search(r"Absolute upper-left Y:\s+(-?\d+)", info)[1])
        self.height = int(re.search(r"Height:\s+(\d+)", info)[1])

    def focus(self):
        self.x.XRaiseWindow(self.display, self.window)
        self.x.XSetInputFocus(self.display, self.window, 2, 0)
        self.flush()

    def flush(self):
        self.x.XSync(self.display, 0)
        time.sleep(0.08)

    def key(self, name, down=None):
        count = len(self.keys)
        code = self.x.XKeysymToKeycode(self.display, self.x.XStringToKeysym(name.encode()))
        for pressed in (True, False) if down is None else (down,):
            self.xt.XTestFakeKeyEvent(self.display, code, pressed, 0)
        self.flush()
        if len(name) == 1 or name == "space":
            deadline = time.monotonic() + 3
            while len(self.keys) == count and time.monotonic() < deadline:
                time.sleep(0.02)
            assert len(self.keys) > count, (name, self.keys)

    def button(self, button, down):
        self.xt.XTestFakeButtonEvent(self.display, button, down, 0)
        self.flush()

    def move(self, x, y):
        self.xt.XTestFakeMotionEvent(self.display, -1, int(x), int(y), 0)
        self.flush()

    def close(self):
        self.x.XCloseDisplay(self.display)


def gui_case():
    viewers, sims = [], []
    keys = []
    observed = dict(shapes=[], native_key_shapes=[], force_peak=0.0)
    updates = 0
    inputs = None
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

    class ObservedWindow(entry.DepthWindow):
        def __init__(self, on_key):
            super().__init__(on_key)
            self.root.geometry("+800+0")

        def update(self, sim):
            nonlocal updates, inputs
            updates += 1
            running = super().update(sim)
            viewer = viewers[0]
            if updates == 1:
                inputs = XInput(keys)
                self.root.focus_force()
                self.root.update()
                self.root.event_generate("<KeyPress-1>")
            elif 2 <= updates <= 7:
                shape = tuple(entry.OBJECT_SHAPES)[updates - 2]
                assert sim.object_shape == shape and sim.steps == 1
                assert shape in self.status.cget("text")
                np.testing.assert_array_equal(
                    sim.agent.policy.depth_history, np.repeat(sim.agent.policy.depth_history[-1:], 4, axis=0)
                )
                assert viewer.perturb.active == 0
                observed["shapes"].append(shape)
                if updates < 7:
                    self.root.event_generate(f"<KeyPress-{updates}>")
                else:
                    inputs.focus()
                    inputs.key("1")
            elif 8 <= updates <= 13:
                shape = tuple(entry.OBJECT_SHAPES)[updates - 8]
                assert sim.object_shape == shape and sim.steps == 1, (updates, sim.object_shape, sim.steps)
                np.testing.assert_array_equal(viewer.opt.geomgroup, [1, 1, 1, 0, 0, 0])
                observed["native_key_shapes"].append(shape)
                if updates < 13:
                    inputs.key(str(updates - 6))
                else:
                    inputs.key("1")
            elif updates == 14:
                assert sim.object_shape == "cuboid" and sim.steps == 1
                scene = mujoco.MjvScene(sim.model, maxgeom=2000)
                mujoco.mjv_updateScene(
                    sim.model, sim.data, viewer.opt, None, viewer.cam, mujoco.mjtCatBit.mjCAT_ALL, scene
                )
                viewport = viewer.viewport
                point, geom, flex, skin = (
                    np.zeros(3),
                    np.zeros(1, np.int32),
                    np.zeros(1, np.int32),
                    np.zeros(1, np.int32),
                )
                pixels = []
                for y in np.linspace(0.1, 0.85, 100):
                    for x in np.linspace(0.1, 0.9, 100):
                        body = mujoco.mjv_select(
                            sim.model,
                            sim.data,
                            viewer.opt,
                            viewport.width / viewport.height,
                            x,
                            y,
                            scene,
                            point,
                            geom,
                            flex,
                            skin,
                        )
                        if body == sim.box:
                            pixels.append((x, y))
                assert pixels, "Object not selectable in viewport"
                x, y = np.mean(pixels, axis=0)
                selected = (
                    inputs.left + viewport.left + x * viewport.width,
                    inputs.top + inputs.height - viewport.bottom - y * viewport.height,
                )
                inputs.move(*selected)
                for _ in range(2):
                    inputs.button(1, True)
                    inputs.button(1, False)
                deadline = time.monotonic() + 2
                while viewer.perturb.select != sim.box and time.monotonic() < deadline:
                    time.sleep(0.02)
                assert viewer.perturb.select == sim.box, viewer.perturb.select
                inputs.key("Control_L", True)
                inputs.button(3, True)
                inputs.move(selected[0], selected[1] - 35)
                assert viewer.perturb.active, "Native Ctrl/right drag did not activate perturbation"
                observed["drag_initial_z"] = float(sim.data.qpos[sim.bq + 2])
            elif 15 <= updates <= 19:
                observed["force_peak"] = max(
                    observed["force_peak"], float(np.linalg.norm(sim.data.xfrc_applied[sim.box]))
                )
                if updates == 19:
                    assert observed["force_peak"] > 1
                    observed["drag_final_z"] = float(sim.data.qpos[sim.bq + 2])
                    assert observed["drag_final_z"] > observed["drag_initial_z"] + 0.005, observed
                    inputs.button(3, False)
                    inputs.key("Control_L", False)
                    inputs.key("space")
            elif updates == 20:
                assert sim.stop_reason == "user_stop"
                np.testing.assert_array_equal(sim.data.ctrl, 0)
                np.testing.assert_array_equal(sim.data.xfrc_applied, 0)
                assert viewer.perturb.active == 0
                inputs.key("r")
            elif updates == 21:
                assert sim.steps == 1 and sim.stop_reason is None
                assert viewer.perturb.active == 0
                np.testing.assert_array_equal(sim.data.xfrc_applied, 0)
                self.root.lift()
                self.root.update()
                ImageGrab.grab().save(OUT / "windows.png")
                self.close()
                return False
            return running

    output = io.StringIO()
    try:
        with patch.object(entry, "CarryBoxSim", make_sim), patch.object(
            entry, "DepthWindow", ObservedWindow
        ), patch.object(mujoco.viewer, "launch_passive", launch), patch.object(
            sys, "argv", ["s2s", "--duration", "4"]
        ), contextlib.redirect_stdout(
            output
        ):
            entry.main()
    finally:
        if inputs is not None:
            inputs.close()
    assert not viewers[0].is_running()
    np.testing.assert_array_equal(sims[0].data.xfrc_applied, 0)
    np.testing.assert_array_equal(sims[0].data.ctrl, 0)
    observed["result"] = json.loads(output.getvalue())
    assert observed["result"]["run_end_reason"] == "depth_window_closed"
    return observed


def main():
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "gui"], cwd=ROOT, capture_output=True, text=True, timeout=60
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    results = {"gui": json.loads(completed.stdout)}
    for shape in entry.OBJECT_SHAPES:
        completed = subprocess.run(
            [sys.executable, "scripts/g1_carrybox_s2s.py", "--headless", "--object-shape", shape, "--duration", ".1"],
            cwd=ROOT,
            env={**os.environ, "DISPLAY": "", "MUJOCO_GL": "egl"},
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert completed.returncode == 0, completed.stderr
        result = json.loads(completed.stdout)
        assert result["object_shape"] == shape and result["run_end_reason"] == "duration"
        results[shape] = result
    (OUT / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    print(
        json.dumps(
            {
                "native_drag_force_N": results["gui"]["force_peak"],
                "tk_shapes": results["gui"]["shapes"],
                "mujoco_shapes": results["gui"]["native_key_shapes"],
                "headless_shapes": 6,
            }
        )
    )


if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(json.dumps(gui_case()))
    else:
        main()
