---
task_id: "ENG-carrybox-stand-20261124"
language: "zh-CN"
axes: ["L", "S", "D"]
risk_tier: "T2"
artifact: "TASK"
status: "FROZEN"
development_modes: ["MODEL_DEPLOYMENT", "STATE_MACHINE"]
original_request: "可能要去原来的项目里下载把"
allowed_paths: ["models/stand_onboard/", "tests/", "scripts/g1_carrybox.py", "docs/carrybox.md", "agent/"]
forbidden_scope: ["真实硬件操作", "修改上游权重", "修改共享Agent/ROS节点", "项目外写入", "commit/push"]
steps: ["确认官方来源并保存stand及来源哈希", "核对env和ONNX接口并接入现有离线入口测试", "运行冻结测试，记录与硬件验证的边界", "更新原部署步骤、报告、交接并校验"]
tests: [{"command": ".venv/bin/python -m unittest discover -s tests -p test_carrybox.py -v"}, {"command": "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files"}]
stop_conditions: ["官方模型结构与现有入口不兼容且需要扩大修改范围", "两次范围内修复后冻结测试仍不通过", "需要真实设备操作", "若共享dq副作用未隔离且非零回归未通过，停止真实stand离线验收", "若结构不兼容需扩大共享源码范围，停止并报告"]
safeguards: ["Official stand weights unchanged; source hashes recorded", "Only local offline inference, no real hardware or remote writes", "Preserve default dryrun, coordinate mapping, history reset, watchdog and e-stop", "Do not equate fake ROS interface/ONNX checks with dynamic balance validation", "真实stand用非零dq验证启动预检、正常step和异常后共享dq不变", "验证encoder1x8x18x32到1x128、actor1x896到1x29及有限TargetJointState；启动前推理不发布", "测试提取仓库真实CircularBuffer AST；fake getter保持真实副本/引用语义", "官方OEM复位组合键仅在程序启动前使用；程序运行后L2/R2/B急停，用非急停键初始化手柄", "保留dryrun、所有watchdog、20ms deadline、发布锁和故障锁存；不操作硬件", "只报告真实ONNX前向及入口切换，不报告ROS/相机/动态平衡或携箱切换成功"]
expert_required: true
expert_brief: {"affected_call_path": ["官方zip白名单提取stand四文件及README → 原ParkourStandAgent → 真实ONNX → 入口模拟ROS传输", "保留实际ColdStart、CircularBuffer和carrybox，替换设备通信边界"], "critical_interfaces": ["官方zip SHA bbba90bdb77bbab19e74cbe9f556ea0b9330ea9d125ad8271d431aa0e37a6609；env23649字节，agent.yaml原为空且loader不使用其内容", "stand按观测项堆8帧本体96维，加128latent为896；不套用carrybox整帧历史", "stand64x36裁剪到18x32，零深度getter不使用48x27缓存采样网格或cv2", "原stand速度getter引用共享dq，base观测原地乘0.05会污染缓存，入口需隔离"], "invariants": ["四文件原字节及hash不变，白名单解压忽略其他资产", "TorsoBase stand与pelvis carrybox映射/IMU保持，独立深度和历史", "stand推理不得改变共享q/dq，重入策略历史reset", "官方出处与结构通过不等同物理平衡/实机对齐证明"], "smallest_change_locus": ["models/stand_onboard和provenance，真实stand模式测试", "入口用StandAgent局部覆盖速度getter返回副本，保持共享源码不变", "docs补官方操作与离线边界"], "mandatory_safeguards": ["真实stand用非零dq验证启动预检、正常step和异常后共享dq不变", "验证encoder1x8x18x32到1x128、actor1x896到1x29及有限TargetJointState；启动前推理不发布", "测试提取仓库真实CircularBuffer AST；fake getter保持真实副本/引用语义", "官方OEM复位组合键仅在程序启动前使用；程序运行后L2/R2/B急停，用非急停键初始化手柄", "保留dryrun、所有watchdog、20ms deadline、发布锁和故障锁存；不操作硬件", "只报告真实ONNX前向及入口切换，不报告ROS/相机/动态平衡或携箱切换成功"], "minimal_tests": [".venv/bin/python -m unittest discover -s tests -p test_carrybox.py -v", "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files"], "blockers": ["若共享dq副作用未隔离且非零回归未通过，停止真实stand离线验收", "若结构不兼容需扩大共享源码范围，停止并报告"]}
device_actions: []
real_device_authorized: false
---

用户授权从原项目寻找下载。已确认官方Hiking in the Wild链接和包内部署README。新增文件仅在项目目录。
