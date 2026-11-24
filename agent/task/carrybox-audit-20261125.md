---
task_id: "ENG-carrybox-audit-20261125"
language: "zh-CN"
axes: ["L", "P", "C", "S"]
risk_tier: "T2"
artifact: "TASK"
status: "FROZEN"
development_modes: ["MODEL_DEPLOYMENT", "SIMULATOR_EXTENSION"]
original_request: "看一下s2s的表现 以及后续我实机部署 观测和深度相机什么的都对其了吗"
allowed_paths: ["agent/", "docs/carrybox.md"]
forbidden_scope: ["真实设备操作", "改策略/权重/训练参数", "修改部署及仿真核心行为", "项目外写入", "commit/push"]
steps: ["核对实际观测/图像/控制路径与训练参数", "固定初态运行60秒上限的训练限矩、部署限矩值、部署目标预裁剪三组对照并记录轨迹", "查看视频/曲线，分离搬起、持稳、掉落与倾倒", "整理已对齐/不一致/待现场测量项目及使用说明", "执行冻结检查并校验报告交接"]
tests: [{"command": ".venv/bin/python -m unittest discover -s tests -p test_carrybox.py -v"}, {"command": "env MUJOCO_GL=egl .venv/bin/python agent/receipts/carrybox-audit-20261125/evaluate.py"}, {"command": "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files"}]
stop_conditions: ["需要硬件或项目外修改", "两次范围内修复后冻结检查仍失败", "无阻碍三组离线诊断的来源缺失；本审查未运行本轮回放或测试，不预报结果。", "外参没有实际校验、传感器采集未同步、启动/stand切换未做动力学仿真，阻止给出后续实机观测和部署已经完全对齐的结论。", "s2s已有hip终止和strict yaw等判据实现差异已向主Agent反馈；本轮scope不含生产代码修复，必须作为未解决项交接。"]
safeguards: ["No hardware execution, preserve default dryrun and e-stop", "Do not change policies, models, timing, camera or deployment parameters", "Limit-only simulation comparison is not a hardware deployment validation", "Keep latched pickup separate from continuous hold and dynamic stability", "Training camera intrinsics/extrinsics are requirements, not measured real-camera calibration", "三组只作为确定性工程诊断；第三组明确标注目标预裁剪诊断，不把MuJoCo硬限矩视为实机电机已证明具备的行为。", "保留有限值、数值稳定性、关节越限、限矩和现有终止条件；60s是请求上限，触发终止即报告实际时长，不绕过终止延长演示。", "同时保存现有metrics及训练同义的hip_yaw高度、局部yaw strict重算；若判据差异影响停止或结论，明确说明，不能称成功判据完整对齐。", "区分曾连续搬起1s、当前仍持箱、严格持稳2s和整段保持情况；不得由pickup锁存为真或未倾倒推导策略稳定。", "无硬件时仅确认光轴米制处理与数学接口；近场无效测量、遮挡后表面、视野、外参、同步延迟和深度噪声均不能由纯s2s证实。", "ROS仍默认dryrun，保留急停及锁存watchdog；20ms检查覆盖发布前计算，不证明传输、驱动和硬件闭环延迟满足20ms。"]
expert_required: true
expert_brief: {"affected_call_path": ["训练参数/checkpoint → shared CarryBoxPolicy → ROS TorsoBase/pelvis IMU/RealSense 或 MuJoCo。仅离线诊断，不改生产代码。"], "critical_interfaces": ["93×6本体、4×27×48光轴米制深度、关节排序/符号、默认q及动作缩放在代码层对齐；真实物理标定未验证。"], "invariants": ["训练相机外参在s2s使用，在实机路径未使用或测量；50Hz取60FPS最新帧可重复，主机收帧时间不是曝光时间；未同步深度与lowstate。", "部署hip_roll139→88Nm，50Hz目标预裁剪不同于s2s200Hz直接限矩；s2s没有coldstart/stand动态切换。", "原s2s hip检测误用hip_pitch，strict用world yaw而非local yaw，box>.7而非>=.7，手力为法向绝对值累计而非净向量范数。"], "smallest_change_locus": ["agent/receipts/carrybox-audit-20261125诊断脚本/数据/视频，docs及工程工件；第三组复用真实clip helper AST。"], "mandatory_safeguards": ["三组只作为确定性工程诊断；第三组明确标注目标预裁剪诊断，不把MuJoCo硬限矩视为实机电机已证明具备的行为。", "保留有限值、数值稳定性、关节越限、限矩和现有终止条件；60s是请求上限，触发终止即报告实际时长，不绕过终止延长演示。", "同时保存现有metrics及训练同义的hip_yaw高度、局部yaw strict重算；若判据差异影响停止或结论，明确说明，不能称成功判据完整对齐。", "区分曾连续搬起1s、当前仍持箱、严格持稳2s和整段保持情况；不得由pickup锁存为真或未倾倒推导策略稳定。", "无硬件时仅确认光轴米制处理与数学接口；近场无效测量、遮挡后表面、视野、外参、同步延迟和深度噪声均不能由纯s2s证实。", "ROS仍默认dryrun，保留急停及锁存watchdog；20ms检查覆盖发布前计算，不证明传输、驱动和硬件闭环延迟满足20ms。"], "minimal_tests": [".venv/bin/python -m unittest discover -s tests -p test_carrybox.py -v", "env MUJOCO_GL=egl .venv/bin/python agent/receipts/carrybox-audit-20261125/evaluate.py", "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files"], "blockers": ["无阻碍三组离线诊断的来源缺失；本审查未运行本轮回放或测试，不预报结果。", "外参没有实际校验、传感器采集未同步、启动/stand切换未做动力学仿真，阻止给出后续实机观测和部署已经完全对齐的结论。", "s2s已有hip终止和strict yaw等判据实现差异已向主Agent反馈；本轮scope不含生产代码修复，必须作为未解决项交接。"]}
device_actions: []
real_device_authorized: false
---

延长单一确定性场景检查，不做成功率/泛化科研结论。所有产物写入项目agent与docs目录。
