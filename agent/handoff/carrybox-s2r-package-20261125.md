---
task_id: "ENG-carrybox-s2r-package-20261125"
language: "zh-CN"
axes: ["A"]
risk_tier: "T1"
status: "DONE"
changed_files: ["README.md", "docs/carrybox.md", "deployment/carrybox-models.tar.gz", "deployment/carrybox-models.tar.gz.sha256", "agent/plan/carrybox-s2r-package-20261125.md", "agent/task/carrybox-s2r-package-20261125.md", "agent/report/carrybox-s2r-package-20261125.md", "agent/handoff/carrybox-s2r-package-20261125.md", "agent/receipts/carrybox-s2r-package-20261125/archive.json", "agent/receipts/carrybox-s2r-package-20261125/tests.json"]
task_contract_sha256: "77dcd07866c2d041e0b95083e0ef1d73236e49005448eb896de98b8f350baee7"
tests: [{"command": "sha256sum -c deployment/carrybox-models.tar.gz.sha256", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "87b353cbfdb804c19b33088b2725eb8ab2d4d33422b7f5d1f644132b6b4c9bb0", "stdout_sha256": "ca2b436e6a47ade288b37cd54f8b2f11d2a9dbc6e7af8aeb17ab5d70e58b5b34", "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "runner": "run_engineering_tests.py"}, {"command": "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "54245a56a4a09812aaa8b8c21a7cc8958d075c36f7d26d4a4ebcbb8aa1810518", "stdout_sha256": "c585b85064c852e7888a54320a39dbd55250a5a2b9d33dcd899ba22166170df1", "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "runner": "run_engineering_tests.py"}]
artifact: "HANDOFF"
resume_command: null
---

另一台电脑按docs/carrybox.md首节获取cel_instinct，在仓库根目录执行sha256sum -c deployment/carrybox-models.tar.gz.sha256，再用tar --keep-old-files -xzf deployment/carrybox-models.tar.gz首次解包。已有同名模型时先核对/备份，不覆盖用户模型；归档未变时pull代码不必重新解包。

需准备对应架构的原ROS2/Unitree/CRC/RealSense/Python环境，不能复制本机.venv。默认入口为python scripts/g1_carrybox.py --bundle models/carrybox_wall19 --standdir models/stand_onboard，保持dry-run；真实电机发布需现场完成验收后显式加--nodryrun。实机A仅初始化，R1站立、L1搬箱、R1返回、L2/R2/B急停，Select未绑定；仿真S/A不能套用到实机。

模型归档及静态检查通过；没有恢复用户暂停的鼠标/动力学验证或新增实机测试。实机观测显示/记录功能未实现，相机外参、传感器时序及真实关节/IMU对齐仍需设备测量。本次归档不改变此前未严格持稳及长期stand未验证的结论。

任务交付限于分支发布已有实现及模型。AGENTS.md和用户手动回放JSON留在本地；提交后核对远端cel_instinct与本地HEAD一致。
