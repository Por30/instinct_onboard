---
task_id: "ENG-carrybox-modes-20261124"
language: "zh-CN"
axes: ["D", "H", "C", "S"]
risk_tier: "T2"
status: "DONE"
changed_files: ["scripts/g1_carrybox.py", "tests/ros_carrybox_harness.py", "tests/test_carrybox.py", "docs/carrybox.md", "agent/plan/carrybox-modes.md", "agent/task/carrybox-modes.md", "agent/report/carrybox-modes.md", "agent/handoff/carrybox-modes.md", "agent/receipts/carrybox-modes/tests.json", "agent/receipts/carrybox-modes/tests-attempt1.json"]
task_contract_sha256: "8fe7b95ad1c85616d633f964e37f5eaed469d18cb03b13eb528d0ed8670ac51a"
tests: [{"command": ".venv/bin/python -m unittest discover -s tests -p test_carrybox.py -v", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "6dba2e34daf05948eeec6d59075ac28101b139c570ad261e806d84ebcffc2c9e", "stdout_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "stderr_sha256": "351d1a4fdca15692c81a6196b83794616ef3c9b23184657b222bf48e3377f44c", "runner": "run_engineering_tests.py"}, {"command": "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "54245a56a4a09812aaa8b8c21a7cc8958d075c36f7d26d4a4ebcbb8aa1810518", "stdout_sha256": "c585b85064c852e7888a54320a39dbd55250a5a2b9d33dcd899ba22166170df1", "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "runner": "run_engineering_tests.py"}]
artifact: "REPORT"
---

已核对原g1_parkour实际代码，并对齐搬箱入口：自动ColdStartAgent，到位后R1进入stand，L1进入carrybox，R1当tick返回stand。保留L2/R2，新增入口原有B急停与锁存故障。采用按键上升沿防止长按跨模式，双键不启用carrybox。冷启动复用原helper的实测位置步进，不再固定3秒插值；保留startup_step_size/kpkd_factor参数，自带identity动作项保证倍率实际生效。

通过standdir接回原ParkourStandAgent，节点保持TorsoBase关节及IMU语义；carrybox输入和输出按名称/腰部符号转换，仍直接读取pelvis IMU。kp/kd只排列。两策略互不污染历史。额外要求torso IMU时效；ROS限矩取原部署与搬箱限制的较小值，因此髋roll88Nm低于s2s训练139Nm。原locomotion脚本、共享UnitreeNode、训练模型和s2s未在本次跟进中修改。

未提供stand模型时，只允许显式pose-stand的dry-run姿态检查，禁止nodryrun组合。stand有四个必需文件；加载后控制timer启动前进行不发布的真实stand结构推理检查。旧模型格式没有可靠root/joint张量元数据，不编造自动语义检查。

最终12项unittest全部通过，包括13种模拟ROS入口场景；真实ColdStartAgent和搬箱ONNX参与，stand为mock。覆盖到位、提前按键、长按、双键、重入历史、R1当tick不运行旧策略、非同一pelvis/torso输入、29关节映射、故障锁存和非法状态。pre-commit run --all-files通过。首次测试已通过，首次格式检查由Black自动整理三个文件；首次回执保留，最终回执全部PASS。工程工件须通过交叉校验。

没有实机或ROS环境，也尚未提供原standdir。真实stand模型推理、训练关节语义、平衡能力和携箱返回stand的动态表现未验证；R1不是放箱或保箱策略。原部署固件协议沿用mode_pr=0、从LowState读取mode_machine、CRC和发布话题，不自动切换OEM运动服务。具体步骤见docs/carrybox.md。
