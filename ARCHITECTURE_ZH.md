# Pupper V3 工程架构文档

> 本文档对 Pupper V3 四足机器人 monorepo 进行全面解析，涵盖项目结构、核心架构、各子系统实现细节、数据流与部署流程。

---

## 1. 项目概述

**Pupper V3** 是一台小型四足机器人，具备以下核心能力：

| 能力 | 实现方式 |
|------|----------|
| **运动控制** | 神经网络策略（强化学习训练）+ ROS2 控制框架 |
| **仿真** | MuJoCo 物理仿真 + ROS2 硬件接口模拟 |
| **视觉感知** | Hailo AI 加速器 + 鱼眼相机 + 人物检测/跟随 |
| **语音交互** | OpenAI Realtime API + WebSocket 语音助手 |
| **表情系统** | Rust GUI 应用（egui），支持眨眼、眼球追踪、人物跟随 |
| **动画系统** | 基于 CSV 关键帧的动画控制器，支持录制/回放 |
| **硬件平台** | Raspberry Pi 5 + 自定义控制板 + CAN 总线舵机 |

### 技术栈总览

```
语言:      C++ (ROS2 控制器/硬件接口), Python (AI/工具), Rust (GUI), TypeScript (Web UI)
框架:      ROS2 Jazzy (机器人中间件), MuJoCo/MJX (仿真), JAX/Brax (RL 训练)
硬件:      Raspberry Pi 5, Hailo-8L AI 加速器, 自定义 CAN 控制板
通信:      ROS2 Topic/Service, WebSocket, ZMQ, CAN bus
构建:      colcon (ROS2), Cargo (Rust), uv (Python), npm (TypeScript)
```

---

## 2. 目录结构

```
pupperv3-monorepo/
├── ai/                          # AI 相关代码
│   ├── rl/                      # 强化学习训练（MuJoCo MJX + JAX/Brax）
│   │   ├── pupper_mjx_rl_training.py   # 主训练脚本
│   │   ├── pupper_mjx_rl_use_this.py   # 训练入口
│   │   ├── conf/                       # Hydra 配置（仿真/训练/策略/奖励/导出）
│   │   └── pyproject.toml              # uv 管理的 Python 依赖
│   ├── llm-ui/                  # LLM 语音助手前端
│   │   ├── live-audio/          # 实时语音交互 Web 应用（Vite + TypeScript）
│   │   ├── live-audio-original/ # 原始版本
│   │   ├── agent-starter-python/# Python agent 启动器
│   │   ├── moonshine-test/      # Moonshine 语音识别测试
│   │   └── ui-rs/               # Rust 版 UI（实验性）
│   └── playground/              # 实验性项目
│       ├── vlm-nav/             # 视觉语言模型导航
│       ├── undistory/           # 图像去畸变
│       └── ...
├── ros2_ws/                     # ROS2 工作空间
│   ├── build.sh                 # 构建脚本（colcon build）
│   ├── src/                     # ROS2 包源码（15 个包）
│   │   ├── neural_controller/   # 神经网络运动控制器（C++）
│   │   ├── control_board_hardware_interface/  # 硬件接口（CAN 总线 + IMU）
│   │   ├── pupper_v3_description/ # URDF/MuJoCo 模型文件
│   │   ├── pupperv3_mujoco_sim/ # MuJoCo 仿真硬件接口
│   │   ├── animation_controller_py/  # 动画播放控制器
│   │   ├── openai_bridge/       # OpenAI Realtime API 桥接
│   │   ├── llm_websocket_server/# LLM WebSocket 服务器
│   │   ├── hailo/               # Hailo AI 视觉检测
│   │   ├── person_follower/     # 人物跟随节点
│   │   ├── cmd_vel_mux/         # 速度指令多路复用器
│   │   ├── bag_recorder/        # 手柄触发录制 MCAP 数据包
│   │   ├── imu_to_tf/           # IMU 数据转 TF 变换
│   │   ├── joy_utils/           # 手柄工具（急停/控制器切换）
│   │   ├── pupper_feelings/     # 表情控制（终端版）
│   │   └── real2sim_controller/ # Sim2Real 控制器变体
│   └── test_animation_system.py # 动画系统测试
├── pupper-rs/                   # Rust GUI 应用（机器人表情界面）
│   ├── src/
│   │   ├── main.rs              # 主入口（egui 应用）
│   │   ├── config.rs            # TOML 配置解析
│   │   ├── detection.rs         # ZMQ 人物检测接收器
│   │   ├── eyes/                # 眼睛动画（绘制/追踪/眨眼）
│   │   ├── system/              # 系统监控（电池/CPU/服务/网络）
│   │   └── ui/                  # UI 组件（状态栏/电池指示器）
│   ├── config.toml              # GUI 配置文件
│   └── pupper-gui.service       # systemd 服务文件
├── robot/                       # 机器人部署配置
│   ├── services/                # systemd 服务（音量最大化的服务）
│   ├── utils/                   # 部署工具
│   │   ├── robot.service        # 机器人主服务
│   │   ├── robot.sh             # 启动脚本
│   │   ├── battery_monitor.service # 电池监控服务
│   │   ├── pair_ps5_controller.sh   # PS5 手柄配对脚本
│   │   └── ...
│   └── start_ui.sh              # 开发用 tmux 启动脚本
├── infra/                       # 基础设施
│   └── pupper_image_builder/    # Packer 构建树莓派镜像
│       ├── pios_base_arm64.pkr.hcl   # 基础镜像
│       ├── pios_full_arm64.pkr.hcl   # 完整镜像
│       ├── pios_ai_arm64.pkr.hcl     # AI 扩展镜像
│       └── setup_scripts/            # 镜像配置脚本
├── bags/                        # 录制的 MCAP 动画数据包
├── scripts/                     # 工具脚本
│   ├── mcap_to_csv.py           # MCAP 转 CSV
│   ├── animation_editor/        # 动画编辑器
│   └── record_all_except_raw_camera.sh # 录制脚本
├── analysis/                    # 数据分析工具
│   └── histogram.py
├── install_dev_dependencies.sh  # 开发环境安装脚本
├── stop_all_services.sh         # 停止所有服务
└── llm_logs.sh                  # 查看 LLM agent 日志
```

