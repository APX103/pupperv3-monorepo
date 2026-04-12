# Pupper V3 架构文档

## Policy 存储格式

Policy 以单个 JSON 文件存储（约 25MB），基于 JAX/Haiku 导出。包含：

**元数据字段：**
- `use_imu`: 是否使用 IMU
- `control_orientation`: 是否进行姿态控制
- `observation_history`: 观测历史帧数（20）
- `action_scale`: 动作缩放因子（1.0）
- `kp` / `kd`: PD 控制器增益（5.0 / 0.25）
- `default_joint_pos`: 12 维默认关节位置
- `joint_upper_limits` / `joint_lower_limits`: 关节限位
- `in_shape`: 输入维度 [None, 720]

**网络结构（5 层 MLP）：**

| 层 | 类型 | 激活函数 | 权重形状 (kernel) | 偏置形状 |
|----|------|----------|-------------------|----------|
| 0  | dense | elu      | 720 x 1024        | 1024     |
| 1  | dense | elu      | 1024 x 512        | 512      |
| 2  | dense | elu      | 512 x 512         | 512      |
| 3  | dense | elu      | 512 x 512         | 512      |
| 4  | dense | tanh     | 512 x 12          | 12       |

总参数量：约 196 万。

**权重布局：** `layers[i].weights[0]` 为 kernel（shape [in, out]），`layers[i].weights[1]` 为 bias。计算为标准右乘：`output = input @ W + b`。

## 观测向量（单帧 36 维，总计 20x36=720 维）

| 索引   | 维度 | 描述                           |
|--------|------|--------------------------------|
| 0-2    | 3    | 机体角速度（陀螺仪 xyz）        |
| 3-5    | 3    | 投影重力向量（体坐标系）         |
| 6-8    | 3    | 速度指令（x, y, yaw）           |
| 9-11   | 3    | 期望 Z 轴方向（体坐标系）        |
| 12-23  | 12   | 关节位置 - 默认位置             |
| 24-35  | 12   | 上一步动作输出                   |

历史缓冲区初始值全零，重力 Z 分量（索引 5）初始化为 -1.0。

## 动作输出

网络输出 12 维 tanh 约束值 [-1, 1]，转换为关节指令：
```
joint_cmd[i] = clamp(fade_in * policy_output[i] * action_scale + default_joint_pos[i], lower, upper)
```

## 机器人结构

Pupper V3 四足机器人，12 个关节（4 腿 x 3 关节/腿）：

```
leg_front_r_1, leg_front_r_2, leg_front_r_3    # 前右
leg_front_l_1, leg_front_l_2, leg_front_l_3    # 前左
leg_back_r_1,  leg_back_r_2,  leg_back_r_3     # 后右
leg_back_l_1,  leg_back_l_2,  leg_back_l_3     # 后左
```

默认姿态：`[0.26, 0.0, -0.52, -0.26, 0.0, 0.52, 0.26, 0.0, -0.52, -0.26, 0.0, 0.52]`

## 现有 ROS2 仿真链路

```
PS4/PS5 手柄 → joy_linux → teleop_twist_joy → /teleop_cmd_vel
                                                    ↓
                                              cmd_vel_mux
                                                    ↓
                                          neural_controller (RTNeural)
                                                    ↓
                                          ros2_control → MuJoCo 硬件接口
                                                    ↓
                                             MuJoCo 仿真可视化
```

- 控制频率：500Hz，每 10 次执行一次 policy（50Hz 推理）
- cmd_vel_mux 优先级：teleop > llm > person_following
- MuJoCo XML 模型位于 `ros2_ws/src/pupper_v3_description/description/mujoco_xml/`

## RL 训练

- 框架：MJX（MuJoCo JAX）
- 训练脚本：`ai/rl/pupper_mjx_rl_training.py`
- 配置目录：`ai/rl/conf/`
- 模型下载：`python3 download_latest_policy.py`（从 WandB）
