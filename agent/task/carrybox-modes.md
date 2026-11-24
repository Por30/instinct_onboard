---
task_id: "ENG-carrybox-modes-20261124"
language: "zh-CN"
axes: ["D", "H", "C", "S"]
risk_tier: "T2"
artifact: "TASK"
status: "FROZEN"
development_modes: ["STATE_MACHINE", "ROS_NODE"]
original_request: "并确认以下原来的实机部署步骤 模式的切换 尽量保持原来的设计"
allowed_paths: ["scripts/g1_carrybox.py", "tests/", "docs/carrybox.md", "agent/"]
forbidden_scope: ["真实设备操作", "修改原locomotion行为或训练checkpoint", "修改项目外文件", "commit/push"]
steps: ["核对原状态机、站立模型接口和部署前置条件", "恢复原按键流程并隔离两个策略的关节和IMU约定", "补充入口状态切换和故障测试", "执行冻结测试并更新部署步骤和交接"]
tests: [{"command": ".venv/bin/python -m unittest discover -s tests -p test_carrybox.py -v"}, {"command": "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files"}]
stop_conditions: ["需要真实设备操作", "两次范围内修复仍无法通过冻结测试", "需要项目外修改", "若具体stand模型不兼容，停止该模型部署；当前缺少该bundle仅阻碍真实模型语义和推理核验，不阻碍离线入口实现"]
safeguards: ["No hardware execution; default dryrun and explicit nodryrun only with stand model", "Preserve latched watchdog, finite validation, 20ms deadline, L2/R2/B and finally motor-off", "Carrybox pelvis IMU, named joint permutation/signs; stand original torso convention and fresh secondary IMU", "Do not change original locomotion entry, trained policy, s2s physics or external files", "stand启动前执行不发布的真实ParkourStandAgent.step，检查ORT结构、状态及TargetJointState shape/finite；缺模型不声称root、joint语义或平衡已验证", "结构不匹配阻止启动；具体模型语义不兼容阻止使用；无可靠字段时明确兼容性前提，不臆造自动检查", "默认dryrun；pose-stand仅显式dryrun，禁止nodryrun组合；缺stand不自动降级", "stand要求有效torso IMU和独立100ms watchdog，禁止pelvis fallback", "保留状态/深度/摇杆/控制时效、20ms deadline、finite、急停及退出停机；publish_lock内复查fault，故障后不发布正常动作", "真实stand模型、ROS、相机、硬件和携箱返回stand动态未验证；mock不替代这些验证"]
expert_required: true
expert_brief: {"affected_call_path": ["自动 ColdStartAgent → R1 stand → L1 carrybox → R1 stand；TorsoBase节点，R1当tick执行stand，不再运行carrybox", "限定入口、测试、docs和agent工件；不修改共享Agent、ROS节点或s2s"], "critical_interfaces": ["旧stand格式不保证root frame或关节顺序元数据；USD路径和配置名称不能证明语义", "standdir必须是原G1_29Dof_TorsoBase兼容bundle；机器检查文件、配置、ONNX输入输出及目标，语义需具体训练来源", "按名称排列并转换waist符号；position/velocity/effort带符号，kp/kd只排列；carrybox pelvis IMU、stand torso IMU", "stand需env.yaml、agent.yaml、actor.onnx和0-depth_encoder.onnx；构造前零base_velocity_cmd"], "invariants": ["TorsoBase节点和last_sent_target_joint_state语义固定；carrybox独立训练历史和上一动作", "进入carrybox reset，进入stand显式清空历史", "ColdStartAgent自带identity动作项使kpkd_factor生效，RealNode最终限幅", "按键上升沿、到位条件、双键抑制、每tick一次切换；力矩取原部署和搬箱限制较小值"], "smallest_change_locus": ["保留入口映射与安全处理，不补造frame元数据或修改共享loader", "文档区分启动结构推理检查和待具体模型核验的训练语义"], "mandatory_safeguards": ["stand启动前执行不发布的真实ParkourStandAgent.step，检查ORT结构、状态及TargetJointState shape/finite；缺模型不声称root、joint语义或平衡已验证", "结构不匹配阻止启动；具体模型语义不兼容阻止使用；无可靠字段时明确兼容性前提，不臆造自动检查", "默认dryrun；pose-stand仅显式dryrun，禁止nodryrun组合；缺stand不自动降级", "stand要求有效torso IMU和独立100ms watchdog，禁止pelvis fallback", "保留状态/深度/摇杆/控制时效、20ms deadline、finite、急停及退出停机；publish_lock内复查fault，故障后不发布正常动作", "真实stand模型、ROS、相机、硬件和携箱返回stand动态未验证；mock不替代这些验证"], "minimal_tests": [".venv/bin/python -m unittest discover -s tests -p test_carrybox.py -v", "env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files"], "blockers": ["若具体stand模型不兼容，停止该模型部署；当前缺少该bundle仅阻碍真实模型语义和推理核验，不阻碍离线入口实现"]}
device_actions: []
real_device_authorized: false
---

现有用户授权覆盖本机离线适配；原standdir尚未提供，允许显式dry-run姿态保持检查，实际控制必须提供原stand模型。测试为本地模拟ROS传输，不声称实机验证。