---

## 3. 系统架构

### 3.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                      Pupper V3 系统架构                          │
├─────────────┬───────────────────────────────────────────────────┤
│             │                                                   │
│   用户交互层 │  PS5 手柄 ──→ joy_linux ──→ teleop_twist_joy     │
│             │  语音助手 ──→ live-audio ──→ WebSocket Server     │
│             │                                                   │
├─────────────┼───────────────────────────────────────────────────┤
│             │                                                   │
│   指令调度层 │  cmd_vel_mux ──→ /cmd_vel (优先级多路复用)        │
│             │  joy_utils ──→ 控制器激活/急停                     │
│             │                                                   │
├─────────────┼───────────────────────────────────────────────────┤
│             │                                                   │
│   控制层     │  neural_controller (RTNeural 实时推理)            │
│             │  animation_controller (关键帧动画)                 │
│             │                                                   │
├─────────────┼───────────────────────────────────────────────────┤
│             │                                                   │
│   硬件抽象层 │  ros2_control 框架                                │
│             │  ├─ control_board_hardware_interface (真实硬件)    │
│             │  └─ pupperv3_mujoco_sim (仿真)                    │
│             │                                                   │
├─────────────┼───────────────────────────────────────────────────┤
│             │                                                   │
│   硬件层     │  CAN 总线 (12 个舵机) + IMU + 相机 + Hailo AI    │
│             │                                                   │
├─────────────┼───────────────────────────────────────────────────┤
│             │                                                   │
│   感知层     │  Hailo 检测 ──→ person_follower ──→ /cmd_vel     │
│             │  ZMQ ──→ pupper-rs (眼球追踪)                     │
│             │                                                   │
├─────────────┼───────────────────────────────────────────────────┤
│             │                                                   │
│   表情界面层 │  pupper-rs (Rust egui 全屏应用)                   │
│             │  电池/CPU/服务状态 + 眼睛动画 + 人物追踪           │
│             │                                                   │
└─────────────┴───────────────────────────────────────────────────┘
```

### 3.2 ROS2 节点拓扑

```
[PS5 手柄]
    │
    ▼
[joy_linux_node] ──→ /joy (传感器消息)
    │                       │
    ▼                       ▼
