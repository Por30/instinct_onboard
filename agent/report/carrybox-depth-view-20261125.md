---
task_id: "ENG-carrybox-depth-view-20261125"
language: "zh-CN"
axes: ["S"]
risk_tier: "T1"
status: "DONE"
changed_files: ["scripts/g1_carrybox_s2s.py", "docs/carrybox.md", "agent/plan/carrybox-depth-view-20261125.md", "agent/task/carrybox-depth-view-20261125.md", "agent/report/carrybox-depth-view-20261125.md", "agent/handoff/carrybox-depth-view-20261125.md", "agent/receipts/carrybox-depth-view-20261125/smoke.py", "agent/receipts/carrybox-depth-view-20261125/depth_window.png", "agent/receipts/carrybox-depth-view-20261125/displayed_history.npy", "agent/receipts/carrybox-depth-view-20261125/results.json", "agent/receipts/carrybox-depth-view-20261125/tests.json"]
task_contract_sha256: "fde9322d54daeeb1c53dd1810370414c87ce20c86a7f04a5aba39cba50956e53"
tests: [{"command": "env MUJOCO_GL=glfw xvfb-run -a -s \"-screen 0 1600x1000x24\" .venv/bin/python agent/receipts/carrybox-depth-view-20261125/smoke.py", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "65a97f927be17400baf9263a6e0671ba390ebcc23b32beb6d0b4521d6bb037ff", "stdout_sha256": "d19c83d4a6c0f58c70320141e7cbd75eb32271a794ae6a095c7e77365dae7e0a", "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "runner": "run_engineering_tests.py"}, {"command": "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "54245a56a4a09812aaa8b8c21a7cc8958d075c36f7d26d4a4ebcbb8aa1810518", "stdout_sha256": "c585b85064c852e7888a54320a39dbd55250a5a2b9d33dcd899ba22166170df1", "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "runner": "run_engineering_tests.py"}]
artifact: "REPORT"
---

交互s2s默认同步打开MuJoCo和Tk深度输入窗口，入口新增DepthWindow及--no-depth-view。窗口只读CarryBoxPolicy.depth_history，显示推理实际使用的四帧27×48深度，左上最旧、右下最新，最近邻放大8倍，固定黑色0.1m、白色3m；标题状态显示输入采样时间、最新帧深度范围和停止原因。显示没有额外渲染相机或推进观测历史，输入时间比动作执行后的MuJoCo状态早一个20ms控制周期。策略、物理、真实部署入口和模式切换没有变化。

两个窗口共享原有停止/重置输入队列；空格/Esc停止，R/Backspace重置，关闭任一窗口结束回放，退出清零仿真控制并释放窗口。--no-depth-view只打开MuJoCo；--headless不导入Tk。文档记录依赖和输入时间语义。

冻结检查2/2通过。Xvfb下使用真实MuJoCo、真实Tk、真实ONNX策略执行四个场景：深度窗口按键停止/重置/关闭、MuJoCo窗口关闭、禁用深度窗口、无DISPLAY的headless运行。检查了停止不推进、重置首帧填充、4帧显示对应关系、显示前后观测/动作/状态不变、双窗口释放和退出控制清零。全量pre-commit通过。depth_window.png为实际窗口截图，displayed_history.npy为对应原始米制输入，results.json保存四个场景结果。截图已检查，标签与四帧内容可读。

验证限于离线原生窗口集成，没有在实际桌面进行人工操作或接入实机。此次未重测搬箱性能；已有持稳审计结论仍适用。代码和证据随cel_instinct提交；用户AGENTS本地授权及carrybox-s2s-manual.json保持原样。
