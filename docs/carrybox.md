# G1 Wall19 搬箱子：深度部署与 s2s

本入口适配指定的 `05_stage5_from15000/model_29999.pt`，checkpoint SHA256 为
`659d56613321bf60706a401e81f3924d6cb2f8eac22bcaaa41fb64a9a8e5b355`。
当前工作站的部署包位于 `models/carrybox_wall19`，无需重新导出即可运行。

## 从cel_instinct分支部署到机载电脑

当前是完成离线适配和标称s2s审计的版本，尚未实机验证。60秒回放存在两次落地，严格持稳未通过；
实际相机外参、IMU/关节标定、传感器时序及模式切换动力学仍需验证。以下是后续部署流程，
先完成模型/环境迁移和dry-run，再在现场验证条件具备后接管电机。

### 1. 拉取代码并迁移模型

在机载电脑选定的工作目录执行：

```bash
git clone --branch cel_instinct --single-branch \
  https://github.com/Por30/instinct_onboard.git
cd instinct_onboard
mkdir -p .cache
```

Git仓库包含代码、文档、测试和回放证据，**不包含被项目忽略的models目录**。
当前工作站已准备模型包 `.cache/carrybox-deploy-models.tar.gz` 及同名 `.sha256` 文件，
包含 `models/carrybox_wall19` 与官方 `models/stand_onboard`，不需要原始训练checkpoint才能运行。
从当前工作站复制到已经克隆代码的机载电脑，替换示例用户名与主机名：

```bash
cd /home/cao/instinct_onboard
scp .cache/carrybox-deploy-models.tar.gz .cache/carrybox-deploy-models.tar.gz.sha256 \
  ROBOT_USER@ROBOT_HOST:~/instinct_onboard/.cache/
```

示例假定机载仓库为 `~/instinct_onboard`；实际克隆位置不同则同步修改目标路径。
在机载仓库根目录校验并解包（首次安装；已有同名模型时先核对版本）：

```bash
sha256sum -c .cache/carrybox-deploy-models.tar.gz.sha256
tar -xzf .cache/carrybox-deploy-models.tar.gz
```

也可直接复制这两个完整模型目录。不要只复制actor，搬箱需要encoder、manifest及仿真资产；
stand还需要原配置文件。不要复制工作站的`.venv`到不同架构的机载电脑。

### 2. 使用原深度locomotion的ROS/Python环境

使用原 `g1_parkour.py` 已能工作的环境，先加载ROS2和Unitree消息工作空间，再激活原机载Python环境。
新机器按项目README安装ROS2、`unitree_hg`/`unitree_go`、对应架构的`crc_module`、RealSense SDK和Python依赖。
在仓库根目录检查实际部署所需的导入和模型前向：

```bash
python -c 'import rclpy, pyrealsense2, cv2, onnxruntime, quaternion; from unitree_hg.msg import LowState, IMUState; from unitree_go.msg import WirelessController; from crc_module import get_crc; from instinct_onboard.agents.parkour_agent import ParkourStandAgent'

python scripts/g1_carrybox.py --bundle models/carrybox_wall19 --offline --steps 50
```

offline仅检查搬箱推理，不启动ROS或相机；官方stand加载检查在下一步ROS入口中执行。
机载推理不需要MuJoCo、PyTorch或训练仓库。需要在新工作站跑s2s时另装`mujoco`；
录制三组审计视频还需`matplotlib`、`imageio`、`imageio-ffmpeg`和`Pillow`。
完整来源对照unittest依赖导出器所指的训练源码、checkpoint及独立参考ONNX，不能在只有部署包的设备上直接复现全部测试。

### 3. 现场标定与dry-run

先核对29DoF机型、关节方向/零位、pelvis与torso IMU路径，以及相机安装外参、SDK视野/深度标尺和采集延迟。
下面的数学和标称回放结果不能代替这些测量。确认ROS可见`/lowstate`、`/secondary_imu`和`/wirelesscontroller`后运行：

```bash
python scripts/g1_carrybox.py \
  --bundle models/carrybox_wall19 \
  --standdir models/stand_onboard
```

