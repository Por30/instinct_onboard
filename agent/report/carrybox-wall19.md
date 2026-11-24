---
task_id: "ENG-carrybox-wall19-20261124"
language: "zh-CN"
axes: ["L", "P", "C", "S", "E"]
risk_tier: "T2"
status: "DONE"
changed_files: ["AGENTS.md", "agent/handoff/carrybox-wall19.md", "agent/plan/carrybox-wall19.md", "agent/receipts/carrybox-wall19/export-validation.json", "agent/receipts/carrybox-wall19/s2s.json", "agent/receipts/carrybox-wall19/tests.json", "agent/report/carrybox-wall19.md", "agent/task/carrybox-wall19.md", "docs/carrybox.md", "instinct_onboard/agents/action_term.py", "instinct_onboard/agents/carrybox_agent.py", "instinct_onboard/carrybox_export.py", "instinct_onboard/carrybox_policy.py", "instinct_onboard/robot_cfgs.py", "instinct_onboard/simulation/__init__.py", "instinct_onboard/simulation/carrybox.py", "scripts/export_carrybox.py", "scripts/g1_carrybox.py", "scripts/g1_carrybox_s2s.py", "tests/ros_carrybox_harness.py", "tests/test_carrybox.py"]
task_contract_sha256: "d09c22f1aee794d5d0c6d4d4353c0fd16230dcd29ef58dfeb41f183993fa7848"
tests: [{"command": ".venv/bin/python -m unittest discover -s tests -p test_carrybox.py -v", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "6dba2e34daf05948eeec6d59075ac28101b139c570ad261e806d84ebcffc2c9e", "stdout_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "stderr_sha256": "dc3664360e91dc71f8749cdbf1a5697e981cb5f15433336fab65a857b8ca69b0", "runner": "run_engineering_tests.py"}, {"command": ".venv/bin/python scripts/g1_carrybox_s2s.py --bundle models/carrybox_wall19 --headless --duration 20 --output agent/receipts/carrybox-wall19/s2s.json", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "7f24d7ae9d7e79e537ec34effb1508f33cb936200425e3d30f7b1c756408abcc", "stdout_sha256": "3762f24ad907a3fa0f6e2f67efbe58adcb71e52329031192d8dbb8c24434d511", "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "runner": "run_engineering_tests.py"}, {"command": "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "54245a56a4a09812aaa8b8c21a7cc8958d075c36f7d26d4a4ebcbb8aa1810518", "stdout_sha256": "c585b85064c852e7888a54320a39dbd55250a5a2b9d33dcd899ba22166170df1", "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "runner": "run_engineering_tests.py"}]
artifact: "REPORT"
---

# Wall19 搬箱子适配结果

已完成G1深度管线理解、指定checkpoint导出、独立s2r入口与MuJoCo s2s。部署包在 `models/carrybox_wall19`，来源只读，未提交commit。

复用既有相机子进程、JointPositionAction、TargetJointState及Unitree发布接口；s2s与ROS使用同一CarryBoxAgent。新增pelvis根关节配置，保留腰部正号、正确限矩和骨盆IMU；完整保留encoder、geometry、grasp、actor。历史为6×93及4×27×48，深度米制，不接受物体真值。

验证结果：11项unittest通过，覆盖原训练函数/独立旧ONNX的batch1/3对照、历史/映射/深度/惯量，以及模拟ROS接口的急停、三类数据超时、推理异常和20ms截止时间。分离ONNX对16组输入最大误差1.430511474609375e-6。pre-commit全部适用检查通过。

20秒标准箱闭环运行1000步，未触发倾倒、数值或限矩失败。曾连续搬起1秒；严格持稳2秒未通过。结束时箱底离地0.75318m，双手接触力约30.53/31.96N。限矩比例最大1.0。单一初态结果不代表稳定性或成功率，亦不等同历史参考不同初态的18.1秒结果。

当前没有实机，未运行真实ROS2/RealSense/电机；ROS测试为stub transport。相机标定和完整端到端采集延迟仍需现场核对；watchdog不是设备级安全保证。s2s为标准箱标称场景，未覆盖多形状、随机化或配对RSI。44body物理来自已绑定同checkpoint的现有Isaac采集profile，本轮未重新采集。

启动：`.venv/bin/python scripts/g1_carrybox_s2s.py`。无通信检查：`.venv/bin/python scripts/g1_carrybox.py --offline`。完整说明见 `docs/carrybox.md`。
