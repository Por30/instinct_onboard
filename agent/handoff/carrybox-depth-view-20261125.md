---
task_id: "ENG-carrybox-depth-view-20261125"
language: "zh-CN"
axes: ["S"]
risk_tier: "T1"
status: "DONE"
changed_files: ["scripts/g1_carrybox_s2s.py", "docs/carrybox.md", "agent/plan/carrybox-depth-view-20261125.md", "agent/task/carrybox-depth-view-20261125.md", "agent/report/carrybox-depth-view-20261125.md", "agent/handoff/carrybox-depth-view-20261125.md", "agent/receipts/carrybox-depth-view-20261125/smoke.py", "agent/receipts/carrybox-depth-view-20261125/depth_window.png", "agent/receipts/carrybox-depth-view-20261125/displayed_history.npy", "agent/receipts/carrybox-depth-view-20261125/results.json", "agent/receipts/carrybox-depth-view-20261125/tests.json"]
task_contract_sha256: "fde9322d54daeeb1c53dd1810370414c87ce20c86a7f04a5aba39cba50956e53"
tests: [{"command": "env MUJOCO_GL=glfw xvfb-run -a -s \"-screen 0 1600x1000x24\" .venv/bin/python agent/receipts/carrybox-depth-view-20261125/smoke.py", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "65a97f927be17400baf9263a6e0671ba390ebcc23b32beb6d0b4521d6bb037ff", "stdout_sha256": "d19c83d4a6c0f58c70320141e7cbd75eb32271a794ae6a095c7e77365dae7e0a", "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "runner": "run_engineering_tests.py"}, {"command": "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "54245a56a4a09812aaa8b8c21a7cc8958d075c36f7d26d4a4ebcbb8aa1810518", "stdout_sha256": "c585b85064c852e7888a54320a39dbd55250a5a2b9d33dcd899ba22166170df1", "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "runner": "run_engineering_tests.py"}]
artifact: "HANDOFF"
resume_command: null
---

深度可视化功能完成，入口scripts/g1_carrybox_s2s.py默认启用双窗口。工作站启动：

```bash
cd /home/cao/instinct_onboard
MUJOCO_GL=glfw .venv/bin/python scripts/g1_carrybox_s2s.py --bundle models/carrybox_wall19 --duration 60
```

输入按四帧历史排列，黑近白远，直接显示上次策略推理使用的27×48米制输入，附采样时间。空格/Esc停止，R/Backspace重置；关闭任一窗口退出。仅需MuJoCo时添加--no-depth-view，离线批量检查添加--headless。模型目录沿用本机已有导出包；模型仍不在Git中。新环境的交互双窗口需要Python tkinter。

真实MuJoCo/Tk图形集成四场景及pre-commit均通过，回执和实际截图见agent/receipts/carrybox-depth-view-20261125/。没有未完成的功能修复。实机相机标定与策略持稳验证仍按docs/carrybox.md中的既有结论和流程另行处理；本功能不改变实机部署行为。