多相机时追加`--camera-serial 实际序列号`。默认发布到随机后缀的`/lowcmd_dryrun_*`，不驱动机器人。
使用A等非急停键初始化手柄缓存，检查传感器时效、相机输出、模式日志和L2/R2/B故障锁存；
dry-run不会把机器人移动到冷启动目标，未满足实测到位条件时R1不进入stand，这是预期行为。
相机视野不足、畸变、输入缺失或超时应先解决，不能通过关闭检查来继续。

### 4. 现场接管及原模式操作

完成上述核对、软件急停检查和受支撑验证后，退出dry-run。由现场操作者执行原项目前置操作：
机器人平躺，**L2+R2**停止原运动模式，**L2+A → L2+B**复位关节，然后启动实际电机发布：

```bash
python scripts/g1_carrybox.py \
  --bundle models/carrybox_wall19 \
  --standdir models/stand_onboard \
  --nodryrun
```

用A初始化手柄消息，程序自动cold_start；人工支撑扶正、关节到位后松开再按**R1**进入stand；
站稳后按**L1**进入carrybox，按**R1**返回stand。搬箱没有摇杆速度命令。
程序运行中**L2/R2/B**为急停，不能再次执行上面的OEM组合复位键；Ctrl-C也会退出并关闭电机。
故障锁存后退出并排除原因，再重启。携箱返回原stand可能松手，不能将R1理解为保箱或放箱动作。
本分支没有自动切换OEM运动模式；应用模式流程与固件模式是两回事。

## 直接启动

在项目根目录执行。当前 `.venv` 已配置好 ONNX、MuJoCo 和测试依赖。

```bash
cd /home/cao/instinct_onboard

# MuJoCo 交互仿真，默认运行20秒；空格/Esc停止，R/Backspace重置
.venv/bin/python scripts/g1_carrybox_s2s.py

# 无界面运行并输出结果；--box-xy 可指定箱子初始位置
.venv/bin/python scripts/g1_carrybox_s2s.py --headless --duration 20 \
  --output agent/receipts/carrybox-wall19/s2s.json

# 无ROS、无相机、无电机消息的固定输入推理检查
.venv/bin/python scripts/g1_carrybox.py --offline --steps 50
```

固定输入检查不反馈机器人运动，不能用来判断搬箱效果。s2s 使用真实策略输出推进机器人和箱子动力学。

## 原项目管线及本次适配

`scripts/g1_parkour.py` 将 `RealsenseMPCamera` 与 `UnitreeNode` 组合：相机子进程通过共享内存提供米制深度，
`ParkourAgent` 处理图像与历史，运行深度编码器和 actor，最终由 `ActionTerm` 生成 `TargetJointState`，
`UnitreeNode` 处理限矩、关节映射、CRC 与 ROS 发布。`scripts/depth_latent_publisher.py` 是另一个独立深度 latent 发布入口。

新的 `g1_carrybox.py` 沿用上述相机进程、agent、动作项和 Unitree 发布机制，并保留原来的 cold_start → stand ↔ 任务策略流程。
`CarryBoxPolicy` 完成本体历史、深度历史与两个 ONNX 会话；`CarryBoxAgent` 复用 `JointPositionAction` 和
`TargetJointState`。MuJoCo 使用同一个 `CarryBoxAgent.act()`，不另写一套观测或动作缩放。
只将 `action_term.py` 中的 `RealNode` 导入改为类型检查时导入，让动作项可以脱离 ROS 运行。

| 项目 | Wall19 实际契约 |
| --- | --- |
| 基座 | pelvis；使用 LowState 中骨盆 IMU，不使用 torso IMU |
| 控制 | 策略50Hz；s2s显式PD200Hz，物理步长5ms |
| 本体单帧93维 | gyro×0.25、重力投影、q−default、dq×0.05、上一原始动作29维 |
| 本体历史 | 6个完整93维帧，从旧到新，共558维；每帧clip±100 |
| 深度 | 4×27×48，光轴深度、米制0.1–3m，无归一化；缺失点填3m |
| 完整前向 | encoder128 → geometry12及grasp12 → 与本体558拼成710 → actor29 |
| 抓取预测 | 使用深度latent、预测几何和最新93维本体，保留法向退化回退 |
| 动作 | clip±100后保存为上一动作；目标角=default+0.25×action |
| 历史重置 | 首个当前帧重复填满；上一动作归零 |
| 关节映射 | 训练的pelvis根顺序按名称映射到29个电机；三个腰关节均正号 |

