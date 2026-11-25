---
task_id: "ENG-carrybox-s2s-modes-20261125"
language: "zh-CN"
axes: ["D", "C", "S"]
risk_tier: "T2"
status: "DONE"
changed_files: ["scripts/g1_carrybox_s2s.py", "instinct_onboard/simulation/carrybox.py", "instinct_onboard/simulation/stand.py", "tests/test_carrybox_s2s_modes.py", "tests/stand_parity_harness.py", "docs/carrybox.md", "agent/plan/carrybox-s2s-modes-20261125.md", "agent/task/carrybox-s2s-modes-20261125.md", "agent/report/carrybox-s2s-modes-20261125.md", "agent/handoff/carrybox-s2s-modes-20261125.md", "agent/receipts/carrybox-s2s-modes-20261125/modes.png", "agent/receipts/carrybox-s2s-modes-20261125/results-before-gyro-fix.json", "agent/receipts/carrybox-s2s-modes-20261125/results.json", "agent/receipts/carrybox-s2s-modes-20261125/smoke.py", "agent/receipts/carrybox-s2s-modes-20261125/stand-probe-before-gyro-fix.json", "agent/receipts/carrybox-s2s-modes-20261125/tests-attempt1.json", "agent/receipts/carrybox-s2s-modes-20261125/tests-attempt2.json", "agent/receipts/carrybox-s2s-modes-20261125/tests-before-format.json", "agent/receipts/carrybox-s2s-modes-20261125/tests.json", "agent/report/carrybox-interaction-20261125.md", "agent/handoff/carrybox-interaction-20261125.md"]
task_contract_sha256: "8e5b37f40996d8361f9896646b9e00887189e6b2afd1473b589c5de08bbc7560"
tests: [{"command": ".venv/bin/python -m unittest discover -s tests -p test_carrybox_s2s_modes.py -v", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "0b8db419928fb7248631643b794be33af68572fa2ac9a87669d7f9e4d948df5e", "stdout_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "stderr_sha256": "cddbb1f502cf40cd7f44b235cdf3b569d8a919386e6426ab9bd8e86515740a38", "runner": "run_engineering_tests.py"}, {"command": "env MUJOCO_GL=glfw xvfb-run -a -s \"-screen 0 1600x1000x24\" .venv/bin/python agent/receipts/carrybox-s2s-modes-20261125/smoke.py", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "56a0fbc388fabd199a3d54e1ce6b8579ab437c2a01a36032c0cee05763f87d30", "stdout_sha256": "50a5fa3645605ad2a0fbd0cc5b597a433a3a429f8e6755744c421f17565d1aa6", "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "runner": "run_engineering_tests.py"}, {"command": "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "54245a56a4a09812aaa8b8c21a7cc8958d075c36f7d26d4a4ebcbb8aa1810518", "stdout_sha256": "c585b85064c852e7888a54320a39dbd55250a5a2b9d33dcd899ba22166170df1", "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "runner": "run_engineering_tests.py"}]
artifact: "HANDOFF"
resume_command: null
---

实机入口scripts/g1_carrybox.py与ROS节点未改：A初始化手柄→自动cold_start→到位后新按R1 stand→L1搬箱→R1返回stand；L2/R2/B急停。

s2s默认cold_start，用固定根位姿明确模拟人工支撑。至少执行过一个冷启动控制步且全部关节误差≤0.2rad时，新按S进入官方stand并撤去支撑；A只允许从stand进入carrybox，S立即返回stand。空格/Esc/B优先急停并清零，锁存后仅R重置恢复；形状切换也回cold_start。两个窗口显示模式与支撑状态。搬箱显示实际4帧深度历史，stand使用官方8帧18×32全零输入，其他模式的相机画面标为未消费预览。

新增ROS-free官方stand执行器，复用动作项、按项8帧历史和跨模式上一目标反算动作。按名称映射TorsoBase顺序/腰部符号，以torso link坐标读取角速度及重力。当前入口所有模式使用ROS与训练限矩的交集；原139Nm髋roll的60秒回放不是当前入口的复验。

冻结验证全部通过：4项单元测试（含与实际ParkourStandAgent的15步数值对照、重置/历史/源状态不污染、帧与关节映射、到位守卫和故障停控）；真实Tk/MuJoCo按键切换、急停优先/锁存、R恢复、形状重置和双窗口退出；无DISPLAY三种起始模式；全量pre-commit。stand检查共10秒，首20ms受支撑cold_start，后9.98秒无支撑stand未触发停止。完整结果见同slug receipts/results.json。

两次范围内修复：第一次改正MuJoCo惯性局部帧与torso link帧混用；第二次修正快捷stand启动跳过cold_start导致last_action初始化不同（修前5.96秒倾倒），实际执行一条冷启动目标后再切入，并守卫首个tick前S不能跳过冷启动。没有伪造last_target或按成功案例增加固定预热时间。格式工具随后统一换行，最终测试回执全通过。tests-attempt1/2和before-gyro-fix文件为历史失败/诊断，不代表当前验证结果。

已实现所请求模式流程，但未验证长期stand、携箱返回stand稳定性、实机相机/标定/传感器时序。此前鼠标选中拖拽GUI测试仍为独立PARTIAL；本次没有恢复其排查，也不把模式检查写成鼠标验证通过。用户AGENTS.md和carrybox-s2s-manual.json保持不提交；模型目录仍被Git忽略。

交互启动：`env MUJOCO_GL=glfw .venv/bin/python scripts/g1_carrybox_s2s.py --bundle models/carrybox_wall19 --standdir models/stand_onboard --duration 60`。本任务无待恢复实现；若另行排查原鼠标GUI，先读取其PARTIAL handoff及停止条件。
