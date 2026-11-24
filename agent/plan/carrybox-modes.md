---
task_id: "ENG-carrybox-modes-20261124"
language: "zh-CN"
axes: ["D", "H", "C", "S"]
risk_tier: "T2"
artifact: "PLAN"
status: "DONE"
allowed_paths: ["scripts/g1_carrybox.py", "tests/", "docs/carrybox.md", "agent/"]
---

核对并恢复原实机入口模式操作，复用ColdStartAgent和可选原ParkourStandAgent。当前搬箱入口固定3秒准备且不能返回stand；修复入口接线和回归测试，不改训练或s2s。验收覆盖正常切换、提前启用、到位判断、重入重置、坐标映射、失联和急停。
