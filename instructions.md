# Pupper V3 策略训练指南

## 概述

Pupper V3 的运动策略使用 **PPO（Proximal Policy Optimization）强化学习** 训练。

```
算法:     PPO (on-policy)
框架:     Brax + JAX
仿真器:   MuJoCo MJX (GPU 加速物理仿真)
任务:     四足机器人速度跟踪运动控制
```

---

## 1. 模型结构

**全连接 MLP**，不是 Transformer，不是 CNN。

### 策略网络 (Policy Network)

```
输入:    观测向量 (observation_history × single_obs_size)
         例: 4 × 48 = 192 维

隐藏层:  (256, 128, 128, 128)  ← 默认，可配
激活函数: ELU

输出:    12 维动作向量 (12 个关节的目标位置偏移)
最终激活: tanh (将输出夹到 [-1, 1])
```

### 值网络 (Value Network)

```
默认: (256, 256, 256, 256, 256)
用于 PPO 训练，部署时丢弃
```

### 观测向量（single_obs_size ≈ 48）

```
索引 0-2:   角速度 ωx, ωy, ωz                    (IMU)
索引 3-5:   投影重力向量 gx, gy, gz               (IMU 四元数计算)
索引 6-8:   速度指令 vx, vy, ωz                   (/cmd_vel)
索引 9-11:  期望体姿态向量                          (/cmd_pose)
索引 12-23: 关节位置偏差 (12关节 × pos - default)   (编码器)
索引 24-35: 上一步动作 (12关节)                     (策略输出反馈)
索引 36-47: 保留/其他
```

堆叠 4 份历史 (observation_history=4)，实际输入 192 维。

### 动作向量（12 维）

```
输出 = tanh(MLP(observation)) × action_scale + default_joint_pos

12 个关节: leg_front_r [1,2,3], leg_front_l [1,2,3],
           leg_back_r  [1,2,3], leg_back_l  [1,2,3]

每个输出 = 目标关节角度 (rad)
```

---

## 2. 训练环境要求

### 硬件

| 需求 | 说明 |
|------|------|
| **GPU** | **必须**。推荐 A100 或 L4。最低需要 CUDA GPU |
| **显存** | 8192 并行环境，A100 80GB 最佳 |
| **CPU/RAM** | 次要，瓶颈在 GPU |

性能基准：

```
L4 GPU:    ~400K env steps/s (平地), ~180K (复杂地形)
A100 GPU:  ~760K env steps/s (平地), ~250K (复杂地形)
5090 GPU:  ~56K steps/s (高度场)
```

### 软件

```bash
# 方式一: 本地 (ai/rl/)
uv sync   # 安装 JAX, Brax, MuJoCo MJX, WandB 等

# 方式二: Colab (pupper_mjx_rl_use_this.py)
# 直接在 Google Colab 开 A100/L4 运行

# 关键依赖版本 (Colab 版)
mujoco==3.2.7
mujoco-mjx==3.2.7
brax==0.12.1
jax==0.5.0 / jaxlib==0.5.0
```

**注意：本地训练需要 CUDA GPU + Linux 环境，Mac 不可用（JAX CUDA only）。**

---

## 3. 训练流程

### 方式一：本地训练

```bash
# 1. 进入训练目录
cd ai/rl

# 2. 安装依赖
uv sync

# 3. 运行训练（会自动 clone pupperv3-mjx 和 pupper_v3_description）
uv run python pupper_mjx_rl_training.py

# 可覆盖参数:
uv run python pupper_mjx_rl_training.py \
  training.ppo.num_timesteps=100000000 \       # 训练步数 (默认 1B)
  policy.hidden_layer_sizes=[256,128,128,128] \ # 网络结构
  training.height_field_random=true             # 启用随机地形
```

### 方式二：Colab 训练（最简单）

1. 打开 `ai/rl/pupper_mjx_rl_use_this.py` 里的 Colab 链接：
   `https://colab.research.google.com/drive/1Zo2p2u-VpFHtcHxb3qiSrB8qlHIezEiy`