[teleop_twist_joy]    [joy_utils/estop_controller]
    │                       │
    ▼                       ├── 急停: /emergency_stop
[/teleop_cmd_vel]           └── 控制器切换: controller_manager service
    │
    ▼
[cmd_vel_mux_node] ←── /llm_cmd_vel (来自 LLM WebSocket Server)
    │
    ▼
[/cmd_vel]
    │
    ▼
[controller_manager/ros2_control_node]
    │                        ▲
    │  ┌─────────────────────┼──────────────────────┐
    │  │                     │                      │
    ▼  ▼                     ▼                      ▼
[neural_controller]  [animation_controller]  [forward_*_controller]
    │                     │                      │
    ▼                     ▼                      ▼
[hardware_interface] ─────→ CAN 总线 → 12 个关节舵机
    │
    ├─ 关节状态 (position/velocity/effort)
    └─ IMU 数据 (orientation/angular_velocity/linear_acceleration)
```

---

## 4. 核心子系统详解

### 4.1 神经网络运动控制器 (`neural_controller`)

**语言**: C++  
**框架**: ros2_control ControllerInterface + RTNeural  
**位置**: `ros2_ws/src/neural_controller/`

这是整个系统的核心控制器，负责在实时控制循环中运行神经网络策略。

#### 工作流程

```
1. 初始化阶段 (init_duration: 1.0s)
   └─ 从当前关节位置平滑插值到 default_joint_pos

2. 淡入阶段 (fade_in_duration: 1.0s)
   └─ 策略输出从 0 逐渐过渡到 100%

3. 正常运行阶段
   └─ 循环执行: 观测 → 推理 → 动作
```

#### 观测向量（输入）

| 索引 | 内容 | 来源 |
|------|------|------|
| 0-2 | 角速度 (ωx, ωy, ωz) | IMU angular_velocity |
| 3-5 | 投影重力向量 (gx, gy, gz) | IMU 四元数 → 旋转矩阵逆变换 |
| 6-8 | 速度指令 (vx, vy, ωz) | /cmd_vel |
| 9-11 | 期望姿态向量 | /cmd_pose |
| 12-23 | 关节位置偏差 (12 关节) | hardware_interface position - default_joint_pos |
| 24-35 | 上一步动作 (12 关节) | 策略输出反馈 |
| ... | 历史观测 (observation_history 份) | 延迟缓冲区 |

**观测历史**: `observation_history` 份历史叠加，模型输入形状为 `[1, observation_history * single_obs_size]`。

#### 动作向量（输出）

12 个关节的目标位置/速度，分两种模式：
- **position 模式**: `action * scale + default_joint_pos`，夹紧到关节限位
- **velocity 模式**: `action * scale`

#### 安全机制

- **急停 (E-Stop)**: 接收 `/emergency_stop` 后所有关节阻尼制动
- **身体角度限制**: 投影重力向量 z 分量 < cos(max_body_angle) 时触发急停
- **NaN 检测**: 观测/动作中出现 NaN 立即报错
- **观测限幅**: 所有观测值 clamp 到 `[-observation_limit, observation_limit]`

#### 配置 (`config.yaml`)

```yaml
neural_controller:
  ros__parameters:
    repeat_action: 10           # 每个动作重复 10 个控制周期 (520Hz / 10 = 52Hz 策略频率)
    gain_multiplier: 1.0         # 增益缩放因子（补偿 sim2real gap）
    estop_kd: 0.1               # 急停时的阻尼系数
    init_duration: 1.0           # 初始化过渡时间
    fade_in_duration: 1.0        # 策略淡入时间
    max_body_angle: 1.5          # 最大身体倾斜角 (弧度)
    model_path: "policy_latest.json"  # 策略文件路径
