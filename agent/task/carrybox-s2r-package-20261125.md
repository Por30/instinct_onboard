---
task_id: "ENG-carrybox-s2r-package-20261125"
language: "zh-CN"
axes: ["A"]
risk_tier: "T1"
artifact: "TASK"
status: "FROZEN"
development_modes: ["BUILD_TOOLING"]
original_request: "把改完的s2r流程推送到分支上 我后续直接用另一台电脑pull下来部署"
allowed_paths: ["deployment/carrybox-models.tar.gz", "deployment/carrybox-models.tar.gz.sha256", "docs/carrybox.md", "README.md", "agent/plan/carrybox-s2r-package-20261125.md", "agent/task/carrybox-s2r-package-20261125.md", "agent/report/carrybox-s2r-package-20261125.md", "agent/handoff/carrybox-s2r-package-20261125.md", "agent/receipts/carrybox-s2r-package-20261125/"]
forbidden_scope: ["修改策略/ROS/仿真运行逻辑", "恢复用户暂停的仿真和鼠标验证或操作实机", "提交用户AGENTS修改和手动回放结果", "项目外写入、强推或改写main"]
steps: ["核对cel_instinct远端与已有模型包内容和哈希", "将现有部署模型包纳入分支并补齐pull/解包/环境/观测验收说明", "执行包完整性与pre-commit检查，生成并校验工程记录", "提交推送cel_instinct并核对远端提交及模型包可用性"]
tests: [{"command": "sha256sum -c deployment/carrybox-models.tar.gz.sha256"}, {"command": "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files"}]
stop_conditions: ["远端有并发更新时保留并核对差异", "两次范围内修复后冻结检查仍失败", "缺少推送认证时保留可推送提交并报告"]
safeguards: ["本次用户要求另一台电脑pull后部署，随分支提供当前已准备的ONNX/stand模型包；不包含原始训练checkpoint", "模型归档仅含models/carrybox_wall19和models/stand_onboard普通文件/目录，保持原模型字节及来源记录", "默认dry-run和原实机按键保持；明确观测验收工具尚未实现、实机未验证", "工程校验仅限模型归档完整性与静态pre-commit，不恢复已暂停的动力学/鼠标验证"]
expert_required: false
expert_brief: null
device_actions: []
real_device_authorized: false
---

本次发布已有s2r实现及可迁移模型，满足另一台电脑从分支获取运行资产。原发布任务的模型单独复制方案由本次同分支归档替代；历史工件保留原始记录。
