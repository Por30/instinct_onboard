---
task_id: "ENG-carrybox-interaction-20261125"
language: "zh-CN"
axes: ["S"]
risk_tier: "T2"
status: "PARTIAL"
changed_files: ["scripts/g1_carrybox_s2s.py", "instinct_onboard/simulation/carrybox.py", "tests/test_carrybox_interaction.py", "docs/carrybox.md", "agent/plan/carrybox-interaction-20261125.md", "agent/task/carrybox-interaction-20261125.md", "agent/report/carrybox-interaction-20261125.md", "agent/handoff/carrybox-interaction-20261125.md", "agent/receipts/carrybox-interaction-20261125/smoke.py", "agent/receipts/carrybox-interaction-20261125/tests.json", "agent/receipts/carrybox-interaction-20261125/tests-attempt1.json"]
task_contract_sha256: "ea7a82f1e6ee1e9a175c2164fde01b228b43e0bbe254c77079dc55837fc33bc0"
tests: [{"command": ".venv/bin/python -m unittest discover -s tests -p test_carrybox_interaction.py -v", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "cbfa8e2f9c8d1509ad6a77d640528a586eb0489ac8bf04c705bbfde553b9850e", "stdout_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "stderr_sha256": "a55a4424c326de3b5c60cf64a3096b15038de10c19d23e0e43ab442fb0f21bf6", "runner": "run_engineering_tests.py"}, {"command": "env MUJOCO_GL=glfw xvfb-run -a -s \"-screen 0 1600x1000x24\" .venv/bin/python agent/receipts/carrybox-interaction-20261125/smoke.py", "result": "FAIL", "exit_code": 1, "executed": true, "receipt_sha256": "5bc45b8ba5363265718cf4d8f37604612b9b10c3fd732543af311d33753da84a", "stdout_sha256": "831776694a6c1b7edff1385c087a707001d272eb7118cded225ba3f6b38f6008", "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "runner": "run_engineering_tests.py"}, {"command": "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "54245a56a4a09812aaa8b8c21a7cc8958d075c36f7d26d4a4ebcbb8aa1810518", "stdout_sha256": "c585b85064c852e7888a54320a39dbd55250a5a2b9d33dcd899ba22166170df1", "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "runner": "run_engineering_tests.py"}]
artifact: "HANDOFF"
resume_command: "env MUJOCO_GL=glfw xvfb-run -a -s \"-screen 0 1600x1000x24\" .venv/bin/python agent/receipts/carrybox-interaction-20261125/smoke.py"
---

代码已实现六种形状、双窗口数字键1–6切换、CLI启动形状及物理子步外力叠加。形状变化重置策略历史和回放，更新质量/惯量/碰撞边界，按实际形状计算底部高度；质量保持1.125kg。默认长方体参数不变。停止、重置、切换与退出清除外力，原生右键视角操作保留，物体扰动使用双击选中后Ctrl+右键。

冻结数值检查通过3项：六种形状的深度可见性/历史/地面接触、返回长方体后12步轨迹与默认一致、10N外力贯穿4个物理子步且释放/停止/重置清理。全量pre-commit通过。图形测试中的Tk和原生MuJoCo数字键六形状切换已通过，Ctrl+右键拖拽的端到端验证尚未通过：XTest双击后viewer.perturb.select仍为0，因此没有执行后续拖拽位移/停止/重置和六形状headless检查。不能声称完整鼠标操作验证成功。

初次图形失败为键事件尚未被消费，修复为等待原生回调；第二次失败为鼠标选择未命中，修复为将点击从射线边缘移到物体投影内部并等待事件。选择仍失败，触发工程技能最多两次范围内修复的停止条件。已向用户请求继续排查授权；当前未提交/推送，不触碰用户AGENTS和手动回放文件。此前cel_instinct已发布功能保持不变。

继续时先确认用户允许突破两次修复限制，再排查Xvfb坐标、原生viewport与双击事件；保留现有测试断言，不以直接设置perturb.select代替真实鼠标验证。完成后通过冻结检查、更新工件、pre-commit再提交到cel_instinct。

后续状态：上述“未提交/推送”指本轮鼠标任务停止时。后续carrybox-s2s-modes-20261125任务随模式代码携带这些交互改动；鼠标任务仍为PARTIAL，历史回执未改写。其smoke.py主场景尚未适配新的模式入口，只有XInput键盘辅助被新模式测试复用，恢复鼠标排查时需一并核对。
