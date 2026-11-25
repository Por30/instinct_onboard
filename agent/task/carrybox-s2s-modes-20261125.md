---
task_id: "ENG-carrybox-s2s-modes-20261125"
language: "zh-CN"
axes: ["D", "C", "S"]
risk_tier: "T2"
artifact: "TASK"
status: "FROZEN"
development_modes: ["STATE_MACHINE", "SIMULATOR_EXTENSION", "MODEL_DEPLOYMENT"]
original_request: "保留原来的模式操作，s2s也模拟这套流程，按s进入stand模式，按a进入搬箱子模式"
allowed_paths: ["scripts/g1_carrybox_s2s.py", "instinct_onboard/simulation/", "tests/test_carrybox_s2s_modes.py", "tests/stand_parity_harness.py", "docs/carrybox.md", "agent/"]
forbidden_scope: ["真实入口/ROS/策略权重修改或实机操作", "修复上一轮鼠标选中GUI测试", "覆盖用户AGENTS或手动回放结果", "改写main或强推"]
steps: ["实现官方stand的仿真执行并对齐TorsoBase观测/动作和跨模式last_action", "接入冷启动支撑、S/A转移守卫与急停/R恢复", "接入双窗口模式提示和深度使用语义及CLI起始模式", "执行数值对照和原生GUI/无界面检查，记录自由stand结果", "更新使用文档及工程工件并校验"]
tests: [{"command": ".venv/bin/python -m unittest discover -s tests -p test_carrybox_s2s_modes.py -v"}, {"command": "env MUJOCO_GL=glfw xvfb-run -a -s \"-screen 0 1600x1000x24\" .venv/bin/python agent/receipts/carrybox-s2s-modes-20261125/smoke.py"}, {"command": "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files"}]
stop_conditions: ["两次范围内修复仍无法通过冻结测试", "需要真实硬件或项目外写入", "用户文件冲突", "若官方stand加载或自由站立失败，保留故障证据并停止自动运行", "原鼠标测试问题不纳入本任务修复或完成声明"]
safeguards: ["保持scripts/g1_carrybox.py及真实手柄流程不变；键盘A是仿真搬箱键，区别于实机A初始化手柄", "仿真扶正只在cold_start生效并明确显示；S放行检查实测关节误差，未到位S不延迟生效", "急停优先于同批S/A，立即清ctrl/xfrc，必须R恢复；回stand不承诺保箱或放箱", "官方模型缺失、输入输出非有限、维度不匹配或推理异常明确失败停控，不降级姿态stand", "切入stand当前tick不再运行carrybox；重置策略历史并保留上一条已接受目标的last_action语义", "深度窗口区分stand固定零输入与carrybox米制深度，非carrybox不把旧帧当当前输入", "原鼠标拖拽GUI阻塞独立保留，本次模式测试不代表旧鼠标已验证"]
expert_required: true
expert_brief: {"affected_call_path": ["键盘队列→仿真模式控制→cold_start/stand/carrybox→统一PD子步", "仿真stand runner加载官方ONNX与动作项，真实入口只读"], "critical_interfaces": ["stand按TorsoBase关节重排及腰部符号，position/velocity/effort带符号，kp/kd仅重排", "torso_link局部角速度/投影重力；carrybox仍pelvis", "stand输入896=6项8帧历史768+固定零深度[1,8,18,32]编码128", "last_action反算跨模式上一条接受TargetJointState"], "invariants": ["cold_start仅到位新S进入stand，A仅stand放行，S从carrybox立即返stand", "cold_start每次位置增量0.2rad且kp/kd为carrybox两倍", "历史按项、旧到新、首次重复，stand速度缩放不污染源状态", "50Hz和已有子步及限矩/有限检查；stand无扶正支持", "形状重置回cold_start，急停后形状键不能恢复"], "smallest_change_locus": ["s2s入口键盘/状态/深度显示；sim可选目标和冷启动支撑；仿真专用stand模型执行", "专用数值对照与原生GUI测试、文档和工件；不改真实agent/ROS"], "mandatory_safeguards": ["保持scripts/g1_carrybox.py及真实手柄流程不变；键盘A是仿真搬箱键，区别于实机A初始化手柄", "仿真扶正只在cold_start生效并明确显示；S放行检查实测关节误差，未到位S不延迟生效", "急停优先于同批S/A，立即清ctrl/xfrc，必须R恢复；回stand不承诺保箱或放箱", "官方模型缺失、输入输出非有限、维度不匹配或推理异常明确失败停控，不降级姿态stand", "切入stand当前tick不再运行carrybox；重置策略历史并保留上一条已接受目标的last_action语义", "深度窗口区分stand固定零输入与carrybox米制深度，非carrybox不把旧帧当当前输入", "原鼠标拖拽GUI阻塞独立保留，本次模式测试不代表旧鼠标已验证"], "minimal_tests": [".venv/bin/python -m unittest discover -s tests -p test_carrybox_s2s_modes.py -v", "env MUJOCO_GL=glfw xvfb-run -a -s \"-screen 0 1600x1000x24\" .venv/bin/python agent/receipts/carrybox-s2s-modes-20261125/smoke.py", "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files"], "blockers": ["若官方stand加载或自由站立失败，保留故障证据并停止自动运行", "原鼠标测试问题不纳入本任务修复或完成声明"]}
device_actions: []
real_device_authorized: false
---

官方stand资产已存在，仿真生产路径不使用ROS stub；测试以实际ParkourStandAgent为数值对照。默认cold_start，显式--start-mode carrybox用于原直接回放。
