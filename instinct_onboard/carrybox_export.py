"""Export the user-specified Wall19 checkpoint without launching Isaac Sim."""

from __future__ import annotations

import ast
import json
import math
import re
import shutil
import xml.etree.ElementTree as ET
from collections import deque
from pathlib import Path

import numpy as np
import torch
import yaml
from torch import nn
from torch.nn import functional as F

from instinct_onboard.carrybox_policy import sha256

DEFAULT_CHECKPOINT = Path(
    "/home/cao/perceptual_ball/logs/rsl_rl/g1_carrybox_depth/walled19/"
    "2026-11-07_17-31-48_wall19_still_hold_fresh30k_20261107_173148/"
    "05_stage5_from15000/model_29999.pt"
)
DEFAULT_SOURCE = Path("/home/cao/perceptual_ball/source/perceptual_ball/perceptual_ball")
DEFAULT_URDF = Path("/home/cao/PhysHSI/legged_gym/resources/robots/g1/urdf/g1_29dof.urdf")
DEFAULT_PROFILE = Path("/home/cao/unitree_rl_lab_carrybox/docs/sim2sim_wall19/isaac_profile.json")


class ConfigLoader(yaml.SafeLoader):
    pass


ConfigLoader.add_constructor("tag:yaml.org,2002:python/tuple", ConfigLoader.construct_sequence)
ConfigLoader.add_constructor("tag:yaml.org,2002:python/object/apply:builtins.slice", ConfigLoader.construct_sequence)


def source_classes(path, names):
    """Reuse only the named inference classes, without importing simulator registration."""
    tree = ast.parse(Path(path).read_text())
    definitions = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name in names]
    if {node.name for node in definitions} != set(names):
        raise ValueError(f"Missing inference classes in {path}")
    namespace = {"torch": torch, "nn": nn, "F": F, "math": math, "_ACTIVATIONS": {"elu": nn.ELU, "relu": nn.ReLU}}
    exec(compile(ast.Module(body=definitions, type_ignores=[]), str(path), "exec"), namespace)
    return [namespace[name] for name in names]


class CarryBoxActor(nn.Module):
    def __init__(self, source):
        super().__init__()
        (encoder,) = source_classes(source / "rsl_rl_extensions/modules.py", ["DepthCNNEncoder"])
        geometry, grasp = source_classes(source / "carrybox_wall14.py", ["GeometryHead", "GraspHead"])
        self.perception_encoder = encoder(4, 27, 48)
        self.pose_head = geometry()
        self.grasp_head = grasp()
        self.actor = nn.Sequential(
            nn.Linear(710, 512),
            nn.ELU(),
            nn.Linear(512, 256),
            nn.ELU(),
            nn.Linear(256, 256),
            nn.ELU(),
            nn.Linear(256, 29),
        )

    def from_latent(self, proprio, latent):
        geometry = self.pose_head(latent)
        contacts = self.grasp_head(latent, geometry, proprio)
        return self.actor(torch.cat((proprio, latent, geometry, contacts), -1))

    def forward(self, proprio, depth):
        return self.from_latent(proprio, self.perception_encoder(depth))


class LatentActor(nn.Module):
    def __init__(self, policy):
        super().__init__()
        self.policy = policy

    def forward(self, proprio, latent):
        return self.policy.from_latent(proprio, latent)


def joint_order(root):
    """PhysX breadth-first articulation traversal includes fixed links."""
    joints = root.findall("joint")
    queue = deque(["pelvis"])
    names = []
    while queue:
        parent = queue.popleft()
        for joint in joints:
            if joint.find("parent").get("link") == parent:
                queue.append(joint.find("child").get("link"))
                if joint.get("type") != "fixed":
                    names.append(joint.get("name"))
    if len(names) != 29 or len(set(names)) != 29:
        raise ValueError("Expected exactly 29 unique pelvis-rooted joints")
    return names


def resolve_values(value, names):
    if not isinstance(value, dict):
        return [float(value)] * len(names)
    result = []
    for name in names:
        matches = [float(v) for pattern, v in value.items() if re.fullmatch(pattern, name)]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one value for {name}")
        result.append(matches[0])
    return result


