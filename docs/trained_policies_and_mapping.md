# Pupper V3 已训练策略与控制映射详解

本文档详细说明项目中已有的训练策略、奖励函数配置、以及从手柄到关节控制的完整映射链路。

---

## 一、已训练策略概览

### 策略文件列表

| 策略文件 | 大小 | WandB Run | 最终奖励 | 网络参数 | 特点 |
|----------|------|-----------|----------|----------|------|
| `policy.json` | 1.2MB | - | ~4.8M | 小网络，快速推理 |
| `policy_latest.json` | 38.9MB | 243 | 17.57 | 最新四足策略 |
| `policy_ancient-surf-216_max_reward_20.27.json` | 38.9MB | 216 | 20.27 | 大网络，腿伸出问题 |
| `policy_rich-donkey-233_max_reward_19.16.json` | 38.9MB | 233 | 19.16 | 三足策略（改进版） |
| `policy_pretty-spaceship-243_max_reward_17.57.json` | 38.9MB | 243 | 17.57 | 四足重训练 |

### 策略演进历史

```
Run 216 (20.27分)
  ↓ 大网络，但腿伸出
Run 233 (19.16分)
  ↓ 改进为三足策略
Run 238 (未标明分数)
  ↓ 四足重训练1B步数
Run 243 (17.57分)
  ↓ 当前最新四足策略
```

---

## 二、各策略的损失/奖励函数配置

### 基础奖励函数（所有策略共享）

位于 `ai/rl/conf/reward/default.yaml`:

| 奖励项 | 权重 | 作用说明 |
|--------|------|---------|
| **tracking_lin_vel** | 1.5 | 鼓励机器人跟随手柄前进/左右速度命令 |
| **tracking_ang_vel** | 0.8 | 鼓励机器人跟随手柄转向命令 |
| **tracking_orientation** | 0.5 | 鼓励机器人保持直立姿态 |
| **lin_vel_z** | -0.1 | 惩罚上下跳动（不希望跳跃） |
| **ang_vel_xy** | -0.002 | 惩罚左右摇晃（不希望横滚/俯仰角速度） |
| **orientation** | -0.0 | 姿态惩罚（当前关闭） |
| **torques** | -0.025 | 能耗惩罚（鼓励节能） |
| **joint_acceleration** | -1e-6 | 加速度平滑惩罚 |
| **mechanical_work** | 0 | 机械功惩罚（当前关闭） |
| **action_rate** | -0.1 | 动作突变惩罚（鼓励平滑） |
| **feet_air_time** | 0.02 | 抬脚奖励（小值，轻微鼓励） |
| **stand_still** | -0.00 | 停止时姿态惩罚（当前关闭） |
| **stand_still_joint_velocity** | -0.2 | 停止时关节速度惩罚 |
| **abduction_angle** | -0.01 | 外展角度惩罚（不希望腿太开） |
| **termination** | -100.0 | 倒地惩罚（强烈避免摔倒） |
| **foot_slip** | -0.2 | 打滑惩罚 |
| **knee_collision** | -10.0 | 膝盖碰地惩罚 |
| **body_collision** | -0.5 | 本体碰地惩罚 |

### 各策略特殊配置

#### Run 216 - 大网络通用策略

**网络配置:**
```yaml
hidden_layer_sizes: [1024, 1024, 1024, 1024]  # 大网络
activation: "elu"
action_scale: 0.75
observation_history: 4
```

**特点:**
- 网络参数约12M
- 通用策略但会出现"腿伸出"问题
- 训练步数未明确，可能约300M

#### Run 233 - 三足改进策略

**网络配置:**
```yaml
hidden_layer_sizes: [256, 128, 128, 128]  # 默认网络
activation: "elu"
action_scale: [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0.1]  # 特殊配置
```

**三足配置说明:**
- 前11个关节正常scale=1.0
- 后左腿膝关节（第12个关节）scale=0.1（几乎禁用）
- 让机器人用3条腿走路

**特点:**
- 较小网络，推理更快
- 针对三足场景优化

#### Run 238 - 四足重训练

**网络配置:**
```yaml
hidden_layer_sizes: [256, 128, 128, 128]  # 默认网络
activation: "elu"
action_scale: 0.75  # 正常四足
observation_history: 4
```

**训练配置:**
```yaml
num_timesteps: 1000000000  # 1B步数
episode_length: 500
num_envs: 8192
```

**特点:**
- 训练步数最多（1B）
- 稳定的四足策略
- config.yaml 中 `neural_controller_three_legged` 引用此策略

#### Run 243 - 最新四足策略

**网络配置:**
```yaml
hidden_layer_sizes: [256, 128, 128, 128]  # 默认网络
activation: "elu"
action_scale: 0.75
observation_history: 4
```

