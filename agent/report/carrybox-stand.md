---
task_id: "ENG-carrybox-stand-20261124"
language: "zh-CN"
axes: ["L", "S", "D"]
risk_tier: "T2"
status: "DONE"
changed_files: ["scripts/g1_carrybox.py", "tests/ros_carrybox_harness.py", "tests/test_carrybox.py", "docs/carrybox.md", "models/stand_onboard/params/env.yaml", "models/stand_onboard/params/agent.yaml", "models/stand_onboard/exported/actor.onnx", "models/stand_onboard/exported/0-depth_encoder.onnx", "models/stand_onboard/UPSTREAM_README.md", "models/stand_onboard/provenance.json", "agent/plan/carrybox-stand.md", "agent/task/carrybox-stand.md", "agent/report/carrybox-stand.md", "agent/handoff/carrybox-stand.md", "agent/receipts/carrybox-stand/tests.json", "agent/receipts/carrybox-stand/tests-attempt1.json", "agent/receipts/carrybox-stand/provenance.json"]
task_contract_sha256: "4a9d2a0c121f863d7fecc8d5b9afb0b3c3fffc32cce4145c0f1c52ef3acda75b"
tests: [{"command": ".venv/bin/python -m unittest discover -s tests -p test_carrybox.py -v", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "6dba2e34daf05948eeec6d59075ac28101b139c570ad261e806d84ebcffc2c9e", "stdout_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "stderr_sha256": "b7556b1597229a20cf4f359da51e26e6a19e3d219f4223f788f0127e7f1478fc", "runner": "run_engineering_tests.py"}, {"command": "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files", "result": "PASS", "exit_code": 0, "executed": true, "receipt_sha256": "54245a56a4a09812aaa8b8c21a7cc8958d075c36f7d26d4a4ebcbb8aa1810518", "stdout_sha256": "c585b85064c852e7888a54320a39dbd55250a5a2b9d33dcd899ba22166170df1", "stderr_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "runner": "run_engineering_tests.py"}]
artifact: "REPORT"
---

已从Hiking in the Wild官网Data & Model链接取得官方压缩包，通过Google Drive连接器下载，白名单提取stand_onboard四个原文件及README到models/stand_onboard。原字节不变，ZIP与逐文件SHA256见provenance回执；无修改上游账户、无发送消息、无实机操作。

实际加载官方ParkourStandAgent和两张ONNX通过：encoder输入1×8×18×32、输出1×128；actor输入1×896、输出1×29。8×96本体历史按原观测项堆叠，真实CircularBuffer参与；stand零深度覆盖路径未调用图像处理。官方agent.yaml原本为空，当前loader不使用其内容，没有填造配置。

真实模型检查发现原stand关节速度getter返回共享引用，观测归一化会原地将dq乘0.05。仅在新入口通过StandAgent覆盖该getter返回副本，隔离对搬箱后续输入的污染；未修改共享ParkourStandAgent。非零dq测试确认启动预检、正常stand步及注入真实actor故障后共享q/dq保持不变。故障时不再发布正常命令。

12项unittest通过，包含14种入口场景，新增真实官方stand与carrybox切换，以及actor失败锁存。真实ColdStartAgent、ParkourStandAgent、CircularBuffer和ONNX参与；ROS、相机、可视化边界仍为stub。pre-commit全部检查通过，首次isort仅整理导入，首次回执保留。工程工件交叉校验通过后交付。

已依据上游README补充原实机前置步骤：程序前平躺、L2+R2停止原运动模式、L2+A后L2+B复位，再启动、手扶直立、R1站立、L1进入任务。强调程序运行中L2/R2/B会急停，不能重复复位组合；使用非急停键初始化消息。以上仅为来源核对，未执行。

官方下载与真实前向完成了上一轮缺少stand模型的离线验证。ONNX/env仍无完整根坐标/训练关节排序元数据，不将来源和结构检查冒充物理对齐证明；未验证真实ROS、RealSense、动态平衡、携箱返回stand或硬件安全。此前s2s标称场景结果不变。