def export_bundle(checkpoint, output, source=DEFAULT_SOURCE, urdf=DEFAULT_URDF, profile=DEFAULT_PROFILE):
    checkpoint, output, source, urdf, profile = map(Path, (checkpoint, output, source, urdf, profile))
    if output.exists() and any(output.iterdir()):
        raise ValueError("Export output must be empty; choose a new bundle directory")
    torch.set_num_threads(1)
    saved = torch.load(checkpoint, map_location="cpu", weights_only=False)
    env_path, agent_path = (checkpoint.parent / "params" / name for name in ("env.yaml", "agent.yaml"))
    env = yaml.load(env_path.read_text(), Loader=ConfigLoader)
    agent = yaml.load(agent_path.read_text(), Loader=ConfigLoader)
    contract = saved["environment_contract"]
    if (
        contract["variant"] != "walled19"
        or contract["actor"] != "proprio558_depth128_geometry12_contacts12"
        or contract["depth"]["normalization"] != "none"
        or contract["depth"]["shape"] != [4, 27, 48]
        or agent["policy"]["class_name"] != "CarryBoxWall16ActorCritic"
        or agent["policy"]["actor_obs_normalization"]
        or agent["policy"]["actor_hidden_dims"] != [512, 256, 256]
        or agent["policy"]["activation"] != "elu"
        or agent["clip_actions"] != 100.0
        or env["actions"]["joint_pos"]["scale"] != 0.25
        or env["observations"]["proprio"]["state"]["history_length"] != 6
        or env["observations"]["perception"]["image"]["history_length"] != 4
        or env["sim"]["dt"] * env["decimation"] != 0.02
    ):
        raise ValueError("Checkpoint/params do not match the supported Wall19 inference contract")
    actor = CarryBoxActor(source).eval()
    state = saved["model_state_dict"]
    inference = {k: v for k, v in state.items() if not (k.startswith("critic.") or k == "log_std")}
    actor.load_state_dict(inference, strict=True)
    if not all(torch.isfinite(v).all() for v in inference.values()):
        raise ValueError("Nonfinite checkpoint weights")
    root = ET.parse(urdf).getroot()
    names = joint_order(root)
    robot = env["scene"]["robot"]
    parameters = []
    for name in names:
        actuators = [
            a for a in robot["actuators"].values() if any(re.fullmatch(p, name) for p in a["joint_names_expr"])
        ]
        if len(actuators) != 1:
            raise ValueError(f"Ambiguous actuator for {name}")
        parameters.append(
            [resolve_values(actuators[0][key], [name])[0] for key in ("stiffness", "damping", "armature")]
        )
    limits = [root.find(f"joint[@name='{name}']/limit") for name in names]
    physics = json.loads(profile.read_text())
    if (
        physics["checkpoint_sha256"] != sha256(checkpoint)
        or physics["environment_contract"] != contract
        or physics["joint_names"] != names
        or physics["source_files_sha256"].get(str(urdf)) != sha256(urdf)
    ):
        raise ValueError("Captured Isaac physics profile is not bound to this checkpoint/URDF")
    for name, digest in physics["source_files_sha256"].items():
        if Path(name).suffix == ".usd" and sha256(name) != digest:
            raise ValueError(f"Captured physics asset changed: {name}")
    camera = env["scene"]["depth_camera"]
    if camera["offset"]["convention"] != "world" or camera["prim_path"].split("/")[-1] != "torso_link":
        raise ValueError("Unsupported camera parent or convention")
    cfg = dict(
        schema="instinct_carrybox_wall19_v1",
        checkpoint=str(checkpoint),
        checkpoint_sha256=sha256(checkpoint),
        iteration=saved["iter"],
        environment_contract=contract,
        joint_names=names,
        history_order="whole_frames_oldest_to_newest",
        control_dt=0.02,
        physics_dt=float(env["sim"]["dt"]),
        default_joint_pos=resolve_values(robot["init_state"]["joint_pos"], names),
        default_root_pose=physics["default_root_pose"],
        kp=[p[0] for p in parameters],
        kd=[p[1] for p in parameters],
        armature=[p[2] for p in parameters],
        effort=[float(l.get("effort")) for l in limits],
        joint_lower=[float(l.get("lower")) for l in limits],
        joint_upper=[float(l.get("upper")) for l in limits],
        camera=dict(
            width=48,
            height=27,
            near=0.1,
            far=3.0,
            fx=camera["focal_length"] * 48 / camera["horizontal_aperture"],
            fy=camera["focal_length"] * 27 / camera["vertical_aperture"],
            position=camera["offset"]["pos"],
            quaternion_wxyz=camera["offset"]["rot"],
        ),
        source_sha256={
            str(p): sha256(p)
            for p in (
                env_path,
                agent_path,
                urdf,
                profile,
                source / "rsl_rl_extensions/modules.py",
                source / "carrybox_wall14.py",
            )
        },
    )
    for key in ("kp", "kd", "effort", "armature"):
        np.testing.assert_allclose(cfg[key], physics["controls"][key], atol=1e-6, rtol=0)
    np.testing.assert_allclose(cfg["default_joint_pos"], physics["default_joint_positions"], atol=1e-7, rtol=0)
    exported = output / "exported"
    exported.mkdir(parents=True)
    p, d = torch.zeros(1, 558), torch.ones(1, 4, 27, 48)
    models = [
        ("depth_encoder", actor.perception_encoder, (d,), ["depth"], ["latent"]),
        ("actor", LatentActor(actor), (p, torch.zeros(1, 128)), ["proprio", "latent"], ["actions"]),
        ("policy", actor, (p, d), ["proprio", "depth"], ["actions"]),
    ]
    with torch.inference_mode():
        for name, model, inputs, input_names, output_names in models:
            torch.onnx.export(
                model,
                inputs,
                str(exported / f"{name}.onnx"),
                opset_version=17,
                input_names=input_names,
                output_names=output_names,
                dynamic_axes={key: {0: "batch"} for key in input_names + output_names},
                dynamo=False,
            )
    cfg["onnx_sha256"] = {name: sha256(exported / f"{name}.onnx") for name, *_ in models}
    # The runtime bundle owns the URDF and meshes; training repositories stay read-only.
    asset_dir = output / "robot"
    (asset_dir / "meshes").mkdir(parents=True)
    root.find("mujoco/compiler").set("meshdir", "meshes")
    for mesh in root.findall(".//mesh"):
        original = (urdf.parent / mesh.get("filename")).resolve()
        destination = asset_dir / "meshes" / original.name
        if destination.exists() and sha256(destination) != sha256(original):
            raise ValueError(f"Mesh basename collision: {original.name}")
        if not destination.exists():
            shutil.copyfile(original, destination)
        mesh.set("filename", f"meshes/{original.name}")
    ET.ElementTree(root).write(asset_dir / "g1.urdf", encoding="unicode")
    (output / "physics.json").write_text(json.dumps(physics, indent=2) + "\n")
    cfg["asset_sha256"] = {str(p.relative_to(output)): sha256(p) for p in sorted(asset_dir.rglob("*")) if p.is_file()}
    cfg["asset_sha256"]["physics.json"] = sha256(output / "physics.json")
    (output / "manifest.json").write_text(json.dumps(cfg, indent=2) + "\n")
    from instinct_onboard.carrybox_policy import CarryBoxPolicy

    runtime = CarryBoxPolicy(output)
    rng = np.random.default_rng(42)
    error = 0.0
    with torch.inference_mode():
        for _ in range(16):
            proprio = rng.normal(0, 0.5, (1, 558)).astype(np.float32)
            depth = rng.uniform(0.1, 3, (1, 4, 27, 48)).astype(np.float32)
            expected = actor(torch.from_numpy(proprio), torch.from_numpy(depth)).numpy()[0]
            actual = runtime.infer(proprio, depth)
            np.testing.assert_allclose(actual, np.clip(expected, -100, 100), atol=2e-5, rtol=1e-5)
            error = max(error, float(np.max(np.abs(actual - np.clip(expected, -100, 100)))))
    report = dict(
        checkpoint_sha256=cfg["checkpoint_sha256"],
        samples=16,
        split_onnx_max_abs_error=error,
        inference_modules=["depth_encoder", "geometry", "grasp", "actor"],
    )
    (output / "validation.json").write_text(json.dumps(report, indent=2) + "\n")
    return report
