---
task_id: "ENG-carrybox-s2r-package-20261125"
language: "zh-CN"
axes: ["A"]
risk_tier: "T1"
status: "DONE"
changed_files: ["README.md", "docs/carrybox.md", "deployment/carrybox-models.tar.gz", "deployment/carrybox-models.tar.gz.sha256", "agent/plan/carrybox-s2r-package-20261125.md", "agent/task/carrybox-s2r-package-20261125.md", "agent/report/carrybox-s2r-package-20261125.md", "agent/handoff/carrybox-s2r-package-20261125.md", "agent/receipts/carrybox-s2r-package-20261125/archive.json", "agent/receipts/carrybox-s2r-package-20261125/tests.json"]
task_contract_sha256: "77dcd07866c2d041e0b95083e0ef1d73236e49005448eb896de98b8f350baee7"
tests: [{"command": "sha256sum -c deployment/carrybox-models.tar.gz.sha256", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "87b353cbfdb804c19b33088b2725eb8ab2d4d33422b7f5d1f644132b6b4c9bb0", "stdout_sha256": "ca2b436e6a47ade288b37cd54f8b2f11d2a9dbc6e7af8aeb17ab5d70e58b5b34", "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "runner": "run_engineering_tests.py"}, {"command": "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "54245a56a4a09812aaa8b8c21a7cc8958d075c36f7d26d4a4ebcbb8aa1810518", "stdout_sha256": "c585b85064c852e7888a54320a39dbd55250a5a2b9d33dcd899ba22166170df1", "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "runner": "run_engineering_tests.py"}]
artifact: "REPORT"
---

本次交付将现有s2r运行资产随cel_instinct分支发布，目标仓库为https://github.com/Por30/instinct_onboard。基于已发布的2815442568c20e2f6adb8044e9cdbd6d17c527c8，仅补充模型归档、校验文件和部署说明，没有修改ROS、策略或仿真运行逻辑。

归档共19,521,067字节，含models/carrybox_wall19和models/stand_onboard；55个成员均为普通文件或目录，没有链接或越界路径。所有文件与当前已准备模型逐字节一致，manifest/provenance中的45项声明哈希全部匹配，细节见archive.json。归档SHA256为fda185e4ef6d8e0efd7f3e9a17dec79b44177e1e6f55890c932f3f28b5f32a18，不包含原始训练checkpoint或工作站虚拟环境。

README和docs/carrybox.md给出clone/pull→SHA256校验→首次解包→原ROS/Python环境→offline→dry-run→现场接管流程。明确实机A初始化、R1站立、L1搬箱、R1返回及L2/R2/B急停；Select未绑定。现场相机/本体/历史/时序验收表区分代码契约和真实设备未测项目；专用实机观测显示/完整输入记录工具尚未实现。

冻结的模型归档校验与pre-commit run --all-files均通过。保留用户暂停的GUI/动力学验证，不重新推理、不接入相机/ROS/电机。此前60秒搬箱回放两次落地、严格持稳未通过，短时stand通过不证明长期或实机稳定；这些既有边界没有因打包而改变。

只提交上述允许文件。用户本地AGENTS.md授权修改和carrybox-s2s-manual.json保持原状，不纳入交付。发布使用por30的SSH push URL，正常更新cel_instinct，不改写main或强推；提交后以git ls-remote核对远端分支。
