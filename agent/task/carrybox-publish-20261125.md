---
task_id: "ENG-carrybox-publish-20261125"
language: "zh-CN"
axes: ["S"]
risk_tier: "T1"
artifact: "TASK"
status: "FROZEN"
development_modes: ["BUILD_TOOLING"]
original_request: "后续实机部署 是什么流程 你新建一个cel_instinct分支 把搬箱子相关的改动提交上去 https://github.com/Por30/instinct_onboard"
allowed_paths: ["README.md", "docs/carrybox.md", "agent/", "instinct_onboard/agents/action_term.py", "instinct_onboard/agents/carrybox_agent.py", "instinct_onboard/carrybox_export.py", "instinct_onboard/carrybox_policy.py", "instinct_onboard/robot_cfgs.py", "instinct_onboard/simulation/", "scripts/export_carrybox.py", "scripts/g1_carrybox.py", "scripts/g1_carrybox_s2s.py", "tests/test_carrybox.py", "tests/ros_carrybox_harness.py", ".cache/carrybox-deploy-models.tar.gz", ".cache/carrybox-deploy-models.tar.gz.sha256"]
forbidden_scope: ["执行实机命令", "修改部署/策略/仿真行为", "提交模型/缓存/本地AGENTS环境授权或用户手动回放结果", "覆盖远端分支或改写main/历史", "项目外写入"]
steps: ["核对目标仓库和基线并创建cel_instinct分支", "补全代码拉取、模型迁移、环境预检、dry-run及实机操作文档", "整理搬箱子改动与验证证据并执行冻结检查", "检查提交内容和工件后提交并推送指定仓库", "核对远端分支提交与工作区剩余改动并交付链接及流程"]
tests: [{"command": ".venv/bin/python -m unittest discover -s tests -p test_carrybox.py -v"}, {"command": ".venv/bin/python scripts/g1_carrybox.py --offline --steps 50"}, {"command": "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files"}]
stop_conditions: ["目标分支已有冲突更新则先检查并保留远端内容", "缺少写入认证时保留本地可推送提交并明确报告", "两次范围内修复后冻结检查仍失败"]
safeguards: ["用户仅授权代码提交与推送，未授权操作实机", "只提交审查过的搬箱子路径，不改写main或强推", "保留dryrun/急停/故障锁存及未实测声明", "Git不包含models，明确模型需单独迁移且保持哈希"]
expert_required: false
expert_brief: null
device_actions: []
real_device_authorized: false
---

本次为T1发布/文档任务，已有实现和审计结论保持不变。部署说明明确模型未入Git、真实相机尚未标定、长期持箱会落地；发布不代表实机验证通过。
