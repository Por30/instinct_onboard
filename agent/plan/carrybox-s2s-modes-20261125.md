---
task_id: "ENG-carrybox-s2s-modes-20261125"
language: "zh-CN"
axes: ["D", "C", "S"]
risk_tier: "T2"
artifact: "PLAN"
status: "DONE"
allowed_paths: ["scripts/g1_carrybox_s2s.py", "instinct_onboard/simulation/", "tests/test_carrybox_s2s_modes.py", "tests/stand_parity_harness.py", "docs/carrybox.md", "agent/"]
---

保留实机模式语义，在现有MuJoCo入口增加cold_start→S stand→A carrybox→S stand，并显示支撑和模式状态。继续保留上一轮形状代码及鼠标未验证事实。

已完成S/A模式、官方stand数值对照、双窗口操作与短时自由站立验证，详见同task_id Report。实机和此前鼠标GUI未验证状态保持独立。
