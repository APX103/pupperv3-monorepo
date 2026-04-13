# Pupper V3 训练、仿真、可视化与部署完整指南

## 目录

- [1. 训练新模型](#1-训练新模型)
  - [1.1 环境要求](#11-环境要求)
  - [1.2 方式一：Google Colab（推荐）](#12-方式一google-colab推荐)
  - [1.3 方式二：本地训练](#13-方式二本地训练)
  - [1.4 训练参数详解](#14-训练参数详解)
  - [1.5 自定义配置](#15-自定义配置)
  - [1.6 从检查点恢复训练](#16-从检查点恢复训练)
- [2. 部署到机器人](#2-部署到机器人)
  - [2.1 获取训练产物](#21-获取训练产物)
  - [2.2 放置策略文件](#22-放置策略文件)
  - [2.3 修改部署配置](#23-修改部署配置)
  - [2.4 构建、启动与验证](#24-构建启动与验证)
  - [2.5 恢复开机自启](#25-恢复开机自启)
- [3. 仿真验证](#3-仿真验证)
  - [3.1 sim:=True 的工作原理](#31-simtrue-的工作原理)
  - [3.2 在树莓派上运行仿真](#32-在树莓派上运行仿真)
  - [3.3 Foxglove 远程可视化](#33-foxglove-远程可视化)
- [4. 训练可视化](#4-训练可视化)
  - [4.1 WandB 训练监控](#41-wandb-训练监控)
  - [4.2 MuJoCo 内置 GUI](#42-mujoco-内置-gui)
  - [4.3 RViz2 3D 模型查看](#43-rviz2-3d-模型查看)
  - [4.4 Foxglove 实时数据面板](#44-foxglove-实时数据面板)
- [5. 已包含的动作](#5-已包含的动作)
  - [5.1 RL 行走策略](#51-rl-行走策略)
  - [5.2 关键帧动画](#52-关键帧动画)
  - [5.3 控制器切换](#53-控制器切换)

---

## 1. 训练新模型

### 1.1 环境要求

#### 硬件

| 需求 | 说明 |
|------|------|
| **GPU** | **必须**。推荐 NVIDIA A100 (80GB) 或 L4 |
| **显存** | 8192 个并行环境同时仿真，需要大显存 |
| **CPU/RAM** | 次要，瓶颈在 GPU |

性能参考：

| GPU | 平地 (steps/s) | 复杂地形 (steps/s) |
|-----|----------------|-------------------|
| L4 | ~400K | ~180K |
| A100 | ~760K | ~250K |
| 5090 | ~56K（高度场） | — |

> **注意：本地训练需要 CUDA GPU + Linux 环境，Mac 不可用（JAX 仅支持 CUDA 后端）。**

#### 软件依赖

训练框架基于 **Brax + JAX + MuJoCo MJX**，算法为 **PPO (Proximal Policy Optimization)**。

依赖管理使用 `uv`，配置文件在 `ai/rl/pyproject.toml`，关键依赖：

```
Python >= 3.12
mujoco >= 3.3.5
brax >= 0.13.0
jax >= 0.7.1
flax >= 0.11.1
wandb >= 0.21.1
hydra-core
ml-collections
```

### 1.2 方式一：Google Colab（推荐）

Colab 免费提供 A100/L4 GPU，是最简单的训练方式，无需配置本地环境。

#### 步骤

1. **打开 Colab Notebook**

   访问以下链接（也在 `ai/rl/pupper_mjx_rl_use_this.py` 中注释）：

   ```
   https://colab.research.google.com/drive/1Zo2p2u-VpFHtcHxb3qiSrB8qlHIezEiy
   ```

2. **选择 GPU Runtime**

   - 点击菜单栏 `Runtime` → `Change runtime type`
   - Hardware accelerator 选择 **A100 GPU** 或 **L4 GPU**
   - 点击 Save

3. **配置 Weights & Biases（可选但推荐）**

   在 Notebook 中找到 WandB 配置单元格，填入你的 WandB API Key：

   ```python
   wandb.login(key="你的_WANDB_API_KEY")
   ```

   如果没有 WandB 账号：
   - 访问 https://wandb.ai 注册
   - 在 https://wandb.ai/authorize 获取 API Key

   不配置 WandB 也可以训练，但无法在线查看训练曲线。

4. **全部运行**

   - 点击菜单栏 `Runtime` → `Run all`
   - 或按 `Shift + Enter` 逐个单元格执行

5. **等待训练完成**

   默认训练 **10 亿步**，在 A100 上大约需要数小时。训练过程中会定期：
   - 打印训练 reward 曲线
   - 保存检查点
   - 生成策略评估可视化（如果配置了 WandB）

6. **下载策略文件**

   训练完成后，Colab 会输出一个 `policy_*.json` 文件。点击文件左侧的下载按钮保存到本地。

   文件命名格式：`policy_{wandb_run_name}_max_reward_{score}.json`
   例如：`policy_ancient-surf-216_max_reward_20.27.json`

### 1.3 方式二：本地训练

适合有 NVIDIA GPU 的 Linux 机器，使用 Hydra 配置管理，更灵活。

#### 步骤

1. **进入训练目录**

   ```bash
   cd ai/rl
   ```

2. **安装依赖**

   ```bash
   uv sync
   ```

3. **验证配置（可选）**

   ```bash
   uv run python test_config.py
   ```

4. **开始训练**

   ```bash
   uv run python pupper_mjx_rl_training.py
   ```

   训练脚本会自动：
   - `git clone` [pupperv3-mjx](https://github.com/Nate711/pupperv3-mjx)（训练环境、奖励函数、域随机化）
   - `git clone` [pupper_v3_description](https://github.com/g-levine/pupper_v3_description)（MuJoCo XML 模型）
   - 加载模型 → 创建 8192 个并行环境 → 开始 PPO 训练循环
   - 训练完成后导出 RTNeural JSON 策略文件

5. **查找输出**

   训练产物保存在 Hydra 输出目录（默认 `outputs/{日期}/{时间}/`）：

   | 输出 | 路径 | 说明 |
   |------|------|------|
   | 策略 JSON | `outputs/{run}/policy_*.json` | 部署到机器人用 |
   | 检查点 | `outputs/{run}/mjx_params_*` | JAX 格式，可恢复训练 |
   | WandB 日志 | 在线 | 训练曲线和指标 |

#### 命令行覆盖参数

可以在训练命令中覆盖任何 Hydra 配置：

```bash
# 快速测试（10M 步，而非默认 10 亿步）
uv run python pupper_mjx_rl_training.py training.ppo.num_timesteps=10000000

# 使用更小的网络结构
uv run python pupper_mjx_rl_training.py policy.hidden_layer_sizes=[128,64,64,64]

# 启用随机高度场地形
uv run python pupper_mjx_rl_training.py training.height_field_random=true

# 修改学习率
uv run python pupper_mjx_rl_training.py training.ppo.learning_rate=1e-4

# 禁用域随机化（用于调试）
uv run python pupper_mjx_rl_training.py training.domain_randomization_enabled=false
```

### 1.4 训练参数详解

所有参数的配置文件位于 `ai/rl/conf/` 目录下，使用 Hydra 分层管理。

#### PPO 超参数 (`conf/training/default.yaml`)

```yaml
training:
  ppo:
    num_timesteps: 1_000_000_000    # 总训练步数（10 亿）
    num_envs: 8192                   # 并行环境数
    episode_length: 500              # 每个 episode 的步数
    learning_rate: 3.0e-5            # 学习率
    discounting: 0.97                # 折扣因子
    entropy_cost: 1.0e-2             # 熵正则化系数
    batch_size: 256                  # 批量大小
    num_minibatches: 32              # 小批量数
    num_updates_per_batch: 4         # 每批更新次数
    unroll_length: 20                # rollout 长度
```

#### 奖励函数 (`conf/reward/default.yaml`)

奖励函数约 20 项，控制机器人的行走行为：

```yaml
reward:
  # 跟踪奖励（越大越好）
  tracking_lin_vel: 1.5          # 线速度跟踪（前进/后退/侧移）
  tracking_ang_vel: 0.8          # 角速度跟踪（转向）
  tracking_orientation: 0.5      # 体姿态跟踪

  # 正则化惩罚（让动作更平滑）
  torques: -0.025                # 力矩惩罚
  action_rate: -0.1              # 动作变化率惩罚
  joint_acceleration: -1.0e-6   # 关节加速度惩罚

  # 行为惩罚
  lin_vel_z: -0.1                # Z 方向速度（不希望上下跳动）
  foot_slip: -0.2                # 脚滑惩罚
  knee_collision: -10.0          # 膝盖碰地惩罚（避免跪地）
  body_collision: -0.5           # 身体碰地惩罚

  # 终止惩罚
  termination: -100.0            # 摔倒惩罚（最大惩罚项）

  # 行为鼓励
  feet_air_time: 0.02            # 足部腾空时间鼓励（促进步态）
  stand_still_joint_velocity: -0.2  # 静止时关节速度惩罚
```

`tracking_sigma: 0.25` 控制跟踪奖励的高斯宽度——值越小，机器人越精确地跟踪指令。

#### 域随机化 (`conf/training/default.yaml`)

域随机化让策略对真实世界的噪声具有鲁棒性：

```yaml
training:
  domain_randomization:
    friction: [0.6, 1.4]           # 地面摩擦系数范围
    body_mass: [0.9, 1.3]          # 身体质量缩放范围
    body_inertia: [0.9, 1.3]       # 惯性缩放范围
    kick_probability: 0.04          # 随机踢扰概率（4%）
    kick_vel: 0.10                  # 踢扰速度 (m/s)
    latency_distribution: [0.2, 0.8] # 动作延迟（20% 无延迟, 80% 延迟 1 步）
    imu_latency: [0.5, 0.5]        # IMU 传感器延迟
    angular_velocity_noise: 0.1     # 角速度噪声 (rad/s)
    gravity_noise: 0.05             # 重力噪声
    motor_angle_noise: 0.05         # 电机角度噪声 (rad)
    kp_multiplier: [0.6, 1.1]      # 位置增益随机化
    kd_multiplier: [0.8, 1.5]      # 速度增益随机化
```

#### 速度指令采样

训练时随机采样的速度指令范围：

```yaml
training:
  command_sampling:
    lin_vel_x_range: [-0.75, 0.75]   # 前后速度 (m/s)
    lin_vel_y_range: [-0.5, 0.5]     # 左右速度 (m/s)
    ang_vel_yaw_range: [-2.0, 2.0]   # 偏航角速度 (rad/s)
    zero_command_probability: 0.02    # 2% 概率发送零速度指令
```

#### 策略网络架构 (`conf/policy/default.yaml`)

```yaml
policy:
  hidden_layer_sizes: [256, 128, 128, 128]  # 4 个隐藏层
  activation: elu                             # 隐藏层激活函数
  observation_history: 4                      # 观测历史步数
  action_scale: 0.75                         # 动作缩放因子
```

**输入**：192 维（4 步历史 x 48 维单步观测）
- 索引 0-2: 角速度 (IMU)
- 索引 3-5: 投影重力向量 (IMU 四元数计算)
- 索引 6-8: 速度指令 vx, vy, wz (/cmd_vel)
- 索引 9-11: 期望体姿态 (/cmd_pose)
- 索引 12-23: 关节位置偏差 (12 关节)
- 索引 24-35: 上一步动作 (12 关节反馈)
- 索引 36-47: 保留/其他

**输出**：12 维关节目标角度 (rad)，通过 tanh 激活限制在 [-1, 1]。

#### 终止条件

```yaml
training:
  terminal_body_z: 0.05       # 身体高度低于 5cm → 终止（摔倒了）
  terminal_body_angle: 0.70   # 身体倾斜超过 0.7 rad (~40°) → 终止
```

### 1.5 自定义配置

#### 修改奖励权重

直接编辑 `ai/rl/conf/reward/default.yaml`，或通过命令行覆盖：

```bash
# 更重视线速度跟踪，降低力矩惩罚
uv run python pupper_mjx_rl_training.py \
  reward.tracking_lin_vel=3.0 \
  reward.torques=-0.01
```

#### 训练 3 腿策略

修改 `action_scale` 来"关闭"某条腿的动作：

```bash
# 后左腿抬起（BL up）— 将后左 3 个关节的 action_scale 设为 0.1
# 默认 12 关节顺序:
# leg_front_r [1,2,3], leg_front_l [1,2,3],
# leg_back_r  [1,2,3], leg_back_l  [1,2,3]
```

在训练脚本中需要手动修改 action_scale 配置（参见 `ai/rl/pupper_mjx_rl_use_this.py` 中的注释示例）。

#### 训练 2 腿策略

类似地，将两条腿的 action_scale 设为接近 0：

```python
# 后左 + 前右抬起
action_scale = [1, 1, 0.0, 1, 1, 1, 1, 1, 1, 1, 1, 0.1]
```

#### 修改网络结构

```bash
# 更大的网络
uv run python pupper_mjx_rl_training.py policy.hidden_layer_sizes=[512,256,256,256]

# 更小的网络（更快推理）
uv run python pupper_mjx_rl_training.py policy.hidden_layer_sizes=[64,64,64]
```

### 1.6 从检查点恢复训练

如果你有之前训练的检查点（run number），可以从中恢复继续训练：

**本地训练：**

```bash
uv run python pupper_mjx_rl_training.py training.checkpoint_run_number=238
```

**Colab 训练：**

在 Notebook 中修改配置变量：

```python
training_config.checkpoint_run_number = 238
```

已知的优秀检查点（来自项目注释）：

| Run Number | 说明 |
|------------|------|
| 202 | 通用 4 腿策略 |
| 206 | 仅前进策略 |
| 216 | 大网络 (1024,512,512,512) 通用策略 |
| 225 | 3 腿策略 |
| 233 | 改进的 3 腿策略 |
| 238 | 4 腿重新训练 1B 步 |

---

## 2. 部署到机器人

### 2.1 获取训练产物

训练完成后你会得到一个 `policy_*.json` 文件（约 1-40MB），这是 RTNeural 格式的策略文件，包含完整的网络权重和部署参数。

文件内容结构：

```json
{
  "in_shape": [1, 192],
  "out_shape": [1, 12],
  "hidden_layers": [
    {"type": "dense", "in_size": 192, "out_size": 256, "activation": "elu", "weights": [...], "bias": [...]},
    ...
  ],
  "action_scale": 0.75,
  "kp": 5.0,
  "kd": 0.25,
  "default_joint_pos": [0.26, 0.0, -0.52, ...],
  "joint_upper_limits": [...],
  "joint_lower_limits": [...],
  "use_imu": true,
  "observation_history": 4
}
```

### 2.2 放置策略文件

将 `policy_*.json` 复制到以下目录：

```
ros2_ws/src/neural_controller/launch/policy_你的名字.json
```

该目录下已有的策略文件（供参考）：

| 文件 | 说明 |
|------|------|
| `policy_latest.json` | 最新策略（默认使用） |
| `policy.json` | 早期策略 |
| `policy_ancient-surf-216_max_reward_20.27.json` | 最高 reward 策略 (20.27) |
| `policy_pretty-spaceship-243_max_reward_17.57.json` | 另一个 4 腿策略 (17.57) |
| `policy_rich-donkey-233_max_reward_19.16.json` | 3 腿策略 (19.16) |

### 2.3 修改部署配置

编辑 `ros2_ws/src/neural_controller/launch/config.yaml`，找到 `model_path` 字段并修改：

**4 腿策略**（`neural_controller` 节使用）：

```yaml
neural_controller:
  ros__parameters:
    model_path: "$(find-pkg-share neural_controller)/launch/policy_你的名字.json"
```

**3 腿策略**（`neural_controller_three_legged` 节使用）：

```yaml
neural_controller_three_legged:
  ros__parameters:
    model_path: "$(find-pkg-share neural_controller)/launch/policy_你的名字.json"
```

> `$(find-pkg-share neural_controller)` 会在运行时自动解析为包的安装路径。

### 2.4 构建、启动与验证

#### Step 1: SSH 到树莓派

```bash
# 普通 SSH
ssh pi@pupper.local

# 如果需要 Foxglove 可视化（端口转发）
ssh -LA 8765:localhost:8765 pi@pupper.local
```

默认密码在 `infra/pupper_image_builder/readme.md` 中说明，通常为 `rhea123`。

#### Step 2: 禁用开机自启（一次性操作）

在修改代码前，先禁用自动启动的 robot 服务，避免冲突：

```bash
sudo systemctl disable robot
sudo systemctl stop robot
```

#### Step 3: 设置文件权限（一次性操作）

```bash
sudo chown -R pi /home/pi
```

#### Step 4: 同步代码

将修改后的文件同步到树莓派。在本地机器上执行：

```bash
# 方式一：用 rsync 同步整个仓库
rsync -avz --exclude='.git' --exclude='node_modules' \
  /Users/lijialun/work/pupperv3-monorepo/ \
  pi@pupper.local:/home/pi/pupperv3-monorepo/

# 方式二：只同步策略文件
scp ros2_ws/src/neural_controller/launch/policy_你的名字.json \
  pi@pupper.local:/home/pi/pupperv3-monorepo/ros2_ws/src/neural_controller/launch/
```

#### Step 5: 在树莓派上编译

```bash
cd ~/pupperv3-monorepo/ros2_ws
./build.sh
```

编译脚本 `build.sh` 的内容：

```bash
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source /opt/ros/jazzy/setup.bash
cd "$SCRIPT_DIR" || exit
colcon build --symlink-install \
  --cmake-args -DCMAKE_BUILD_TYPE=RelWithDebInfo \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
  -DPython3_EXECUTABLE=/usr/bin/python3 \
  -DCMAKE_CXX_FLAGS="-g0"
source "$SCRIPT_DIR/install/local_setup.bash"
```

`--symlink-install` 意味着 Python 文件和配置文件的修改不需要重新编译就能生效，但 C++ 代码的修改需要重新 build。

#### Step 6: 启动

```bash
ros2 launch neural_controller launch.py
```

#### Step 7: 验证

- 用手柄控制机器人行走，观察步态是否正常
- 使用 Foxglove（浏览器打开 `localhost:8765`）查看关节状态和 IMU 数据
- 如果行为异常，先尝试用仿真验证（见第 3 节）

### 2.5 恢复开机自启

验证策略正常工作后，恢复开机自启：

```bash
sudo systemctl enable robot
```

开机自启服务文件在 `robot/utils/robot.service`，它执行的脚本是 `robot/utils/robot.sh`：

```bash
#!/bin/bash
source /opt/ros/jazzy/setup.bash
source /home/pi/pupperv3-monorepo/ros2_ws/install/local_setup.bash
ROS_LOCALHOST_ONLY=1 ros2 launch neural_controller launch.py
```

### 补充：从 Weights & Biases 下载策略

如果策略已上传到 WandB，可以直接在树莓派上下载：

```bash
cd ~/pupperv3-monorepo/ros2_ws/src/neural_controller

# 下载最新策略
python3 download_latest_policy.py

# 下载指定 run 的策略
python3 download_latest_policy.py --run_number=238
```

下载脚本会将策略保存为 `launch/policy_latest.json`。W&B 项目信息：
- Entity: `hands-on-robotics`
- Project: `pupperv3-mjx-rl`

---

## 3. 仿真验证

### 3.1 sim:=True 的工作原理

在 `neural_controller/launch/launch.py` 中，`sim` 参数控制使用哪个 URDF：

```python
# sim:=False（默认）— 真实机器人
pupper_v3.urdf.xacro
  → 使用 ros2_control 直连真实硬件（SPI 通信）

# sim:=True — MuJoCo 仿真
pupper_v3_mujoco.urdf.xacro
  → 使用 MuJoCo 物理引擎模拟硬件接口
  → 禁用真实相机节点
  → 虚拟 IMU 和关节传感器
```

这意味着你的策略代码（神经网络的推理逻辑）在仿真和真实环境之间完全共享，只是底层硬件接口不同。这也是为什么仿真验证有意义——验证的是策略本身的质量。

### 3.2 在树莓派上运行仿真

#### Step 1: SSH 到树莓派

```bash
ssh pi@pupper.local
```

#### Step 2: 禁用开机自启的 robot 服务（如果在运行）

```bash
sudo systemctl stop robot
```

#### Step 3: 启动仿真模式

```bash
source /opt/ros/jazzy/setup.bash
source ~/pupperv3-monorepo/ros2_ws/install/local_setup.bash
ros2 launch neural_controller launch.py sim:=True
```

此时系统会使用 MuJoCo 仿真引擎代替真实硬件。你可以用手柄（或键盘/话题发布）发送 `/cmd_vel` 指令，观察仿真中机器人的运动。

#### Step 4: 用 Foxglove 观察（可选）

```bash
# 在本地机器上（不是树莓派）
ssh -LA 8765:localhost:8765 pi@pupper.local
# 然后在仿真运行的情况下，打开浏览器访问 localhost:8765
```

### 3.3 Foxglove 远程可视化

Foxglove Bridge 节点在 launch 文件中默认启动，提供 WebSocket 接口。

**连接方式：**

1. SSH 端口转发：

   ```bash
   ssh -LA 8765:localhost:8765 pi@pupper.local
   ```

2. 浏览器打开 https://app.foxglove.dev/ ，选择 "Open connection"，输入 `localhost:8765`

3. 在 Foxglove 中添加面板：
   - **3D** 面板 → 查看机器人 3D 模型和 TF 变换
   - **Plot** 面板 → 查看关节角度、速度等时序数据
   - **Raw Messages** 面板 → 查看任意 topic 的原始消息

> 注意：树莓派上的 `ROS_LOCALHOST_ONLY=1` 环境变量意味着 ROS2 topic 只在本地可见。Foxglove 通过 WebSocket 端口 8765 桥接访问数据，不受此限制。

---

## 4. 训练可视化

### 4.1 WandB 训练监控

WandB (Weights & Biases) 是训练过程中的主要可视化工具。

#### 配置 WandB

**在 Colab 中：**

```python
import wandb
wandb.login(key="你的_API_KEY")
```

**本地训练：**

```bash
wandb login
# 粘贴你的 API Key
```

#### WandB 提供的可视化

- **训练曲线**：Reward、Episode length、Policy loss、Value loss 等
- **评估视频**：定期生成的策略 rollout 视频（在 MuJoCo 中渲染）
- **超参数记录**：自动记录所有训练配置
- **实时对比**：多次训练 run 之间的指标对比

#### 查看方式

训练开始后，终端会输出 WandB 面板链接，格式如：

```
View run at https://wandb.ai/你的用户名/pupperv3-mjx-rl/runs/run_name
```

### 4.2 MuJoCo 内置 GUI

MuJoCo 提供强大的交互式可视化 GUI，可用于调试和观察仿真。

#### 启动方式

MuJoCo 仿真 GUI 通过 `pupper_mujoco_sim` 包提供：

```bash
# 查看可用的 launch 文件
ros2 launch pupper_mujoco_sim <launch_file>
```

#### GUI 功能

MuJoCo 内置 GUI 包含：

| 功能 | 说明 |
|------|------|
| **3D 渲染** | OpenGL 实时渲染机器人模型 |
| **关节滑块** | 实时调整关节角度，手动摆 pose |
| **执行器控制** | 直接控制力矩/速度/位置 |
| **摄像机控制** | 自由视角、跟踪摄像机、固定摄像机 |
| **物理参数** | 调整时间步、重力、求解器参数 |
| **传感器绘图** | 实时绘制 IMU、关节传感器数据 |
| **性能分析器** | GPU/CPU 占用、仿真步率 |
| **关键帧管理** | 保存和加载机器人姿态 |

### 4.3 RViz2 3D 模型查看

RViz2 是 ROS2 的标准 3D 可视化工具，适合查看机器人模型和 TF 树。

#### 查看静态模型（手动拖动关节）

```bash
ros2 launch pupper_v3_description display_model.launch.py
```

这会启动 RViz2 + `joint_state_publisher_gui`，你可以用滑块手动调整每个关节的角度。

#### 查看模型（无手动控制）

```bash
ros2 launch pupper_v3_description rviz_only.launch.py
```

这会启动 RViz2 + `robot_state_publisher` + `joint_state_publisher_gui`，包含完整的 TF 树。

### 4.4 Foxglove 实时数据面板

Foxglove 是基于 Web 的可视化工具，无需安装桌面应用。

#### 常用面板配置

| 面板类型 | 用途 | 推荐添加的 Topic |
|---------|------|-----------------|
| **3D** | 机器人 3D 视图 | `/tf` |
| **Plot** | 时序曲线 | `/joint_states` (position), `/imu_sensor/data` (angular_velocity) |
| **Raw Messages** | 原始消息查看 | `/joy`, `/cmd_vel`, `/teleop_cmd_vel` |
| **Image** | 相机画面 | `/camera/image_raw` |
| **Teleop** | 发送速度指令 | `/cmd_vel` |

#### 查看关键指标

- **关节位置** (`/joint_states` → position)：验证策略输出是否合理
- **IMU 数据** (`/imu_sensor/data` → angular_velocity)：检查身体是否稳定
- **速度指令** (`/teleop_cmd_vel`)：确认手柄输入正确传递
- **最终速度指令** (`/cmd_vel`)：确认 mux 优先级正确

---

## 5. 已包含的动作

### 5.1 RL 行走策略

项目包含 5 个预训练的强化学习策略，存放在 `ros2_ws/src/neural_controller/launch/`：

| 策略文件 | Reward | 关联控制器 | 推荐场景 |
|---------|--------|-----------|---------|
| `policy_latest.json` | — | `neural_controller`（默认） | 日常使用，最新的 4 腿行走 |
| `policy.json` | — | — | 早期策略，一般不推荐使用 |
| `policy_ancient-surf-216_max_reward_20.27.json` | **20.27** | — | 最高 reward 的 4 腿策略 |
| `policy_pretty-spaceship-243_max_reward_17.57.json` | 17.57 | — | 4 腿行走策略 |
| `policy_rich-donkey-233_max_reward_19.16.json` | 19.16 | `neural_controller_three_legged` | 3 腿行走策略（默认配置） |

**切换方式：** 编辑 `config.yaml` 中的 `model_path`，然后重新编译。

### 5.2 关键帧动画

项目包含 13 个预录制的关键帧动画，存放在 `ros2_ws/src/animation_controller_py/launch/animations/`：

| 动画文件 | 描述 |
|---------|------|
| `stand_sit_stand_recording_2025-09-03_12-46-36.csv` | 站立→坐下→站立 |
| `stand_sit_shake_sit_stand_recording_2025-09-03_12-47-18.csv` | 站立→坐下→握手→坐下→站立 |
| `lie_sit_lie_recording_2025-09-03_12-44-08_0.csv` | 躺下→坐→躺下 |
| `lie_downward_dog_recording_2025-09-04_16-08-00_0.csv` | 躺下→下犬式 |
| `stand_downward_dog_recording_2025-09-04_16-09-51_0.csv` | 站立→下犬式 |
| `swim_recording_2025-09-04_16-10-45_0.csv` | 游泳动作 |
| `push_up_recording_2025-09-04_16-11-34_0.csv` | 俯卧撑 |
| `spider_recording_2025-09-04_16-12-38_0.csv` | 蜘蛛爬行 |
| `sneeze_recording_2025-09-04_16-13-54_0.csv` | 打喷嚏 |
| `twerk_recording_2025-09-04_16-14-51_0.csv` | 扭臀舞 |
| `pee2_recording_2025-10-22_17-41-45.csv` | 撒尿姿势 |
| `upward_dog_recording_2025-10-22_17-17-07.csv` | 上犬式 |
| `superman_recording_2025-10-22_17-47-41.csv` | 超人飞行姿势 |

**动画播放原理：** CSV 文件的每一行是一个关键帧，列名为 12 个关节名。`animation_controller_py` 节点以 120Hz 的频率在关键帧之间线性插值，通过 `forward_position_controller`、`forward_kp_controller`、`forward_kd_controller` 发布关节位置指令。

**触发动画：** 通过 ROS2 topic 发送动画名称：

```bash
ros2 topic pub --once /animation_controller_py/animation_select std_msgs/String "{data: 'stand_sit_stand_recording_2025-09-03_12-46-36'}"
```

### 5.3 控制器切换

系统在运行时支持在多种控制器之间切换，通过 `joy_util_node`（`ros2_ws/src/joy_utils/`）实现。

#### 控制器列表

| 控制器 | 说明 | 切换按键（PS5） | 切换按键（Xbox） |
|--------|------|----------------|----------------|
| `neural_controller` | 4 腿 RL 行走 | Button 0 (X) | Button 0 (A) |
| `neural_controller_three_legged` | 3 腿 RL 行走 | Button 1 (O) | Button 1 (B) |
| `forward_kp_controller` | 动画模式 - Kp 控制 | Button 2 (□) | Button 2 (X) |
| `forward_kd_controller` | 动画模式 - Kd 控制 | Button 3 (△) | Button 3 (Y) |
| `forward_position_controller` | 动画模式 - 位置控制 | — | — |

> `forward_position_controller`、`forward_kp_controller`、`forward_kd_controller` 三个控制器同时激活，用于动画系统。

#### 功能按键

| 功能 | PS5 按键 | Xbox 按键 | Button 索引 |
|------|---------|---------|------------|
| E-Stop 急停 | R3（右摇杆按） | R3（右摇杆按） | PS5: 12, Xbox: 10 |
| E-Stop 解除 | Start | Start | PS5: 9, Xbox: 7 |
| 录制开始（长按 1s） | L1 | LB | 4 |
| 录制停止 | R1 | RB | 5 |

> **注意：** 如果你使用 Xbox 手柄，需要修改 `config.yaml` 中的 `estop_index` 和 `estop_release_index`（参见 Xbox 手柄适配相关说明）。

#### 手柄摇杆映射

摇杆轴在 PS5 和 Xbox 上基本一致，不需要修改：

| 功能 | 轴索引 | 摇杆 | 缩放 |
|------|--------|------|------|
| 左右移动 (Linear Y) | Axis 0 | 左摇杆 X | 0.5 |
| 前后移动 (Linear X) | Axis 1 | 左摇杆 Y | 0.75 |
| 转向 (Angular Z) | Axis 3 | 右摇杆 X | 2.0 |

---

## 附录：常用命令速查

```bash
# === 训练 ===
cd ai/rl && uv sync                                    # 安装训练依赖
uv run python test_config.py                           # 验证配置
uv run python pupper_mjx_rl_training.py                # 开始训练
uv run python pupper_mjx_rl_training.py training.ppo.num_timesteps=10000000  # 快速测试

# === 部署 ===
scp policy.json pi@pupper.local:/home/pi/pupperv3-monorepo/ros2_ws/src/neural_controller/launch/
ssh pi@pupper.local "cd ~/pupperv3-monorepo/ros2_ws && ./build.sh"

# === 运行 ===
ros2 launch neural_controller launch.py                # 真实机器人
ros2 launch neural_controller launch.py sim:=True      # 仿真模式

# === 系统服务 ===
sudo systemctl disable robot                           # 禁用开机自启
sudo systemctl enable robot                            # 恢复开机自启
sudo systemctl stop robot                              # 停止运行中的服务
sudo systemctl start robot                             # 手动启动服务

# === 可视化 ===
ssh -LA 8765:localhost:8765 pi@pupper.local            # Foxglove 端口转发
ros2 launch pupper_v3_description display_model.launch.py  # RViz2 模型查看

# === 调试 ===
ros2 topic list                                        # 查看所有 topic
ros2 topic echo /joint_states                          # 查看关节状态
ros2 topic echo /imu_sensor/data                       # 查看 IMU 数据
ros2 topic echo /joy                                   # 查看手柄输入
ros2 control list_controllers                          # 查看活跃的控制器
ros2 topic pub --once /animation_controller_py/animation_select std_msgs/String "{data: 'stand_sit_stand_recording_2025-09-03_12-46-36'}"  # 触发动画
```