```

#### 关节配置

12 个关节，对应 4 条腿，每条腿 3 个关节：

```
leg_front_r (右前): [hip, knee, wheel]   → [leg_front_r_1, leg_front_r_2, leg_front_r_3]
leg_front_l (左前): [hip, knee, wheel]   → [leg_front_l_1, leg_front_l_2, leg_front_l_3]
leg_back_r  (右后): [hip, knee, wheel]   → [leg_back_r_1, leg_back_r_2, leg_back_r_3]
leg_back_l  (左后): [hip, knee, wheel]   → [leg_back_l_1, leg_back_l_2, leg_back_l_3]
```

默认站立姿态: `[0.26, 0.0, -0.52, -0.26, 0.0, 0.52, 0.26, 0.0, -0.52, -0.26, 0.0, 0.52]`

---

### 4.2 硬件接口 (`control_board_hardware_interface`)

**语言**: C++  
**位置**: `ros2_ws/src/control_board_hardware_interface/`

ros2_control 的硬件接口插件，直接与物理硬件通信。

#### 硬件通信

- **CAN 总线**: 通过 Linux SocketCAN 与舵机通信
- **IMU**: 读取加速度计和陀螺仪数据
- **协议**: Cheetah CAN 协议（与 MIT Cheetah 系列兼容）

#### 关节接口

每个关节提供以下接口：

| 命令接口 | 说明 |
|----------|------|
| `position` | 目标位置（缩放后） |
| `velocity` | 目标速度 |
| `effort` | 目标力矩 |
| `kp` | 位置增益 |
| `kd` | 速度增益（阻尼） |

| 状态接口 | 说明 |
|----------|------|
| `position` | 当前关节位置 |
| `velocity` | 当前关节速度 |
| `effort` | 当前力矩 |

#### URDF 配置参数

```xml
<joint name="joint_1">
    <param name="can_channel">1</param>        <!-- CAN 通道 -->
    <param name="can_id">1</param>             <!-- CAN ID -->
    <param name="can_protocol">cheetah</param>  <!-- 通信协议 -->
    <param name="position_scale">95.5</param>   <!-- 位置缩放 -->
    <param name="velocity_scale">30.0</param>   <!-- 速度缩放 -->
    <param name="effort_scale">18.0</param>     <!-- 力矩缩放 -->
    <param name="kp_scale">500.0</param>        <!-- kp 缩放 -->
    <param name="kd_scale">5.0</param>          <!-- kd 缩放 -->
    <param name="axis_direction">-1</param>      <!-- 轴方向 -->
    <param name="position_offset">0.0</param>   <!-- 位置偏移 -->
</joint>
```

---

### 4.3 MuJoCo 仿真 (`pupperv3_mujoco_sim`)

**语言**: C++  
**位置**: `ros2_ws/src/pupperv3_mujoco_sim/`

提供 MuJoCo 物理仿真作为 ros2_control 硬件接口，使同一套控制代码无需修改即可在仿真中运行。

- 支持浮基（floating base）和固基（fixed base）模式
- 机器人模型: `pupper_v3_description/description/mujoco_xml/pupper_v3_complete.xml`
- 依赖 MuJoCo 2.3.1（ARM 原生 / x86 需手动替换）

启动仿真:
```bash
ros2 launch neural_controller launch.py sim:=True
```

---

### 4.4 强化学习训练 (`ai/rl`)

**语言**: Python  
**位置**: `ai/rl/`  
**框架**: JAX + Brax + MuJoCo MJX + WandB

#### 训练流程

```
pupper_mjx_rl_training.py
├── SystemChecker
│   ├── check_gpu()            # GPU/环境验证
│   ├── setup_nvidia_egl()     # EGL 渲染配置
│   └── verify_mujoco()        # MuJoCo 许可证检查
├── ModelManager
│   ├── setup_repositories()   # 克隆 pupperv3_mjx 仓库
│   ├── modify_model()         # 修改模型参数
│   └── _add_height_field()    # 添加地形高度场
└── Trainer
    ├── setup_wandb()           # WandB 实验追踪
    ├── benchmark_model()       # 性能基准测试
    ├── create_environment()    # 创建 MJX 仿真环境
    ├── train()                 # PPO 训练循环
    └── export_policy()         # 导出策略为 JSON 格式
```

#### Hydra 配置结构

```
conf/
├── config.yaml                # 主配置（组合其他配置）
├── simulation/default.yaml    # 仿真参数
├── training/default.yaml      # PPO 训练参数
├── policy/default.yaml        # 策略网络结构
├── reward/default.yaml        # 奖励函数权重
└── export/default.yaml        # 导出设置
```

#### 使用方式

```bash
# 基础训练
uv run python pupper_mjx_rl_training.py