**特点:**
- 当前默认策略（policy_latest.json）
- 分数略低于238但可能更稳定

---

## 三、完整控制映射链路

### 映射总览

```
PS5手柄
  ↓ (joy_linux_node)
/joy 话题
  ↓ (teleop_twist_joy_node)
/teleop_cmd_vel 话题
  ↓ (cmd_vel_mux)
/cmd_vel 话题
  ↓ (neural_controller)
关节命令发送到硬件
  ↓
12个伺服电机运动
```

### 详细映射过程

#### 步骤1: PS5手柄 → /joy

**节点:** `joy_linux_node`

**输出话题:** `/joy`

**消息内容:**
```cpp
// 标准PS5手柄映射
axes[0]  // 左摇杆Y轴 (左右平移)
axes[1]  // 左摇杆X轴 (前进/后退)
axes[2]  // 左摇杆L2按压力
axes[3]  // 右摇杆X轴 (转向)
axes[4]  // 右摇杆Y轴 (未使用)
axes[5]  // 右摇杆R2按压力
buttons[0]  // X按钮
buttons[1]  // O按钮
buttons[2]  // □按钮
buttons[3]  // △按钮
buttons[4]  // L1按钮
buttons[5]  // R1按钮
buttons[6]  // L2按钮
buttons[7]  // R2按钮
buttons[8]  // L3按钮 (左摇杆按下)
buttons[9]  // PS按钮
buttons[10] // Share按钮
buttons[11] // Options按钮
buttons[12] // R3按钮 (右摇杆按下)
buttons[13] // 触摸板
buttons[14] // 触摸板
```

#### 步骤2: /joy → /teleop_cmd_vel

**节点:** `teleop_twist_joy_node`

**配置参数 (config.yaml):**
```yaml
axis_linear:
  x: 1    # 左摇杆X轴
  y: 0    # 左摇杆Y轴
scale_linear:
  x: 0.75 # 前进/后退速度缩放
  y: 0.5  # 左右平移速度缩放
axis_angular:
  yaw: 3   # 右摇杆X轴
scale_angular:
  yaw: 2.0  # 转向速度缩放
```

**映射逻辑:**
```cpp
// 线速度 x (前进/后退)
cmd_vel.linear.x = joy.axes[1] * 0.75

// 线速度 y (左右平移)
cmd_vel.linear.y = joy.axes[0] * 0.5

// 角速度 yaw (转向)
cmd_vel.angular.z = joy.axes[3] * 2.0
```

**Twist消息格式:**
```
geometry_msgs/Twist
├── linear
│   ├── x:  0.75  (最大前进速度 m/s)
│   ├── y:  0.5   (最大侧移速度 m/s)
│   └── z:  0     (未使用)
└── angular
    └── z:  2.0    (最大转向速度 rad/s)
```

#### 步骤3: /cmd_vel → 神经网络观察

**节点:** `neural_controller`

**观察向量构成** (`kSingleObservationSize = 30`):

| 索引 | 观察项 | 说明 |
|------|---------|------|
| 0-2 | `ang_vel` (3) | 本体角速度 [roll, pitch, yaw]，来自IMU |
| 3-5 | `projected_gravity` (3) | 重力向量在本体坐标系投影 [gx, gy, gz]，初始为[0,0,-1] |
| 6-8 | `cmd_vel` (3) | 手柄命令 [x, y, yaw]，来自/cmd_vel话题 |
| 9-11 | `desired_world_z` (3) | 期望本体坐标系中的世界Z轴，初始为[0,0,1] |
| 12-23 | `joint_pos` (12) | 12个关节位置 - default_joint_pos |
| 24-35 | `last_action` (12) | 上一帧动作（历史） |

**观察历史:**
- `observation_history = 4` 表示保留4帧历史
- 完整观察向量大小 = 4 × 30 = 120

**代码实现 (neural_controller.cpp:466-490):**
```cpp
// 角速度 (IMU)
observation_.at(0) = (float)ang_vel_x;
observation_.at(1) = (float)ang_vel_y;
observation_.at(2) = (float)ang_vel_z;

// 投影重力向量
observation_.at(3) = (float)projected_gravity_vector[0];
observation_.at(4) = (float)projected_gravity_vector[1];
observation_.at(5) = (float)projected_gravity_vector[2];  // 初始为-1.0

// 命令速度 (手柄)
observation_.at(6) = (float)cmd_x_vel_;
observation_.at(7) = (float)cmd_y_vel_;
observation_.at(8) = (float)cmd_yaw_vel_;

// 期望姿态
observation_.at(9) = (float)desired_world_z_in_body_frame_.getX();
observation_.at(10) = (float)desired_world_z_in_body_frame_.getY();
observation_.at(11) = (float)desired_world_z_in_body_frame_.getZ();

// 关节位置 (12个关节)
for (int i = 0; i < 12; i++) {
    observation_.at(kJointPositionIdx + i) = joint_pos - params_.default_joint_pos.at(i);
}
```