2. 选 A100/L4 GPU runtime
3. 配置 WandB key
4. 全部运行
5. 下载 `policy_*.json`

### 训练循环内部流程

```
1. git clone pupperv3-mjx           # 环境/奖励/域随机化/导出
2. git clone pupper_v3_description   # MuJoCo XML 模型
3. 加载模型 → 设置 MJX 参数 → 可选添加障碍物/高度场
4. benchmark (测试仿真速度)
5. 创建 PupperV3Env (8192 并行环境)
6. WandB 初始化
7. PPO 训练循环:
   for step in range(num_timesteps):
     - 采样动作
     - 域随机化 (摩擦/质量/惯性/延迟/踢扰)
     - 环境步进 (MuJoCo MJX GPU 仿真)
     - 计算奖励 (~20项)
     - PPO 更新策略
     - 定期评估 + 可视化 + 保存检查点
8. 导出策略为 RTNeural JSON
```

---

## 4. 核心训练参数

### PPO 参数

```python
num_timesteps = 1_000_000_000    # 10 亿步
num_envs = 8192                   # 并行环境数
episode_length = 500              # 每回合步数
learning_rate = 3e-5
discounting = 0.97
entropy_cost = 1e-2
batch_size = 256
num_minibatches = 32
```

### 奖励函数（约 20 项）

```python
# 跟踪奖励
tracking_lin_vel = 1.5            # 线速度跟踪
tracking_ang_vel = 0.8            # 角速度跟踪
tracking_orientation = 0.5        # 姿态跟踪

# 正则化
torques = -0.025                  # 力矩正则化
action_rate = -0.1                # 动作平滑
joint_acceleration = -1e-6        # 关节加速度

# 惩罚
lin_vel_z = -0.1                  # Z 方向速度
foot_slip = -0.2                  # 脚滑
knee_collision = -10.0            # 膝盖碰地
body_collision = -0.5             # 身体碰地
termination = -100.0              # 摔倒

# 鼓励
feet_air_time = 0.02              # 足部腾空时间
stand_still_joint_velocity = -0.2 # 静止时关节速度
```

### 域随机化

```python
friction = (0.6, 1.4)             # 摩擦系数范围
body_mass = (0.9, 1.3)            # 质量缩放范围
body_inertia = (0.9, 1.3)         # 惯性缩放范围
kick_probability = 0.04           # 随机踢扰概率
kick_vel = 0.10                   # 踢扰速度 (m/s)
latency_distribution = [0.2, 0.8] # 动作延迟 (20% 无延迟, 80% 延迟 1 步)
imu_latency = [0.5, 0.5]          # IMU 延迟
angular_velocity_noise = 0.1      # 角速度噪声 (rad/s)
gravity_noise = 0.05              # 重力噪声
motor_angle_noise = 0.05          # 电机角度噪声 (rad)
kp_multiplier = (0.6, 1.1)        # 位置增益随机化
kd_multiplier = (0.8, 1.5)        # 速度增益随机化
```

### 指令采样

```python
lin_vel_x_range = [-0.75, 0.75]   # 前后速度 (m/s)
lin_vel_y_range = [-0.5, 0.5]     # 左右速度 (m/s)
ang_vel_yaw_range = [-2.0, 2.0]   # 偏航角速度 (rad/s)
zero_command_probability = 0.02    # 零速度指令概率
```

### 终止条件

```python
terminal_body_z = 0.05             # 身体高度低于此值 (m)
terminal_body_angle = 0.70         # 身体倾斜超过此值 (rad)
```

---

## 5. 训练输出

### 最终产物：JSON 策略文件