# 覆盖参数
uv run python pupper_mjx_rl_training.py training.ppo.num_timesteps=100000000

# 从检查点恢复
uv run python pupper_mjx_rl_training.py training.checkpoint_run_number=238

# 导出的策略文件用于 neural_controller
```

#### 策略导出

训练完成后策略导出为 JSON 格式（RTNeural 兼容），放入 `ros2_ws/src/neural_controller/launch/` 目录，在 `config.yaml` 中指定 `model_path` 即可部署。

也可从 WandB 下载最新策略：
```bash
python3 download_latest_policy.py
```

---

### 4.5 速度指令多路复用器 (`cmd_vel_mux`)

**语言**: C++  
**位置**: `ros2_ws/src/cmd_vel_mux/`

解决多个速度指令源的冲突问题，将优先级最高的有效指令转发到 `/cmd_vel`。

#### 输入源

| 话题 | 优先级 | 来源 |
|------|--------|------|
| `/teleop_cmd_vel` | 高 | 手柄遥控 |
| `/llm_cmd_vel` | 中 | LLM 语音助手 |
| `/person_follow_cmd_vel` | 低 | 人物跟随 |

#### 参数

```yaml
cmd_vel_mux:
  ros__parameters:
    deadband: 0.05              # 死区阈值
    joystick_timeout_ms: 500    # 手柄超时
```

---

### 4.6 手柄工具 (`joy_utils`)

**语言**: C++  
**位置**: `ros2_ws/src/joy_utils/`

处理 PS5 手柄的特殊按键功能：

- **急停**: PS 按钮 (index 12) → 发布 `/emergency_stop`
- **急停释放**: Options 按钮 (index 9) → 解除急停
- **控制器切换**: △/○ 按钮 (index 0/1) → 在控制器间切换
  - neural_controller ↔ neural_controller_three_legged ↔ forward_*_controller

#### 支持的控制器列表

```yaml
controller_names:
  - neural_controller
  - neural_controller_three_legged
  - forward_kp_controller
  - forward_kd_controller
  - forward_position_controller
```

---

### 4.7 动画控制器 (`animation_controller_py`)

**语言**: Python  
**位置**: `ros2_ws/src/animation_controller_py/`

基于 CSV 关键帧的动画回放系统，通过 `forward_position_controller`、`forward_kp_controller`、`forward_kd_controller` 发送关节指令。

#### 工作流程

```
1. CSV 关键帧文件 → 解析为关节轨迹
2. 按 frame_rate (40fps) 插值
3. 通过 forward_*_controller 发送关节目标
4. init_duration 时间内平滑过渡到第一帧
```

#### 动画制作流程

```
1. 长按 L1 → 开始 MCAP 录制
2. 手动操控机器人完成目标动作
3. 按 R1 → 停止录制
4. 用 Foxglove 验证动画
5. mcap_to_csv.py 转换为 CSV
6. CSV 放入 animation_controller_py/launch/animations/
7. 重新构建
```

#### 预置动画

`bags/` 目录中包含 16 个预录动画：
- 趴下 (lie_down)、坐下 (sit)、握手 (shake)
- 俯卧撑 (push_up)、游泳 (swim)、超人 (superman)
- 打喷嚏 (sneeze)、挠痒 (twerk)、蜘蛛 (spider)
- 下犬式 (downward_dog)、倒 V (upward_dog) 等

---

### 4.8 视觉检测系统 (`hailo`)

**语言**: Python  
**位置**: `ros2_ws/src/hailo/`

利用 Hailo-8L AI 加速器进行实时物体检测。

#### 模块

| 文件 | 功能 |
|------|------|
| `hailo_detection.py` | 人物检测 ROS2 节点 |
| `hailo_inference.py` | Hailo 推理封装 |
| `hailo_depth.py` | 深度估计 |
| `mock_camera.py` | 模拟相机（仿真用） |
| `fisheye_utils.py` | 鱼眼镜头畸变校正 |

#### 输出

- 检测结果发布到 ROS2 话题
- 同时通过 ZMQ (`tcp://127.0.0.1:5556`) 广播给 pupper-rs GUI 用于眼球追踪

#### 相机配置

