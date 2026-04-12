# Pupper V3 开发指南

本文档记录了Pupper V3机器人固件开发的详细说明。

---

## 一、强化学习训练（RL）

### 1.1 训练框架

| 组件 | 说明 |
|------|------|
| 物理引擎 | MuJoCo + MJX (Google JAX加速版) |
| RL算法 | PPO (Proximal Policy Optimization) |
| 框架 | Brax + Hydra配置管理 |
| 主训练文件 | `ai/rl/pupper_mjx_rl_training.py` |
| 使用文件 | `ai/rl/pupper_mjx_rl_use_this.py` |

### 1.2 配置文件结构

```
ai/rl/conf/
├── config.yaml              # 主配置入口
├── training/default.yaml     # PPO训练参数
├── reward/default.yaml       # 奖励函数权重
├── policy/default.yaml       # 神经网络架构
├── simulation/default.yaml   # 仿真环境设置
└── export/default.yaml       # 策略导出配置
```

### 1.3 关键可调参数

#### 奖励函数 (`reward/default.yaml`)
```yaml
rewards:
  scales:
    # 跟踪奖励
    tracking_lin_vel: 1.5      # 线速度跟踪权重
    tracking_ang_vel: 0.8      # 角速度跟踪权重
    tracking_orientation: 0.5    # 姿态跟踪权重

    # 正则化惩罚
    lin_vel_z: -0.1            # 垂直速度惩罚
    ang_vel_xy: -0.002         # 横滚/俯仰角速度惩罚
    torques: -0.025            # 关节扭矩惩罚
    action_rate: -0.1           # 动作变化率惩罚

    # 行为奖励
    feet_air_time: 0.02         # 脚部腾空时间奖励
    stand_still: -0.00          # 零命令时的姿态惩罚

    # 碰撞惩罚
    termination: -100.0          # 终止条件惩罚
    foot_slip: -0.2            # 足部打滑惩罚
    knee_collision: -10.0        # 膝盖碰撞惩罚
    body_collision: -0.5         # 本体碰撞惩罚
```

#### 训练参数 (`training/default.yaml`)
```yaml
ppo:
  num_timesteps: 1000000000    # 总训练步数
  episode_length: 500          # 每回合步数
  num_envs: 8192              # 并行环境数
  learning_rate: 3.0e-5         # 学习率
  entropy_cost: 1e-2           # 熵正则化
  batch_size: 256              # 批大小

# 命令采样
lin_vel_x_range: [-0.75, 0.75]
lin_vel_y_range: [-0.5, 0.5]
ang_vel_yaw_range: [-2.0, 2.0]

# 终止条件
terminal_body_z: 0.05           # 身体高度阈值
terminal_body_angle: 0.70       # 身体角度阈值
```

### 1.4 训练不同风格步态的奖励调整

| 步态风格 | 奖励调整 | 说明 |
|----------|----------|------|
| **小跑 (Trot)** | `feet_air_time: 0.05-0.1`<br>`tracking_lin_vel: 2.0`<br>`action_rate: -0.05` | 鼓励更长腾空时间，加快速度，减少动作变化惩罚 |
| **高步频 (Prance)** | `feet_air_time: 0.1-0.2`<br>`joint_acceleration: -1e-7`<br>`lin_vel_x_range: [1.0, 2.0]` | 大幅鼓励腾空，减少加速度惩罚，提高命令速度 |
| **跳跃 (Hop)** | `feet_air_time: 0.3-0.5`<br>`knee_collision: -20.0`<br>`lin_vel_z_tracking: 增加` | 大幅鼓励腾空，加强膝盖碰撞保护，增加垂直跟踪 |

### 1.5 训练命令