```json
{
  "in_shape": [1, 192],
  "out_shape": [1, 12],
  "hidden_layers": [
    {"type": "dense", "in_size": 192, "out_size": 256, "activation": "elu", "weights": [...], "bias": [...]},
    {"type": "dense", "in_size": 256, "out_size": 128, "activation": "elu", "weights": [...], "bias": [...]},
    {"type": "dense", "in_size": 128, "out_size": 128, "activation": "elu", "weights": [...], "bias": [...]},
    {"type": "dense", "in_size": 128, "out_size": 128, "activation": "elu", "weights": [...], "bias": [...]},
    {"type": "dense", "in_size": 128, "out_size": 12,  "activation": "tanh", "weights": [...], "bias": [...]}
  ],
  "action_scale": 0.75,
  "kp": 5.0,
  "kd": 0.25,
  "default_joint_pos": [0.26, 0.0, -0.52, -0.26, 0.0, 0.52, 0.26, 0.0, -0.52, -0.26, 0.0, 0.52],
  "joint_upper_limits": [...],
  "joint_lower_limits": [...],
  "use_imu": true,
  "observation_history": 4
}
```

文件命名格式: `policy_{wandb_run_name}_max_reward_{score}.json`

例: `policy_ancient-surf-216_max_reward_20.27.json`

### 其他输出

| 输出 | 路径 | 说明 |
|------|------|------|
| 策略 JSON | `output_{run_name}/policy_*.json` | RTNeural 部署用 |
| 检查点 | `output_{run_name}/mjx_params_*` | JAX 格式，可恢复训练 |
| WandB 日志 | 在线 | 训练曲线、指标、可视化 |

---

## 6. 部署到机器人

```
1. 将 policy_*.json 放入 ros2_ws/src/neural_controller/launch/
2. 更新 config.yaml 中的 model_path:
   model_path: "$(find-pkg-share neural_controller)/launch/policy_latest.json"
3. 重新构建:
   cd ros2_ws && source build.sh
4. C++ RTNeural 加载 JSON → 实时推理 (52Hz, ~0.5ms/步)
```

也可从 WandB 下载最新策略：
```bash
cd ros2_ws/src/neural_controller
python3 download_latest_policy.py
# 或指定 run: python3 download_latest_policy.py --run_number=167
```

---

## 7. 策略变体

训练代码支持多种腿部配置：

```python
# 4 腿（默认）
policy_config.action_scale = 0.75
training_config.default_pose = jp.array(
    [0.26, 0.0, -0.52, -0.26, 0.0, 0.52, 0.26, 0.0, -0.52, -0.26, 0.0, 0.52]
)

# 3 腿 - 后左腿抬起 (BL up)
# policy_config.action_scale = [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0.1]

# 3 腿 - 前左腿抬起 (FL up)
# policy_config.action_scale = [1, 1, 1, 1, 1, 0.1, 1, 1, 1, 1, 1, 1.0]

# 2 腿 - 后左+前右抬起
# policy_config.action_scale = [1, 1, 0.0, 1, 1, 1, 1, 1, 1, 1, 1, 0.1]
```

---

## 8. 外部依赖仓库

训练代码运行时自动克隆以下仓库：

| 仓库 | 作用 |
|------|------|
| `https://github.com/Nate711/pupperv3-mjx` | 训练环境、奖励函数、域随机化、策略导出 |
| `https://github.com/g-levine/pupper_v3_description` | MuJoCo XML 机器人模型 |

### pupperv3-mjx 包含的关键模块

| 模块 | 功能 |
|------|------|
| `environment.py` | PupperV3Env (Brax PipelineEnv) |
| `domain_randomization.py` | 域随机化 |
| `utils.py` | 可视化、检查点、进度追踪 |
| `obstacles.py` | 障碍物生成 |
| `export.py` | JAX → RTNeural JSON 导出 |
| `plotting.py` | 训练曲线绘制 |

---

## 9. 从检查点恢复训练

```bash
# 本地
uv run python pupper_mjx_rl_training.py training.checkpoint_run_number=238

# Colab
training_config.checkpoint_run_number = 238
```

已知的优秀检查点（来自 Colab 注释）：

```
202: 通用 4 腿策略
206: 仅前进策略
216: 1024,512,512,512 通用策略（不错但会伸腿）
225: 3 腿策略
233: 更好的 3 腿策略
238: 4 腿重新训练 1B 步
```