```yaml
camera:
  ros__parameters:
    FrameDurationLimits: [200000, 200000]  # 20fps
    format: "RGB888"
    width: 1400
    height: 1050
```

---

### 4.9 人物跟随 (`person_follower`)

**语言**: Python  
**位置**: `ros2_ws/src/person_follower/`

接收 Hailo 人物检测结果，计算跟踪速度指令并发送到 `/person_follow_cmd_vel`。

---

### 4.10 OpenAI 桥接 (`openai_bridge`)

**语言**: Python  
**位置**: `ros2_ws/src/openai_bridge/`

连接 OpenAI Realtime API 的 ROS2 节点。

| 文件 | 功能 |
|------|------|
| `realtime_client.py` | OpenAI Realtime API 客户端 |
| `realtime_client_class.py` | API 客户端类封装 |
| `ros_node.py` | ROS2 节点适配 |
| `audio_util.py` | 音频处理工具 |

---

### 4.11 LLM WebSocket 服务器 (`llm_websocket_server`)

**语言**: Python  
**位置**: `ros2_ws/src/llm_websocket_server/`

为 Web 前端提供 WebSocket 接口（`localhost:8765`），将语音指令翻译为机器人控制命令。

#### 支持的命令

| 命令 | 功能 | ROS2 操作 |
|------|------|-----------|
| `activate` | 启动机器人控制器 | controller_manager activate |
| `deactivate` | 停止机器人控制器 | controller_manager deactivate |
| `move` | 控制移动 | 发布到 `/llm_cmd_vel` |
| `get_battery` | 获取电池状态 | 调用 `check_batt_voltage.py` |
| `status` | 获取机器人状态 | 综合查询 |

#### 速度约束

```
vx (前后): ±0.75 m/s，最小 0.2 m/s
vy (左右): ±0.5 m/s，最小 0.2 m/s
wz (旋转): ±2.0 rad/s
```

#### 架构

```
Live-Audio Web App (WebSocket Client)
    ↓ JSON Messages
WebSocket Server (localhost:8765)
    ↓ ROS2 Topics/Services
Robot Controllers & Hardware
```

---

### 4.12 Rust GUI 应用 (`pupper-rs`)

**语言**: Rust  
**位置**: `pupper-rs/`  
**框架**: egui + eframe

运行在树莓派上的全屏 GUI 应用，展示机器人的"面部表情"。

#### 功能模块

```
pupper-rs/src/
├── main.rs            # 应用入口，管理所有子系统
├── config.rs          # TOML 配置（电池/眨眼/眼追踪等）
├── detection.rs       # ZMQ 接收人物检测数据
├── eyes/
│   ├── animation.rs   # 眨眼动画（黑框下落）
│   ├── drawing.rs     # 眼睛/眉毛绘制
│   ├── tracking.rs    # 瞳孔/眼球追踪
│   └── mod.rs
├── system/
│   ├── battery.rs     # 电池电量监控
│   ├── cpu.rs         # CPU 使用率/温度
│   ├── service.rs     # ROS/LLM 服务状态
│   ├── network.rs     # 网络连接状态
│   ├── bag_recorder.rs # MCAP 录制状态
│   └── mod.rs
└── ui/
    ├── status.rs      # 状态徽章/全屏按钮
    ├── cpu.rs         # CPU 显示组件
    └── mod.rs
```

#### 眼球追踪

支持三种追踪模式：
- `pupils_only`: 仅瞳孔移动
- `whole_eye`: 整个眼球移动
- `combined`: 瞳孔 + 眼球组合移动（默认）

追踪源：
- `mouse`: 鼠标位置
- `person`: 最大检测到的人（默认）

#### 系统状态栏

```
[电池图标] [CPU: 45% 52°C]          [ROS●] [LLM●] [NET●] [BAG●] [⛶]
  ← 左上角                                          右上角 →
```

- 电池低于 15% 时红色闪烁
- ROS/LLM/NET/BAG 显示对应服务状态（绿色/红色/灰色）
- 点击顶部中央区域可隐藏/显示状态栏

---

### 4.13 LLM 语音助手前端 (`ai/llm-ui/live-audio`)

**语言**: TypeScript  
**位置**: `ai/llm-ui/live-audio/`  
**框架**: Vite + TypeScript

