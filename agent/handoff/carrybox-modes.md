---
task_id: "ENG-carrybox-modes-20261124"
language: "zh-CN"
axes: ["D", "H", "C", "S"]
risk_tier: "T2"
status: "DONE"
changed_files: ["scripts/g1_carrybox.py", "tests/ros_carrybox_harness.py", "tests/test_carrybox.py", "docs/carrybox.md", "agent/plan/carrybox-modes.md", "agent/task/carrybox-modes.md", "agent/report/carrybox-modes.md", "agent/handoff/carrybox-modes.md", "agent/receipts/carrybox-modes/tests.json", "agent/receipts/carrybox-modes/tests-attempt1.json"]
task_contract_sha256: "8fe7b95ad1c85616d633f964e37f5eaed469d18cb03b13eb528d0ed8670ac51a"
tests: [{"command": ".venv/bin/python -m unittest discover -s tests -p test_carrybox.py -v", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "6dba2e34daf05948eeec6d59075ac28101b139c570ad261e806d84ebcffc2c9e", "stdout_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "stderr_sha256": "351d1a4fdca15692c81a6196b83794616ef3c9b23184657b222bf48e3377f44c", "runner": "run_engineering_tests.py"}, {"command": "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "54245a56a4a09812aaa8b8c21a7cc8958d075c36f7d26d4a4ebcbb8aa1810518", "stdout_sha256": "c585b85064c852e7888a54320a39dbd55250a5a2b9d33dcd899ba22166170df1", "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "runner": "run_engineering_tests.py"}]
artifact: "HANDOFF"
resume_command: null
---

当前入口实现与离线检查完成，使用文档以docs/carrybox.md为准；此前carrybox-wall19工件保留首次适配和20秒s2s结果，本工件记录后续模式对齐。所有修改仅在项目内，未连接真实设备，未commit。

ROS默认使用 python scripts/g1_carrybox.py --bundle models/carrybox_wall19 --standdir <原TorsoBase站立目录>。无stand模型时可显式使用--pose-stand进行dry-run；无ROS仍用.venv/bin/python scripts/g1_carrybox.py --offline。s2s入口和已有bundle不变。

保留当前映射方向、独立pelvis/torso IMU、逐项较小限矩、历史重置、watchdog与原有发布门。不要直接把carrybox数组给原stand，或将pose-stand解释为平衡策略。原standdir仍待用户提供，收到后应核对训练来源/根坐标/关节语义和真实模型结构；这不是已完成的硬件验收。硬件执行需另获明确授权。

精确测试命令在Task及frontmatter中，最终回执agent/receipts/carrybox-modes/tests.json，首次Black整理回执tests-attempt1.json。