```bash
cd ai/rl

# 安装依赖
uv sync

# 基础训练
uv run python pupper_mjx_rl_training.py

# 快速测试
uv run python pupper_mjx_rl_training.py training.ppo.num_timesteps=10000000

# 调整网络结构
uv run python pupper_mjx_rl_training.py policy.hidden_layer_sizes=[128,64,64,64]

# 启用地形训练
uv run python pupper_mjx_rl_training.py training.height_field_random=true

# 从checkpoint继续
uv run python pupper_mjx_rl_training.py training.checkpoint_run_number=238
```

### 1.6 训练输出

| 输出 | 位置 | 说明 |
|------|------|------|
| Policy文件 | `output_{run_name}/policy_*.json` | RTNeural格式的部署策略 |
| Checkpoints | `output_{run_name}/mjx_params_*` | MJX模型参数 |
| WandB日志 | `hands-on-robotics/pupperv3-mjx-rl` | 可视化训练过程 |

### 1.7 策略导出和部署

```python
# 训练完成后导出
from pupperv3_mjx import export
params_rtneural = export.convert_params(
    params,
    activation="elu",
    action_scale=0.75,
    kp=5.0,
    kd=0.25,
    final_activation="tanh"
)

# 保存为JSON
import json
with open("policy.json", "w") as f:
    json.dump(params_rtneural, f)
```

---

## 二、MuJoCo 仿真

### 2.1 仿真目录结构

```
ros2_ws/src/pupperv3_mujoco_sim/
├── include/
│   ├── mujoco_hardware_interface.hpp  # ROS2硬件接口
│   └── mujoco_core_interactive.hpp  # MuJoCo核心封装
├── src/
│   ├── mujoco_hardware_interface.cpp
│   └── uitools.c                  # 可视化工具
├── third_party/mujoco-2.3.1/       # MuJoCo库
└── launch/
    ├── test_hw_interface.launch.py    # 硬件接口模式
    └── floating_base_launch.py       # 浮动基座模式
```

### 2.2 仿真启动

#### 硬件接口模式（推荐）
```bash
cd ros2_ws
source build.sh
ros2 launch pupper_mujoco_sim test_hw_interface.launch.py
```

#### 独立仿真模式
```bash
cd ros2_ws/build/pupperv3_mujoco_sim
./simulate
```

### 2.3 可用模型文件

在 `ros2_ws/src/pupper_v3_description/description/mujoco_xml/`:

| 模型文件 | 说明 |
|----------|------|
| `pupper_v3_complete.mjx.xml` | 完整模型，3Nm最大力矩 |
| `pupper_v3_complete.mjx.position.xml` | 位置控制版本 |
| `pupper_v3_complete.fixed_base.xml` | 固定基座版本 |
| `model_with_obstacles.xml` | 带障碍物模型 |

### 2.4 可视化方法

| 方法 | 说明 |
|------|------|
| **MuJoCo内置** | 交互式3D视图、实时关节控制、传感器数据显示 |
| **Foxglove Studio** | ROS2话题可视化，需要 `ros2 run foxglove_bridge foxglove_bridge` |
| **mediapy** | 训练时生成视频 |
| **RViz2** | 通过 robot_state_publisher 可视化 |

### 2.5 仿真与真实硬件的差异

| 方面 | 仿真 | 真实硬件 |
|------|------|------|
| **动力学** | 精确控制，简化伺服模型 | 存在摩擦、延迟、非线性 |
| **传感器** | 理想模型，有限噪声模拟 | 漂移、量化误差、真实噪声 |
| **物理** | 地面接触简化，可调摩擦 | 复杂材料特性、环境因素 |
| **控制** | 200Hz统一接口 | 相同接口，硬件限制 |
| **优势** | 无损坏风险、快速迭代、完整可观测 | 真实物理反馈 |

---

## 三、动画动作系统

### 3.1 系统架构

```
录制层 → 处理层 → 播放层 → 编辑层
  .mcap    →   CSV   →  ROS2  →  可视化
```

### 3.2 animation_controller_py 工作机制

**控制流程：**

1. **初始化阶段** (2秒)
   - 使用高Kp值（7.5）快速移动到起始位置
   - 记录当前关节位置作为参考

