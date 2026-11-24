---
task_id: "ENG-carrybox-wall19-20261124"
language: "zh-CN"
axes: ["L", "P", "C", "S", "E"]
risk_tier: "T2"
artifact: "PLAN"
status: "DONE"
allowed_paths: ["instinct_onboard/agents/action_term.py", "instinct_onboard/agents/carrybox_agent.py", "instinct_onboard/carrybox_policy.py", "instinct_onboard/carrybox_export.py", "instinct_onboard/simulation/", "instinct_onboard/robot_cfgs.py", "scripts/g1_carrybox.py", "scripts/g1_carrybox_s2s.py", "scripts/export_carrybox.py", "tests/", "docs/carrybox.md", "agent/", "models/carrybox_wall19/", "AGENTS.md"]
---

实现独立carrybox入口，复用现有TargetJointState/ActionTerm/Unitree相机架构，保留旧入口。部署与MuJoCo共用实际策略输入和输出变换；离线验收不等同实机或任务成功。
