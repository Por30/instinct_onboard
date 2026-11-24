---
task_id: "ENG-carrybox-stand-20261124"
language: "zh-CN"
axes: ["L", "S", "D"]
risk_tier: "T2"
artifact: "PLAN"
status: "DONE"
allowed_paths: ["models/stand_onboard/", "tests/", "scripts/g1_carrybox.py", "docs/carrybox.md", "agent/"]
---

从官方项目模型包提取stand，保留模型字节和来源；用现有入口和真实ParkourStandAgent/ONNX做离线模式集成检查，补充官方原始实机操作顺序。