2. **动画播放阶段**
   - 30Hz帧率插值播放
   - 使用低Kp值（5.0）平滑控制
   - 线性插值实现流畅过渡

3. **控制器切换**
   - 从 neural controllers 切换到 forward controllers
   - 发布位置、Kp、Kd三个命令话题

### 3.3 添加新动画动作

```bash
# 1. 录制动作（在机器人上）
ros2 bag record /joint_states -o my_action.mcap

# 2. 转换为CSV（在机器人上）
python scripts/mcap_to_csv.py my_action.mcap -s START -e END

# 3. 复制到正确位置
cp my_action.csv ros2_ws/src/animation_controller_py/launch/animations/

# 4. 重新构建
cd ros2_ws && ./build.sh
```

### 3.4 现有动作列表

| 动作 | 描述 |
|------|------|
| `knees` | 膝盖动作 |
| `lie_downward_dog` | 下犬式(瑜伽) |
| `push_up` | 俯卧撑 |
| `sneeze` | 打喷嚏 |
| `spider` | 蜘蛛式 |
| `stand_sit_shake_stand` | 站-坐-抖动-站 |
| `superman` | 超人式 |
| `swim` | 游泳动作 |
| `upward_dog` | 上犬式 |

---

## 四、部署流程

### 4.1 部署到仿真

```bash
cd ros2_ws

# 1. 放置策略文件
cp your_policy.json src/neural_controller/launch/

# 2. 更新配置
# 编辑 src/neural_controller/launch/config.yaml
# model_path: "$(find-pkg-share neural_controller)/launch/your_policy.json"

# 3. 启动仿真
source build.sh
ros2 launch neural_controller launch_sim.py
```

### 4.2 部署到真实机器人

```bash
# 1. SSH到机器人
ssh pi@pupper.local

# 2. 停止服务
sudo systemctl disable robot
sudo systemctl stop robot

# 3. 复制策略文件
cd ~/pupperv3-monorepo/ros2_ws/src/neural_controller/launch/
# 上传你的 policy.json

# 4. 重建
cd ~/pupperv3-monorepo/ros2_ws
./build.sh

# 5. 启动
ros2 launch neural_controller launch.py
```

---

## 五、快速参考

### 5.1 常用命令

```bash
# 训练RL策略
cd ai/rl && uv run python pupper_mjx_rl_training.py

# 启动仿真
cd ros2_ws && source build.sh && ros2 launch pupper_mujoco_sim test_hw_interface.launch.py

# 启动Foxglove
ros2 run foxglove_bridge foxglove_bridge

# 转换bag到csv
python scripts/mcap_to_csv.py input.mcap -s START -e END
```

### 5.2 配置文件位置速查

| 配置 | 路径 |
|------|------|
| 训练参数 | `ai/rl/conf/training/default.yaml` |
| 奖励函数 | `ai/rl/conf/reward/default.yaml` |
| 策略架构 | `ai/rl/conf/policy/default.yaml` |
| 部署配置 | `ros2_ws/src/neural_controller/launch/config.yaml` |
| 动画CSV | `ros2_ws/src/animation_controller_py/launch/animations/*.csv` |

---

## 六、已知检查点

从代码注释中已知的训练检查点：

| Run # | 描述 |
|-------|------|
| 202 | 通用策略 |
| 206 | 仅前进策略 |
| 207 | 快速前进策略 |
| 208 | 快速前进策略（1.5倍action scale） |
| 218 | 12M参数策略 (2024,2024,2024,2024) |
| 221 | 使用 (1024,1024,1024,1024) |
| 225 | 3腿策略 |
| 226 | 更长3腿策略 |
| 227 | 2腿策略 |
| 233 | 改进3腿策略 |
| 235 | 3腿（左前腿离地） |
| 238 | 4腿重训练1B |

---

*最后更新: 2026-04-11*