原 `G1_29Dof_TorsoBase` 使用不同顺序和腰部负号；新增的 `G1_29Dof_CarryBox` 独立保存训练限位和力矩限制。
ROS入口的节点保持TorsoBase约定以复用原 `ParkourStandAgent`，在搬箱策略边界按名称重排关节并转换腰部符号。
q/dq和position/velocity/effort转换符号，kp/kd只重排。搬箱推理直接使用pelvis IMU，stand仍使用torso IMU；
不通过改写全局IMU getter切换坐标。MuJoCo继续使用CarryBox配置。
ROS有效限矩取原TorsoBase与重排后搬箱训练限矩的逐项较小值；例如髋roll采用原部署88Nm而非训练139Nm，
腰roll/pitch和踝采用搬箱35Nm而非原部署50Nm。这与s2s训练限矩不完全相同，须在实机验证中单独记录。
本策略不接收速度命令、阶段标志、物体真值、critic或AMP输入。不能把它替换为原parkour的actor，也不能沿用parkour深度归一化。

## 部署包与重新导出

```bash
.venv/bin/python scripts/export_carrybox.py --output models/carrybox_wall19_new
```

导出器默认指向用户指定checkpoint，读取同run的 `params/env.yaml`、`agent.yaml`，以及训练源码中的真实
`DepthCNNEncoder`、`GeometryHead`、`GraspHead` 定义。它不会启动 Isaac Sim。
`--checkpoint`、`--source`、`--urdf`、`--physics-profile` 可以显式指定来源；输出目录必须为空。

包内包含：

- `exported/depth_encoder.onnx`、`exported/actor.onnx`：部署使用的两个图。actor图含geometry/grasp预测头。
- `exported/policy.onnx`：完整前向对照图；三个图均为FP32、opset17、动态batch，控制循环固定batch1。
- `manifest.json`：checkpoint及来源SHA、关节参数、相机、历史和ONNX哈希。
- `robot/g1.urdf`、`robot/meshes`、`physics.json`：独立s2s资产及同checkpoint的实际Isaac标称物理采集。
- `validation.json`：训练前向与分离式ONNX数值对照。

`models/` 已被本项目 `.gitignore` 忽略。迁移机器时应复制整个bundle；部署和s2s运行不读取训练仓库，只有导出及来源对照测试需要来源文件。
物理profile来源于本机 `unitree_rl_lab_carrybox/docs/sim2sim_wall19/isaac_profile.json`，导出器验证其checkpoint、
关节、URDF、USD及控制参数绑定。本次没有重新启动Isaac采集物理参数。

## s2s 场景边界

场景为地面、G1和30×30×25cm、1.125kg标准箱，默认箱中心XY为(1,0)m，无墙柱。
保留训练URDF固定辅助link、肩部capsule碰撞、自碰撞、0.01阻尼和armature，
使用44个body的实际训练质量/COM/惯量，总质量42.341142405kg。该数值含训练辅助link，不能解释为实机称重。

相机挂在torso_link，位置 `[0.0576235,0.01753,0.42987]`m，归一化wxyz旋转为
`[0.91495,0,0.40355,0]` 对应方向，焦距18、水平/垂直孔径35.475779293/19.955125852。
逐像素从光轴0.1m近裁剪面投射射线，包含近距离物体退出面；只使用视觉几何及场景，避免重复渲染碰撞几何。

当前s2s是标称箱子的闭环验证，不重放训练随机化、配对RSI或全部五类物体。MuJoCo与PhysX的接触、摩擦和限速实现仍有差异。
数值异常或越矩视为执行失败；跌倒/倾倒会停止仿真并记录原因，GUI可手动reset。

