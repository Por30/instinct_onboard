---
task_id: "ENG-carrybox-interaction-20261125"
language: "zh-CN"
axes: ["S"]
risk_tier: "T2"
artifact: "PLAN"
status: "PARTIAL"
allowed_paths: ["scripts/g1_carrybox_s2s.py", "instinct_onboard/simulation/carrybox.py", "tests/test_carrybox_interaction.py", "docs/carrybox.md", "agent/"]
---

复用原生MuJoCo鼠标扰动，修复被阻尼覆盖的外力，增加六种形状的交互切换。单S轴T2，本Agent实施并做数值及原生GUI检查。
