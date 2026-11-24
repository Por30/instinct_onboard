---
task_id: "ENG-carrybox-publish-20261125"
language: "zh-CN"
axes: ["S"]
risk_tier: "T1"
artifact: "PLAN"
status: "DONE"
allowed_paths: ["README.md", "docs/carrybox.md", "agent/", "instinct_onboard/agents/action_term.py", "instinct_onboard/agents/carrybox_agent.py", "instinct_onboard/carrybox_export.py", "instinct_onboard/carrybox_policy.py", "instinct_onboard/robot_cfgs.py", "instinct_onboard/simulation/", "scripts/export_carrybox.py", "scripts/g1_carrybox.py", "scripts/g1_carrybox_s2s.py", "tests/test_carrybox.py", "tests/ros_carrybox_harness.py", ".cache/carrybox-deploy-models.tar.gz", ".cache/carrybox-deploy-models.tar.gz.sha256"]
---

整理已有搬箱子实现并发布到用户指定分支；只补部署流程和发布记录，不修改运行行为。保留本地环境授权及用户手动回放文件，不放入提交。