## 2026-11-25 延长回放与对齐审计

三组相同初态的60秒回放都完成了3000个策略步，未触发跌倒、数值异常或越矩停止。
但三组都出现两次箱子落地后重新抓取，均未达到连续2秒严格持稳。20秒的原始回放不足以证明长期保箱。

| 诊断条件 | 首次连续搬起1秒 | 搬起后落地次数 | 60秒末箱底高度 | 严格持稳2秒 |
| --- | --- | --- | --- | --- |
| 原s2s训练限矩 | 4.54s | 2 | 0.774m | 未通过 |
| 替换为实机有效限矩值 | 4.54s | 2 | 0.774m | 未通过 |
| 有效限矩值加50Hz目标预裁剪 | 4.08s | 2 | 0.759m | 未通过 |

前两组在本初态下轨迹相同，不代表更低限矩对其他工况没有影响。第三组复用实际
`RealNode.clip_by_torque_limit()`，3000步中2395步发生目标裁剪；仍使用MuJoCo的200Hz PD和硬限矩，
不能视为真实电机链复现。箱子倾斜是严格持稳失败的主要条件，落地期间也失去双手接触。

视频：[原s2s](../agent/receipts/carrybox-audit-20261125/baseline.mp4)、
[部署限矩](../agent/receipts/carrybox-audit-20261125/deployment_limits.mp4)、
[目标预裁剪](../agent/receipts/carrybox-audit-20261125/target_clipped.mp4)。
[全程曲线](../agent/receipts/carrybox-audit-20261125/comparison.png)与
[详细JSON](../agent/receipts/carrybox-audit-20261125/summary.json)保存于同目录。
视频右下角显示最近一次策略实际使用的深度帧；比显示的物理状态早一个20ms控制周期。

| 对齐项目 | 当前结论 |
| --- | --- |
| 本体输入、历史、动作、ONNX | 已做训练源码/独立ONNX与ROS模拟消息对照；真实关节零位和IMU轴向未测量 |
| 深度值与内参采样 | 米制光轴深度、范围、4帧历史及训练射线一致；读取SDK真实内参，视野不足或非零畸变会拒绝运行 |
| 相机外参 | **实机未对齐确认**：入口没有使用或校验相机相对torso的安装位置/旋转 |
| 传感器时序 | **存在差异**：仿真50Hz同步新帧；实机50Hz取60FPS最新帧，可重复且未与lowstate采集时刻同步 |
| 控制链 | **存在差异**：hip_roll有效上限139→88Nm，实机50Hz目标预裁剪与仿真200Hz直接限矩不同 |
| 模式切换 | 按键和历史重置已测；cold_start→stand→carrybox及携箱返回stand的动力学未验证 |

训练相机需要相对torso位置`[0.0576235,0.01753,0.42987]`m、上述wxyz旋转（向下约47.60°）。
完整针孔视场约89.16°×58°，最外侧像素中心覆盖约87.95°×56.18°。
**这些是训练要求，不是实机标定结果。** 内参重采样不能弥补不同安装位置、俯仰角或缺失视野。
拿到设备后需要核对SDK实际内参/深度标尺、安装外参、IMU与关节零位，并测量采集时刻/端到端延迟。
真实近场空洞、遮挡和噪声的分布也没有被当前理想射线相机验证。

本次还发现原s2s指标与训练定义有差异：髋部停止条件取hip_pitch而非hip_yaw；strict使用world-z角速度
及pelvis COM线速度而非link局部yaw及link原点线速度；箱中心阈值为`>0.7`而非`>=0.7`；
手接触力累计法向绝对值，而训练使用Box过滤后的法向合力向量范数。
审计脚本另按训练语义重算，并同时保留原指标，额外检查训练hip_yaw停止条件；
未修改生产仿真实现。这些差异不改变本轮“未严格持稳且落地两次”的结论，后续需修正生产指标。

复现本次三组诊断（写入上述视频与JSON，不连接设备）：

