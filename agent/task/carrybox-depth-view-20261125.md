---
task_id: "ENG-carrybox-depth-view-20261125"
language: "zh-CN"
axes: ["S"]
risk_tier: "T1"
artifact: "TASK"
status: "FROZEN"
development_modes: ["SIMULATOR_EXTENSION"]
original_request: "同时在s2s的时候同步启动一个窗口可视化当前s2s的深度信息输入"
allowed_paths: ["scripts/g1_carrybox_s2s.py", "docs/carrybox.md", "agent/"]
forbidden_scope: ["修改策略/观测/动作/仿真物理行为", "模型与真实ROS入口改动", "硬件操作", "覆盖用户手动回放或本地AGENTS修改", "强推或改写main"]
steps: ["在s2s入口接入默认启用的Tk深度窗口，直接显示策略4帧输入及时间", "接入停止/重置和双窗口关闭生命周期，保留headless并提供显式关闭深度窗口选项", "执行真实MuJoCo/Tk图形集成检查和格式检查并保存截图/回执", "更新使用文档及工程记录，提交推送到已授权cel_instinct分支"]
tests: [{"command": "env MUJOCO_GL=glfw xvfb-run -a -s \"-screen 0 1600x1000x24\" .venv/bin/python agent/receipts/carrybox-depth-view-20261125/smoke.py"}, {"command": "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files"}]
stop_conditions: ["出现已有用户改动冲突", "两次范围内修复后冻结检查仍失败", "需要实际硬件或改动策略/物理参数"]
safeguards: ["只读当前CarryBoxPolicy.depth_history，不额外调用相机或observe推进历史", "显示固定0.1–3m尺度及策略输入时间，保持真实27×48像素和4帧顺序", "headless不导入或创建Tk，退出时清零仿真控制并释放窗口", "保持现有停止和重置语义；关闭任一窗口终止同一回放", "不提交无关AGENTS与用户手动回放文件，不强推"]
expert_required: false
expert_brief: null
device_actions: []
real_device_authorized: false
---

直接读取本控制周期已经用于推理的深度历史；图像放大仅用于显示。检查窗口事件与模拟步、重置以及关闭行为，避免只验证图像拼接实现。