#### 步骤4: 神经网络 → 动作输出

**网络前向传播:**
```cpp
// RTNeural推理
model_->forward(observation_.data());
```

**输出动作向量:** 12个关节的目标位置偏移

| 索引 | 关节名称 | 动作含义 |
|------|----------|---------|
| 0 | leg_front_r_1 | 前右腿髋关节外展/内收 |
| 1 | leg_front_r_2 | 前右腿髋关节屈曲/伸展 |
| 2 | leg_front_r_3 | 前右腿膝关节屈曲/伸展 |
| 3 | leg_front_l_1 | 前左腿髋关节外展/内收 |
| 4 | leg_front_l_2 | 前左腿髋关节屈曲/伸展 |
| 5 | leg_front_l_3 | 前左腿膝关节屈曲/伸展 |
| 6 | leg_back_r_1 | 后右腿髋关节外展/内收 |
| 7 | leg_back_r_2 | 后右腿髋关节屈曲/伸展 |
| 8 | leg_back_r_3 | 后右腿膝关节屈曲/伸展 |
| 9 | leg_back_l_1 | 后左腿髋关节外展/内收 |
| 10 | leg_back_l_2 | 后左腿髋关节屈曲/伸展 |
| 11 | leg_back_l_3 | 后左腿膝关节屈曲/伸展 |

**动作缩放和映射:**
```cpp
// 网络输出 → 实际关节位置
final_joint_pos = action * action_scale + default_joint_pos

// 其中:
// - action: 网络原始输出 (tanh激活后范围[-1,1])
// - action_scale: 缩放因子 (默认0.75)
// - default_joint_pos: 默认站立姿态
```

**default_joint_pos (config.yaml):**
```yaml
[0.26, 0.0, -0.52, -0.26, 0.0, 0.52, 0.26, 0.0, -0.52, -0.26, 0.0, 0.52]
// 髋外展   髋屈曲    膝屈曲
// [FR1,   FR2,      FR3,      FL1,   FL2,      FL3,      BR1,   BR2,      BR3,      BL1,   BL2,      BL3]
```

#### 步骤5: 动作 → 硬件控制

**发送给hardware_interface:**
```cpp
// 位置控制模式
for (int i = 0; i < 12; i++) {
    state_interfaces_[kPosIdx + i].set_value(final_joint_pos[i]);

    // 设置PD增益
    state_interfaces_[kKpIdx + i].set_value(kps[i]);
    state_interfaces_[kKdIdx + i].set_value(kds[i]);
}
```

**PD控制公式:**
```
torque = Kp * (target_pos - current_pos) + Kd * (target_vel - current_vel)
```

**默认增益:**
```yaml
kps:  [5.0] × 12
kds:  [0.25] × 12
```

---

## 四、PS5手柄完整按键映射

### 运动控制映射

| 手柄输入 | 对应轴/键 | 功能 | 映射速度 |
|----------|------------|------|---------|
| **左摇杆前推** | axes[1] > 0 | 前进 | 最大0.75 m/s |
| **左摇杆后拉** | axes[1] < 0 | 后退 | 最大-0.75 m/s |
| **左摇杆右推** | axes[0] > 0 | 右移 | 最大0.5 m/s |
| **左摇杆左推** | axes[0] < 0 | 左移 | 最大-0.5 m/s |
| **右摇杆右推** | axes[3] > 0 | 顺时针转 | 最大2.0 rad/s |
| **右摇杆左推** | axes[3] < 0 | 逆时针转 | 最大-2.0 rad/s |

### 功能按键映射

| 按键 | 按钮索引 | 功能 | 说明 |
|------|----------|------|------|
| **X** | 0 | 切换四足控制器 | 切换到 `neural_controller` |
| **O** | 1 | 切换三足控制器 | 切换到 `neural_controller_three_legged` |
| **L1** | 4 | 开始录制 | 按住1秒开始录制bag |
| **R1** | 5 | 停止录制 | 停止bag录制 |
| **R3** | 12 | **紧急停止** | 立即停止所有运动 |
| **PS** | 9 | 解除急停 | 恢复最近的控制器 |
| **△** | 3 | [未定义] | 预留用于动画触发 |
| **□** | 2 | [未定义] | 预留用于动画触发 |
| **L2** | 6 | [未定义] | 预留 |
| **R2** | 7 | [未定义] | 预留 |
| **Share** | 10 | [未定义] | 预留 |
| **Options** | 11 | [未定义] | 预留 |

### 控制器切换流程