```bash
env MUJOCO_GL=egl .venv/bin/python agent/receipts/carrybox-audit-20261125/evaluate.py
```

## ROS入口及待实机验证项

按原项目环境准备ROS2、`unitree_hg`/`unitree_go`消息、CRC模块、RealSense和相应Python依赖。
提供原深度locomotion所用、与 `G1_29Dof_TorsoBase` 兼容的stand模型目录：

```bash
python scripts/g1_carrybox.py --bundle models/carrybox_wall19 --standdir models/stand_onboard

# 当前无stand模型时，仅用于ROS传输dry-run的有界PD姿态保持检查
python scripts/g1_carrybox.py --bundle models/carrybox_wall19 --pose-stand
```

默认保留dry-run，只向随机后缀的dry-run话题发布；只有显式 `--nodryrun` 才进入实际电机命令话题。
`--pose-stand`与`--nodryrun`互斥，不是平衡站立策略。缺少stand目录时不会自动退化为姿态保持。
stand目录需要 `params/env.yaml`、`params/agent.yaml`、`exported/actor.onnx`、`exported/0-depth_encoder.onnx`。
入口检查文件存在，加载原agent，并在启动控制计时器前执行一次不发布的stand推理检查输入输出结构与有限值。
旧格式不保证包含根坐标、关节顺序元数据；这些语义仍须对具体原stand模型核对，不能拿任意G1模型替代。

### 已下载的官方stand模型