基于浏览器的实时语音交互界面。

| 文件 | 功能 |
|------|------|
| `index.tsx` | 主入口 |
| `audio-manager.ts` | 音频管理（录音/播放） |
| `robot-face.ts` | 机器人表情显示 |
| `session-manager.ts` | 会话管理 |
| `tools.ts` | 机器人控制工具 |
| `robot_server.py` | Python 后端服务 |

---

### 4.14 Bag 录制器 (`bag_recorder`)

**语言**: Python  
**位置**: `ros2_ws/src/bag_recorder/`

通过手柄按键控制 MCAP 格式的 ROS2 bag 录制。

- **L1 (长按 1 秒)**: 开始录制
- **R1**: 停止录制
- 自动过滤原始图像话题以节省存储空间
- 输出 MCAP 文件，可用 Foxglove Studio 查看

---

### 4.15 机器人描述 (`pupper_v3_description`)

**位置**: `ros2_ws/src/pupper_v3_description/`

提供 URDF 和 MuJoCo XML 格式的机器人模型文件。

```
description/
├── pupper_v3.urdf.xacro           # 真实机器人 URDF
├── pupper_v3_mujoco.urdf.xacro    # 仿真用 URDF
├── pupper_v3.ros2_control.xacro   # ros2_control 硬件接口配置
├── components.xacro               # 组件定义
├── meshes/                        # STL 网格文件
├── mujoco_xml/                    # MuJoCo XML 模型
└── urdf/                          # 原始 URDF 文件
```

#### 模型制作流程

```
CAD 导出 → Blender (Phobos 插件) → URDF → fix_urdf.py 修复
    → MuJoCo compile → create_mujoco_xml.py → 最终 XML
```

---

### 4.16 基础设施 (`infra/pupper_image_builder`)

**位置**: `infra/pupper_image_builder/`  
**工具**: HashiCorp Packer

构建树莓派系统镜像：

| 镜像 | 说明 |
|------|------|
| `pios_base_arm64` | 基础 Raspberry Pi OS + ROS2 |
| `pios_full_arm64` | 完整镜像（包含所有依赖和代码） |
| `pios_ai_arm64` | AI 扩展镜像（包含 Hailo 驱动） |

---

## 5. 数据流

### 5.1 运动控制数据流

```
PS5 手柄 → Bluetooth → /dev/input/js0
    → joy_linux_node → /joy
    → teleop_twist_joy → /teleop_cmd_vel
    → cmd_vel_mux → /cmd_vel
    → neural_controller
        ├── 读取 /cmd_vel (速度指令)
        ├── 读取 IMU 状态 (角速度/姿态)
        ├── 读取关节状态 (位置/速度)
        ├── 组装观测向量
        ├── RTNeural 推理 → 动作向量
        └── 写入关节指令 (position/kp/kd)
    → control_board_hardware_interface
        → CAN 总线 → 12 个舵机
```

### 5.2 语音控制数据流

```
用户语音 → 浏览器 (live-audio)
    → WebSocket → llm_websocket_server (localhost:8765)
        → OpenAI Realtime API → 语义理解
    → JSON 命令返回
        ├── activate/deactivate → controller_manager service
        ├── move → /llm_cmd_vel → cmd_vel_mux → /cmd_vel
        └── get_battery → check_batt_voltage.py
```

### 5.3 视觉感知数据流

```
鱼眼相机 → camera_ros → /camera/image_raw
    → Hailo AI 加速器 → 人物检测结果
        ├── → /detections (ROS2 话题)
        │   → person_follower → /person_follow_cmd_vel → cmd_vel_mux
        └── → ZMQ (tcp://127.0.0.1:5556)
            → pupper-rs DetectionReceiver
            → EyeTracker → 眼球追踪动画
```

### 5.4 动画系统数据流

```
CSV 关键帧文件 → animation_controller_py
    → 解析关键帧 → 插值
    → forward_position_controller (关节位置)
    → forward_kp_controller (位置增益)
    → forward_kd_controller (速度增益)
    → hardware_interface → CAN → 舵机
```

---

## 6. 部署流程

### 6.1 真实机器人部署

