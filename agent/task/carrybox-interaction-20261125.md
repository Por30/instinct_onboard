---
task_id: "ENG-carrybox-interaction-20261125"
language: "zh-CN"
axes: ["S"]
risk_tier: "T2"
artifact: "TASK"
status: "FROZEN"
development_modes: ["SIMULATOR_EXTENSION"]
original_request: "加上右键拖拽的功能 同时能让我用 1 2 3 4 56 来切换不同形状的物体"
allowed_paths: ["scripts/g1_carrybox_s2s.py", "instinct_onboard/simulation/carrybox.py", "tests/test_carrybox_interaction.py", "docs/carrybox.md", "agent/"]
forbidden_scope: ["真实硬件/ROS部署或策略输入契约变更", "修改模型权重与默认长方体物理参数", "覆盖用户AGENTS或手动回放", "强推或改写main"]
steps: ["保留原MuJoCo viewer，将鼠标扰动力传递到全部物理子步并保持停止/重置清理", "增加六种物体形状及正确碰撞/惯量/底部高度，按数字键切换并重置同一回放", "在双窗口提示形状与按键，保留headless并更新文档", "执行数值与原生GUI集成、pre-commit及工件校验，提交到cel_instinct"]
tests: [{"command": ".venv/bin/python -m unittest discover -s tests -p test_carrybox_interaction.py -v"}, {"command": "env MUJOCO_GL=glfw xvfb-run -a -s \"-screen 0 1600x1000x24\" .venv/bin/python agent/receipts/carrybox-interaction-20261125/smoke.py"}, {"command": "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files"}]
stop_conditions: ["用户文件冲突", "两次范围内修复后冻结测试仍失败", "需要实际设备或策略结构变更"]
safeguards: ["鼠标外力仅作用仿真，原扭矩限幅/停止检查保留", "停止/重置/切换/退出清空外力及扰动状态", "形状切换同步碰撞边界与编译得到的惯量，不混合历史", "默认形状无交互时维持原轨迹；其他形状为额外仿真探查", "保留深度真实输入显示和原viewer相机操作", "不触碰用户文件与main"]
expert_required: false
expert_brief: null
device_actions: []
real_device_authorized: false
---

数字键1–6对应长方体、正方体、球体、圆柱、胶囊体、椭球。默认保持长方体，切换形状重置策略与仿真。鼠标沿用原生Ctrl+右键扰动和裸右键平移视角。
