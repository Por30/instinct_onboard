---
task_id: "ENG-carrybox-wall19-20261124"
language: "zh-CN"
axes: ["L", "P", "C", "S", "E"]
risk_tier: "T2"
artifact: "TASK"
status: "FROZEN"
development_modes: ["MODEL_DEPLOYMENT", "SIMULATOR_EXTENSION", "ROS_NODE"]
original_request: "阅读并理解本项目g1深度相机部署管线 然后按照本项目s2r框架适配我的策略 /home/cao/perceptual_ball/logs/rsl_rl/g1_carrybox_depth/walled19/2026-11-07_17-31-48_wall19_still_hold_fresh30k_20261107_173148/05_stage5_from15000/model_29999.pt；现在没有实机 你就仿照本项目深度locomotion的管线 适配我的般箱子策略 同时实现s2s"
allowed_paths: ["instinct_onboard/agents/action_term.py", "instinct_onboard/agents/carrybox_agent.py", "instinct_onboard/carrybox_policy.py", "instinct_onboard/carrybox_export.py", "instinct_onboard/simulation/", "instinct_onboard/robot_cfgs.py", "scripts/g1_carrybox.py", "scripts/g1_carrybox_s2s.py", "scripts/export_carrybox.py", "tests/", "docs/carrybox.md", "agent/", "models/carrybox_wall19/", "AGENTS.md"]
forbidden_scope: ["修改训练项目或checkpoint", "真实设备操作", "更改现有locomotion行为", "commit/push"]
steps: ["核对checkpoint、训练观测/控制/相机与已有管线", "导出完整ONNX并冻结部署参数", "实现共用历史推理和G1入口", "实现MuJoCo场景、光轴深度和闭环控制", "运行单元、集成和格式检查并记录边界", "生成使用文档、报告和交接并校验"]
tests: [{"command": ".venv/bin/python -m unittest discover -s tests -p test_carrybox.py -v"}, {"command": ".venv/bin/python scripts/g1_carrybox_s2s.py --bundle models/carrybox_wall19 --headless --duration 20 --output agent/receipts/carrybox-wall19/s2s.json"}, {"command": "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files"}]
stop_conditions: ["需要写入项目外文件", "出现真实设备操作需求", "冻结测试失败两次修复后仍不通过"]
safeguards: ["ROS default dryrun, explicit cold-start and enable; R2/L2 and finally motor-off", "state/joystick/camera-production timestamps and inference deadline, startup timeout, latched stop", "shape/finite/quaternion validation and real/sim torque limits, unstable physics stop", "No hardware execution; source files read-only; camera intrinsics/extrinsics require measurement"]
expert_required: true
expert_brief: {"affected_call_path": ["checkpoint/params → split encoder + geometry/grasp/actor ONNX → CarryBoxPolicy → CarryBoxAgent → TargetJointState → ROS/MuJoCo"], "critical_interfaces": ["FP32 proprio558=6 whole93 frames; depth4x27x48 optical metres; actor710 to action29", "Pelvis IMU and all-positive original URDF axes; named mapping distinct from TorsoBase"], "invariants": ["50Hz/5ms/decimation4; oldest first; repeat first frame/reset last action zero", "depth0.1–3m without /3; every ray starts at optical near plane", "default+0.25*clip100; previous raw action independent of torque-clipped command", "44body captured physics42.341142404591665kg; inertia COM rotation and mj_setConst; source capsule shoulder collision"], "smallest_change_locus": ["new carrybox policy/export/agent/scripts and simulation module", "action_term RealNode type-only import; separate pelvis robot configuration"], "mandatory_safeguards": ["ROS default dryrun, explicit cold-start and enable; R2/L2 and finally motor-off", "state/joystick/camera-production timestamps and inference deadline, startup timeout, latched stop", "shape/finite/quaternion validation and real/sim torque limits, unstable physics stop", "No hardware execution; source files read-only; camera intrinsics/extrinsics require measurement"], "minimal_tests": [".venv/bin/python -m unittest discover -s tests -p test_carrybox.py -v", ".venv/bin/python scripts/g1_carrybox_s2s.py --bundle models/carrybox_wall19 --headless --duration 20 --output agent/receipts/carrybox-wall19/s2s.json", "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files"], "blockers": []}
device_actions: []
real_device_authorized: false
---

用户授权当前本机无实机的适配和s2s；训练来源只读。已完成一次只读专家审查，继承所有安全约束。

测试内容：

- unittest: training forward and ONNX batch1/3 parity, latest93/zero-normal heads, depth and invalid schema/hash
- unittest: named joints/signs/pelvis, history reset and previous raw action, near-plane rays, 44body inertia and29joint limits
- unittest: ROS interface stubs for dryrun/stop/stale state-camera-joystick/inference failure; actual ROS unavailable
- 20s smoke: timing, finite, torque, actual stop reason; pickup1s and strict-hold2s separate
- pre-commit frozen command and honest receipts