`models/stand_onboard` 来自 [Hiking in the Wild官网](https://project-instinct.github.io/hiking-in-the-wild/) 的
[Data & Model压缩包](https://drive.google.com/file/d/10tQylYHdKLVDVnmVHrygLB70neHnPdoF/view)。
压缩包SHA256为 `bbba90bdb77bbab19e74cbe9f556ea0b9330ea9d125ad8271d431aa0e37a6609`，模型逐文件哈希见
`models/stand_onboard/provenance.json` 和 `agent/receipts/carrybox-stand/provenance.json`。模型和配置保持原字节。
迁移机器时需同时复制这个目录；`models/`被Git忽略。

官方stand encoder输入为 `[1,8,18,32]`、输出128维；actor输入896维（8帧×96维本体加128维深度latent），输出29动作。
这与搬箱输入不同，两者使用独立agent和历史。stand仍由原ParkourStandAgent生成全零深度，
因此不取搬箱相机的27×48像素；不能把这套stand图像预处理移用到搬箱策略。
官方 `agent.yaml` 本来就是空文件，当前loader仅读取保存而不使用它；已用真实模型加载验证。
新入口仅覆盖stand的关节速度getter返回副本，避免原观测原地×0.05后污染共享dq及后续搬箱推理。

### 官方原实机操作顺序

以下顺序来自包内 `models/stand_onboard/UPSTREAM_README.md`，本轮只核对，未操作实机：

1. 程序启动前，机器人平躺；按 **L2+R2** 停止原运动模式，再按 **L2+A**、**L2+B** 复位关节。
2. 启动部署入口。原说明写“任意按键”初始化手柄缓存；新入口应使用 **A等非急停键**，因为L2/R2/B会立即停机。
3. 程序自动冷启动后，人工扶正机器人；到位后重新按 **R1** 接入站立策略。
4. 站稳后按 **L1** 接入搬箱策略；需要返回stand时按 **R1**。

复位组合键属于程序启动前的OEM操作，不能在新入口运行中重复执行。官方原步骤最后的摇杆行走操作仅适用于parkour；
当前搬箱checkpoint没有速度命令输入。官方README还要求核对29自由度机型、相机安装，并建议使用鞋提高摩擦。

### 模式与原入口对照

| 步骤/按键 | 原 `g1_parkour.py` | 搬箱入口 |
| --- | --- | --- |
| 启动且消息就绪 | 自动进入ColdStartAgent | 相同；目标为搬箱训练默认姿态 |
| 冷启动到位后R1 | 进入stand | 相同，使用原ParkourStandAgent |
| stand中L1 | 进入parkour | 进入carrybox，重置本体/深度历史和上一动作 |
| 任务中R1 | 返回stand | 返回stand，并清空旧stand历史；当tick不再运行搬箱推理 |
| L2/R2 | 软件急停 | 保留；额外支持B |
| 摇杆轴 | 给原策略速度命令 | stand保持零速度命令；搬箱策略没有速度命令输入 |

与原入口相比，模式键使用新按下沿，避免长按跨模式触发。冷启动未到位时R1无效，需到位后松开重按。
R1+L1同时按下不会开启搬箱；搬箱中同时按下以R1返回stand为先。每tick最多一次模式切换。
`--startup_step_size 0.2`保留原参数名和默认值：每步目标相对**当前实测角度**最多偏移0.2rad，不是0.2rad/s。
`--kpkd_factor 2.0`只影响cold_start。入口不传主策略动作项，使用ColdStartAgent自带动作项，让增益倍率实际生效；
原入口传入既有动作项时会沿用动作项增益。最终增益仍受RealNode的kp/kd限制。

先在dry-run中检查 `/lowstate`、`/secondary_imu`、`/wirelesscontroller` 和相机消息、上述流程及急停。
真正接管电机时需在现场按原项目/OEM操作准备低层控制并显式加 `--nodryrun`；本轮未执行这一步。
脚本里的cold_start/stand/carrybox是**应用策略模式**，不是机器人固件运动模式。
仍由UnitreeNode使用 `mode_pr=0`，从LowState复制 `mode_machine`、生成CRC并发布；未新增SportMode切换服务。
原parkour文档提及“方向键直接进入任务”，但当前实际状态机没有这条路径，本入口也不添加。

L2/R2/B立即停机；Ctrl-C、退出和异常均关闭电机。
故障锁存，必须退出后重新启动。相机使用480×270@60FPS，按SDK实际内参采样训练射线；支持 `--camera-serial`。
有非零畸变系数时拒绝运行，需先提供正确的整流方案，不能用简单缩图替代标定。

检查state100ms、joystick500ms、depth100ms和control100ms时效；加载原stand时还要求torso IMU 100ms时效，
禁止缺失时回退到pelvis IMU。单次控制超过20ms不发布迟到动作。
后台watchdog处理控制循环阻塞；相机检查生产帧时间与帧号，并在复制前后检查写入状态。
当前相机时间为主机接收时间，尚未实测传感器采集延迟。软件watchdog也不代替机器人硬件急停或设备级通信保护。

本轮无实机、无ROS2运行环境：ROS入口用stub消息/传输验证控制分支。官方stand下载后，另用实际ColdStartAgent、
ParkourStandAgent、CircularBuffer及两套真实ONNX完成模式集成测试，覆盖非零dq不被stand缩放污染。
这验证了模型加载、输入输出和入口切换，未实际启动ROS、相机或电机，未验证stand动力学平衡效果。
携箱返回原locomotion stand是否会松手/失稳尚未验证；R1返回stand不能解释为放箱或保箱策略。
上机前仍需核对pelvis IMU对齐、关节方向/零位、实际质量和限矩、相机内外参及采集延迟，完成现场急停和受支撑测试。

## 验证

```bash
.venv/bin/python -m unittest discover -s tests -p test_carrybox.py -v
env PRE_COMMIT_HOME=.cache/pre-commit .venv/bin/pre-commit run --all-files
```

来源对照覆盖原训练特征函数与既有独立ONNX的batch1/3输出、预测头、历史、原始上一动作、关节映射、
近裁剪面、44body惯量、限矩，以及模拟ROS传输下的失联、急停、推理失败和超时。
机器的旧Git与pre-commit4.7不兼容，项目内环境使用pre-commit3.8.0；未更改全局环境。

最初适配结果见 `agent/report/carrybox-wall19.md` 与 `agent/receipts/carrybox-wall19/`。
模式对齐补充见 `agent/report/carrybox-modes.md` 与 `agent/receipts/carrybox-modes/`。
官方下载及真实stand离线验证见 `agent/report/carrybox-stand.md` 与 `agent/receipts/carrybox-stand/`。