```
1. 使用 pupper_image_builder 构建/下载树莓派镜像
2. 刷入 Raspberry Pi 5 SD 卡
3. 连接硬件（控制板、舵机、相机、Hailo）
4. 系统服务自动启动：
   - robot.service → robot.sh → ros2 launch neural_controller launch.py
   - pupper-gui.service → pupper-rs 全屏 GUI
   - llm-agent.service → LLM WebSocket 服务
   - battery_monitor.service → 电池监控
5. PS5 手柄蓝牙配对: pair_ps5_controller.sh
```

### 6.2 开发环境部署（x86 Ubuntu 24 仿真）

```bash
# 安装依赖
sudo apt install git-lfs
git lfs install
git clone https://github.com/Nate711/pupperv3-monorepo.git --recurse-submodules
./install_dev_dependencies.sh

# 构建
cd ros2_ws
source build.sh

# 运行仿真
ros2 launch neural_controller launch.py sim:=True
```

### 6.3 systemd 服务

| 服务 | 说明 | 启动命令 |
|------|------|----------|
| `robot.service` | 机器人主控制 | ros2 launch neural_controller launch.py |
| `pupper-gui.service` | Rust 表情 GUI | pupper-rs |
| `llm-agent.service` | LLM 语音助手 | llm_websocket_server |
| `battery_monitor.service` | 电池监控 | check_batt_voltage.py |
| `volume-max.service` | 音量最大化 | — |

停止所有服务:
```bash
./stop_all_services.sh  # sudo systemctl stop robot llm-agent pupper-gui
```

查看 LLM 日志:
```bash
./llm_logs.sh  # sudo journalctl -u llm-agent -f
```

---

## 7. 控制频率与实时性

| 组件 | 频率 | 说明 |
|------|------|------|
| `controller_manager` | 520 Hz | 控制循环主频率 |
| `neural_controller` | 52 Hz | 每 10 个周期推理一次 (repeat_action=10) |
| `joint_state_broadcaster` | 260 Hz | 关节状态广播 |
| `imu_sensor_broadcaster` | 260 Hz | IMU 数据广播 |
| `joy_linux_node` | 50 Hz | 手柄数据采集 |
| `camera` | 20 Hz | 图像采集 (FrameDurationLimits: 200000μs) |
| `animation_controller` | 40 Hz | 动画帧率 |

RTNeural 专门为实时推理设计，避免了 PyTorch/TensorFlow 的非确定性延迟。控制器在 C++ 实时线程中运行。

---

## 8. 关键依赖

### ROS2 包

```
ros-jazzy-desktop
ros-jazzy-ros2-control / ros-jazzy-ros2-controllers
ros-jazzy-teleop-twist-joy
ros-jazzy-foxglove-bridge
ros-jazzy-xacro
ros-jazzy-hardware-interface
ros-jazzy-vision-msgs
ros-jazzy-camera-ros
ros-jazzy-joy-linux
```

### Python 包

```
wandb          # 实验追踪
openai         # OpenAI API
websockets     # WebSocket 服务
glfw           # MuJoCo 渲染
pyaudio/sounddevice  # 音频
jax/brax/mujoco-mjx  # RL 训练
```

### Rust 依赖

```toml
eframe = "0.27"          # GUI 框架
egui_extras = "0.27"     # 图像/SVG 加载
zmq = "0.10"             # ZMQ 消息
serde/toml/serde_json    # 序列化
clap = "4.5"             # 命令行参数
```

---

## 9. 开发工作流

### 添加新动画

```
1. 长按 L1 直到 BAG 状态图标变绿
2. 操控机器人完成目标动作
3. 按 R1 停止录制
4. Foxglove 验证动画
5. scripts/mcap_to_csv.py 转换
6. 放入 animation_controller_py/launch/animations/
7. 重新构建
```

### 更新运动策略

```
1. 在 ai/rl/ 训练新策略
2. 导出 JSON 格式策略文件
3. 或: python3 download_latest_policy.py (从 WandB)
4. 放入 ros2_ws/src/neural_controller/launch/
5. 更新 config.yaml 中的 model_path
6. 重新构建
```

### 测试相机/检测

```bash
# 仿真模式启动模拟相机和检测
ros2 launch hailo detection_with_mock_camera_launch.py

# Foxglove 可视化
ros2 run foxglove_bridge foxglove_bridge
```
