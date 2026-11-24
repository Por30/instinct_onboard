---
task_id: "ENG-carrybox-stand-20261124"
language: "zh-CN"
axes: ["L", "S", "D"]
risk_tier: "T2"
status: "DONE"
changed_files: ["scripts/g1_carrybox.py", "tests/ros_carrybox_harness.py", "tests/test_carrybox.py", "docs/carrybox.md", "models/stand_onboard/params/env.yaml", "models/stand_onboard/params/agent.yaml", "models/stand_onboard/exported/actor.onnx", "models/stand_onboard/exported/0-depth_encoder.onnx", "models/stand_onboard/UPSTREAM_README.md", "models/stand_onboard/provenance.json", "agent/plan/carrybox-stand.md", "agent/task/carrybox-stand.md", "agent/report/carrybox-stand.md", "agent/handoff/carrybox-stand.md", "agent/receipts/carrybox-stand/tests.json", "agent/receipts/carrybox-stand/tests-attempt1.json", "agent/receipts/carrybox-stand/provenance.json"]
task_contract_sha256: "4a9d2a0c121f863d7fecc8d5b9afb0b3c3fffc32cce4145c0f1c52ef3acda75b"
tests: [{"command": ".venv/bin/python -m unittest discover -s tests -p test_carrybox.py -v", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "6dba2e34daf05948eeec6d59075ac28101b139c570ad261e806d84ebcffc2c9e", "stdout_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "stderr_sha256": "b7556b1597229a20cf4f359da51e26e6a19e3d219f4223f788f0127e7f1478fc", "runner": "run_engineering_tests.py"}, {"command": "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "54245a56a4a09812aaa8b8c21a7cc8958d075c36f7d26d4a4ebcbb8aa1810518", "stdout_sha256": "c585b85064c852e7888a54320a39dbd55250a5a2b9d33dcd899ba22166170df1", "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "runner": "run_engineering_tests.py"}]
artifact: "HANDOFF"
resume_command: null
---

当前官方stand已就绪：models/stand_onboard。使用 python scripts/g1_carrybox.py --bundle models/carrybox_wall19 --standdir models/stand_onboard；默认dryrun，真正硬件执行仍需现场明确授权。无ROS用--offline，s2s用scripts/g1_carrybox_s2s.py。

本工件接续carrybox-modes，解决其中“原stand尚缺”的限制；历史工件保留当时事实。官方ZIP存放.cache/hiking-in-the-wild_Data_Model.zip，来源与哈希在models/stand_onboard/provenance.json及agent/receipts/carrybox-stand/provenance.json。models被Git忽略，迁移时复制两个bundle；本轮未commit。

当前入口保留原cold_start/R1 stand/L1 carrybox/R1 stand，R1返回当tick执行stand。保持stand速度getter副本隔离，不能移除；保留真实模型非零dq回归。原共享Agent、UnitreeNode、旧locomotion入口和s2s未改。

最终12项unittest与pre-commit回执在tests.json；其中14种入口场景含官方stand真实推理和故障路径。所有传输仍为stub，不能记成实机或站立平衡验收。官方README操作顺序已整理于docs/carrybox.md，程序启动前OEM按键与程序运行中急停必须分开。