```
[启动] → neural_controller (默认四足模式)
    |
    |→ 按 O → neural_controller_three_legged (三足模式)
    |
    |→ 按 X → neural_controller (四足模式)
    |
    |→ 按 R3 → [急停] 所有控制器关闭
    |
    |→ 按 PS → 恢复最近控制器
```

---

## 五、动画控制映射

### 动画播放触发方式

动画播放通过 ROS2 服务实现，当前代码中需要额外的节点将手柄按键映射到动画触发。

**现有机制:**
```python
# animation_controller_py 监听话题
/animation_controller_py/animation_select  # std_msgs/String

# 播放动画
ros2 topic pub /animation_controller_py/animation_select "data: 'sneeze'"
```

### 可用动画列表

| 动画名称 | 文件名 | 帧数 | 时长 | 描述 |
|----------|---------|------|------|------|
| sneeze | sneeze_recording_*.csv | ~130 | ~4s | 打喷嚏 |
| pee2 | pee2_recording_*.csv | ~280 | ~9s | 撒尿 |
| push_up | push_up_recording_*.csv | ~480 | ~16s | 俯卧撑 |
| swim | swim_recording_*.csv | ~430 | ~14s | 游泳 |
| twerk | twerk_recording_*.csv | ~450 | ~15s | Twerk舞蹈 |
| stand_sit_stand | stand_sit_stand_recording_*.csv | ~540 | ~18s | 站-坐-站 |
| spider | spider_recording_*.csv | ~520 | ~17s | 蜘蛛式 |
| superman | superman_recording_*.csv | ~680 | ~23s | 超人式 |
| lie_downward_dog | lie_downward_dog_recording_*.csv | ~390 | ~13s | 下犬式 |
| upward_dog | upward_dog_recording_*.csv | ~540 | ~18s | 上犬式 |

### 动画播放参数 (config.yaml)

```yaml
animation_controller_py:
  ros__parameters:
    frame_rate: 40.0          # 播放帧率
    init_duration: 1.0         # 初始化过渡时间（秒）
    kps: [7.5] × 12           # 播放时位置增益
    kds: [0.25] × 12          # 播放时阻尼增益
    init_kps: [7.5] × 12      # 初始化时增益
    init_kds: [0.25] × 12
```

### 动画播放流程

```
[触发动画]
    ↓
切换到 Forward Command Controllers (forward_kp/kd/position)
    ↓
初始化阶段 (1-2秒): 从当前姿态插值到动画起始位置
    ↓
播放阶段 (40Hz): 线性插值播放关键帧
    ↓
完成后: 返回 neural_controller
```

---

## 六、安全机制

### 紧急停止 (E-Stop)

**触发条件:**
1. 按下 R3 按钮
2. 机器人倾斜超过 `max_body_angle` (默认1.5弧度≈86°)
3. 检测到异常状态

**E-Stop行为:**
```cpp
// 设置高阻尼，快速停止所有运动
for (int i = 0; i < 12; i++) {
    state_interfaces_[kKdIdx + i].set_value(estop_kd);  // 0.1或0.3
}
```

**恢复方式:**
- 按下 PS 按钮
- 重新激活最近使用的控制器

### Fade-in 机制

**目的:** 启动时平滑过渡到RL控制

```cpp
// fade_in_multiplier: 0 → 1  在 fade_in_duration (1-2秒)内
fade_in_multiplier = min(time / fade_in_duration, 1.0);

// 最终关节命令
final_joint_pos = init_joint_pos + fade_in_multiplier * (target_pos - init_joint_pos);
```

---

## 七、快速参考

### 训练新策略时的奖励调整建议

| 想要的效果 | 关键参数调整 |
|----------|--------------|
| 更快的行走速度 | `tracking_lin_vel: 2.5`, `action_rate: -0.05` |
| 更平滑的步态 | `torques: -0.05`, `action_rate: -0.2` |
| 小跑步态 | `feet_air_time: 0.15`, `tracking_ang_vel: 1.2` |
| 跳跃动作 | `feet_air_time: 0.5`, `lin_vel_z: 0.2` |
| 三足模式 | 修改 `action_scale` 数组，禁用1个关节 |

### 从手柄到关节的完整数据流

```
[手柄摇杆]
  axes[1] = 0.5  (前推一半)
    ↓
  cmd_vel.linear.x = 0.5 × 0.75 = 0.375 m/s
    ↓
  observation[6] = 0.375
    ↓
  [神经网络推理]
    ↓
  action[1] = 0.2  (前右腿髋关节)
    ↓
  final_pos[1] = 0.2 × 0.75 + 0.0 = 0.15 rad
    ↓
  [硬件发送位置命令]
    ↓
  [伺服电机转动到0.15弧度]
```

---

*最后更新: 2026-04-11*
