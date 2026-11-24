---
task_id: "ENG-carrybox-wall19-20261124"
language: "zh-CN"
axes: ["L", "P", "C", "S", "E"]
risk_tier: "T2"
status: "DONE"
changed_files: ["AGENTS.md", "agent/handoff/carrybox-wall19.md", "agent/plan/carrybox-wall19.md", "agent/receipts/carrybox-wall19/export-validation.json", "agent/receipts/carrybox-wall19/s2s.json", "agent/receipts/carrybox-wall19/tests.json", "agent/report/carrybox-wall19.md", "agent/task/carrybox-wall19.md", "docs/carrybox.md", "instinct_onboard/agents/action_term.py", "instinct_onboard/agents/carrybox_agent.py", "instinct_onboard/carrybox_export.py", "instinct_onboard/carrybox_policy.py", "instinct_onboard/robot_cfgs.py", "instinct_onboard/simulation/__init__.py", "instinct_onboard/simulation/carrybox.py", "scripts/export_carrybox.py", "scripts/g1_carrybox.py", "scripts/g1_carrybox_s2s.py", "tests/ros_carrybox_harness.py", "tests/test_carrybox.py"]
task_contract_sha256: "d09c22f1aee794d5d0c6d4d4353c0fd16230dcd29ef58dfeb41f183993fa7848"
tests: [{"command": ".venv/bin/python -m unittest discover -s tests -p test_carrybox.py -v", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "6dba2e34daf05948eeec6d59075ac28101b139c570ad261e806d84ebcffc2c9e", "stdout_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "stderr_sha256": "dc3664360e91dc71f8749cdbf1a5697e981cb5f15433336fab65a857b8ca69b0", "runner": "run_engineering_tests.py"}, {"command": ".venv/bin/python scripts/g1_carrybox_s2s.py --bundle models/carrybox_wall19 --headless --duration 20 --output agent/receipts/carrybox-wall19/s2s.json", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "7f24d7ae9d7e79e537ec34effb1508f33cb936200425e3d30f7b1c756408abcc", "stdout_sha256": "3762f24ad907a3fa0f6e2f67efbe58adcb71e52329031192d8dbb8c24434d511", "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "runner": "run_engineering_tests.py"}, {"command": "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "54245a56a4a09812aaa8b8c21a7cc8958d075c36f7d26d4a4ebcbb8aa1810518", "stdout_sha256": "c585b85064c852e7888a54320a39dbd55250a5a2b9d33dcd899ba22166170df1", "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "runner": "run_engineering_tests.py"}]
artifact: "HANDOFF"
resume_command: null
---

# Wall19 稳定状态与交接

实现与三条冻结检查完成。使用 `models/carrybox_wall19` 可以直接运行；该目录由既有.gitignore忽略，迁移时复制整个bundle或按 `docs/carrybox.md` 从指定checkpoint重新导出。环境 `.venv` 继承本机umr依赖，并在项目内安装prettytable和pre-commit3.8.0；系统默认python3.8不适用本项目的新入口。

验证复现命令保存在frontmatter和Task。默认GUI入口 `.venv/bin/python scripts/g1_carrybox_s2s.py`，20秒、标准箱；空格/Esc停止，R/Backspace重置。带 `--headless --output <项目内路径>` 可保存结果。所有仿真和测试进程均已退出，无真实设备连接。

关键不变量：pelvis基座和IMU，29关节按训练顺序映射，waist正号；光轴米制深度；六个完整本体帧、四个深度帧；上一动作为clip100原始输出，限矩后不反算；actor含geometry/grasp反馈；真实入口默认dryrun，异常锁存关闭电机。

当前20s回放搬起1s通过、严格持稳2s未通过；不要将这一结果写为稳定持箱或硬件验收通过。ROS2未安装，安全分支仅stub验证。后续硬件验证需要现场明确授权与IMU/相机/电机关节标定；不需要为已授权的离线继续工作重复询问权限。
