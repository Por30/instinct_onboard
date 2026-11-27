# G1 Wall19 机载容器

适用于 Ubuntu 22.04、ARM64 的 G1 Jetson。Humble、CycloneDDS、Unitree 消息、CRC 和 Python 依赖装在镜像内。运行时以只读方式挂载项目。宿主机需要已有 Docker、Unitree SDK2、g++ 和 `lsusb`、`udevadm`、`fuser` 等工具。当前部署使用 D435i USB ID `8086:0b3a`、G1 网卡 `enP8p1s0` 和 DDS 域 0。

## 构建和检查

在能访问依赖仓库的机器上准备构建上下文。在 Jetson 或兼容的 Linux ARM64 Docker 构建机上构建镜像。

```bash
bash deployment/humble/prepare-build.sh
docker build --platform linux/arm64 \
  -t instinct-carrybox:wall19-humble-1264316 \
  .deployment/humble/build-context
```

如果 Jetson 无法下载依赖，可在联网的 ARM64 构建机上用 `docker save` 导出镜像，再传到 Jetson 用 `docker load` 导入。构建上下文中的 `sources.txt` 记录 Unitree ROS 2、ros2_numpy 和 CRC 的源码提交。

在 Jetson 的仓库根目录校验并首次解包模型。然后用机载 SDK2 编译运控工具并验证容器。

```bash
sha256sum -c deployment/carrybox-models.tar.gz.sha256 &&
  tar -k -xzf deployment/carrybox-models.tar.gz

bash deployment/humble/build-factory-motion.sh "$HOME/unitree_sdk2-main"
bash deployment/humble/run.sh offline
bash deployment/humble/run.sh check
```

`offline` 应输出参考 checkpoint SHA `659d5661…` 和 `motor_messages=0`。`check` 校验 stand 推理、容器内 ROS 回环、Unitree 消息和 CRC。这两项都不连接机器人网络或相机。

## 深度和 dry-run

待 D435i 空闲时运行预览，命令会输出 PNG 和 NumPy 张量的保存目录。预览复用实机相机采样和策略历史构造，以 50 Hz 生成从旧到新的四帧 `[1,4,27,48]` 光轴深度。灰度图的白色表示 3 米或被填为 3 米的无效值。

```bash
bash deployment/humble/run.sh depth-preview
bash deployment/humble/run.sh dry-run
```

dry-run 启动后按一次 A 提供手柄消息。验证节点进入 `cold_start`、只发布到 `/lowcmd_dryrun_*`，再按 B 验证软件停机。手柄静置没有消息时，运行中的节点会继续控制循环。stand 使用全零深度，切到 carrybox 后才使用 D435i 深度历史。

## 真机启动

确认实验室已交接机器人和相机，其他控制器已退出，防坠支撑与独立停机手段就绪。首轮空载验证站立和停机。

```bash
bash deployment/humble/run.sh live
```

启动器检查本项目容器和 D435i 是否已被占用，运行三步离线检查，然后通过 Unitree 运控服务释放原厂模式。只有服务确认释放后才以 `--nodryrun` 启动策略。释放时机器人可能失去站立支撑，输入就绪后 `cold_start` 会自动驱动关节。

| 按键 | 操作 |
| --- | --- |
| A | 让节点收到启动所需的手柄消息 |
| R1 | 冷启动到位后进入 stand，或从 carrybox 返回 stand |
| L1 | 已站稳时从 stand 切入 carrybox |
| L2、R2 或 B | 禁用电机并退出 |

手柄断联本身不会触发软件停机。切回 stand 时可能松手。结束后按实验室流程恢复原厂模式。见 [实机观测验收和运行限制](../../docs/carrybox.md#3-现场标定与dry-run)。
