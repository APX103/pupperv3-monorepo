# Pupper V3 实战开发指南

本文档提供完整的、可按步骤执行的教程。

---

## 目标一：重新训练步态

### 前置条件检查

在开始训练前，请确保：

```bash
# 检查GPU（训练需要NVIDIA GPU）
nvidia-smi

# 预期输出：看到GPU信息（如RTX 4090、A100等）
# 如果没有GPU，训练会非常慢或无法运行
```

### 步骤1：设置训练环境

```bash
# 进入训练目录
cd D:/work/pupperv3-monorepo/ai/rl

# 安装依赖（使用uv包管理器）
uv sync

# 测试配置是否正确
uv run python test_config.py

# 预期输出：ConfigDict(...) 没有错误
```

### 步骤2：理解配置文件

**奖励函数配置** (`conf/reward/default.yaml`):

```yaml
rewards:
  scales:
    # 跟踪奖励（让机器人跟随命令）
    tracking_lin_vel: 1.5      # 前进/左右速度奖励
    tracking_ang_vel: 0.8      # 转向速度奖励
    tracking_orientation: 0.5    # 姿态保持奖励

    # 惩罚项（让动作更平滑、节能）
    lin_vel_z: -0.1            # 不希望上下跳
    ang_vel_xy: -0.002         # 不希望左右摇晃
    torques: -0.025            # 不希望用力过大
    action_rate: -0.1           # 不希望动作突变

    # 行为奖励
    feet_air_time: 0.02         # 鼓励脚抬起来
    stand_still: -0.00          # 停止时保持默认姿态

    # 碰撞惩罚
    termination: -100.0          # 摔倒的惩罚
    foot_slip: -0.2            # 打滑惩罚
    knee_collision: -10.0        # 膝盖碰地惩罚
```

**训练参数配置** (`conf/training/default.yaml`):

```yaml
ppo:
  num_timesteps: 1000000000    # 训练总步数（10亿步）
  episode_length: 500          # 每回合500步（10秒）
  num_envs: 8192              # 并行运行8192个环境
  learning_rate: 3.0e-5         # 学习率
  batch_size: 256              # 批处理大小
```

### 步骤3：创建自定义训练配置

**场景A：训练快速行走**

创建 `conf/reward/fast_walk.yaml`:

```yaml
rewards:
  scales:
    tracking_lin_vel: 2.5      # 提高速度奖励
    tracking_ang_vel: 0.6
    tracking_orientation: 0.4
    lin_vel_z: -0.2            # 加强抑制上下跳
    ang_vel_xy: -0.005         # 加强抑制摇晃
    torques: -0.03             # 略微加强节能
    action_rate: -0.05          # 允许动作变化更快
    feet_air_time: 0.05         # 提高抬脚奖励
    stand_still: -0.00
    termination: -100.0
    foot_slip: -0.3
    knee_collision: -15.0
    body_collision: -0.8
  tracking_sigma: 0.25
```

**场景B：训练小跑步态**

创建 `conf/reward/trot.yaml`:

```yaml
rewards:
  scales:
    tracking_lin_vel: 2.0
    tracking_ang_vel: 1.0      # 提高转向奖励
    tracking_orientation: 0.5
    lin_vel_z: -0.15
    ang_vel_xy: -0.002
    torques: -0.025
    action_rate: -0.05          # 减少动作惩罚
    joint_acceleration: -1e-7     # 减少加速度惩罚
    feet_air_time: 0.15         # 显著提高抬脚奖励（小跑特征）
    stand_still: -0.00
    termination: -100.0
    foot_slip: -0.25
    knee_collision: -12.0
    body_collision: -0.6
  tracking_sigma: 0.25
```

**场景C：训练跳跃动作**

创建 `conf/reward/hop.yaml`:

```yaml
rewards:
  scales:
    tracking_lin_vel: 1.0        # 降低速度奖励
    tracking_ang_vel: 0.5
    tracking_orientation: 0.3
    lin_vel_z: 0.2             # 允许甚至鼓励上下运动
    ang_vel_xy: -0.002
    torques: -0.02
    action_rate: -0.1
    joint_acceleration: -1e-7
    feet_air_time: 0.5          # 大幅鼓励腾空时间（跳跃特征）
    stand_still: -0.00
    termination: -100.0
    foot_slip: -0.15
    knee_collision: -20.0         # 加强膝盖保护
    body_collision: -1.0
  tracking_sigma: 0.25
```

### 步骤4：开始训练

```bash
cd D:/work/pupperv3-monorepo/ai/rl

# 选项1：使用默认配置快速测试（1000万步，约10分钟）
uv run python pupper_mjx_rl_training.py training.ppo.num_timesteps=10000000

# 选项2：使用自定义奖励配置
uv run python pupper_mjx_rl_training.py reward=fast_walk

# 选项3：组合多个参数
uv run python pupper_mjx_rl_training.py \
    reward=trot \
    training.ppo.num_timesteps=50000000 \
    policy.hidden_layer_sizes=[256,128,128,128]

# 选项4：从已有checkpoint继续训练
uv run python pupper_mjx_rl_training.py training.checkpoint_run_number=243
```

**训练过程中会发生什么：**

1. 环境初始化（约30秒）
2. 模型benchmark测试（约10秒）
3. 开始PPO训练循环
4. 每10万步评估一次策略
5. WandB显示训练曲线（如果配置了）

**预期输出示例：**

```
Installation successful.
Steps per sec:  2500000
Using hands-on-robotics W&B team.
output_2024-04-11_14-30-00/policy_xxx_max_reward_yy.zz.json
time to jit: 12.5
time to train: 7200
```

### 步骤5：查看训练输出

训练完成后，输出在 `ai/rl/outputs/` 目录：

```bash
# 查看输出目录
ls -la ai/rl/outputs/

# 预期看到类似：
# output_2024-04-11_14-30-00/
#   ├── policy_xxx_max_reward_yy.zz.json    # 可部署的策略
#   └── mjx_params_xxx                   # 完整checkpoint
```

**策略文件格式：**
- `policy_*.json` - RTNeural格式，可直接部署
- 文件大小约2-40MB（取决于网络大小）

### 步骤6：调整训练参数的技巧

| 想要的效果 | 修改参数 |
|----------|----------|
| 训练更快 | `training.ppo.num_timesteps=10000000` |
| 用更大网络 | `policy.hidden_layer_sizes=[512,256,256,256]` |
| 用更小网络 | `policy.hidden_layer_sizes=[128,64,64,64]` |
| 训练复杂地形 | `training.height_field_random=true` |
| 从头开始 | `training.checkpoint_run_number=null` |

---

## 目标二：仿真和可视化

### 步骤1：构建仿真环境

```bash
cd D:/work/pupperv3-monorepo/ros2_ws

# 构建整个workspace
./build.sh

# 或者手动构建
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=RelWithDebInfo

# 预期输出：
# Starting >>> pupperv3_mujoco_sim
# ...
# Finished <<< pupperv3_mujoco_sim
```

### 步骤2：启动MuJoCo仿真

```bash
# 激活环境
source install/local_setup.bash

# 启动仿真（硬件接口模式）
ros2 launch neural_controller launch_sim.py
```

**预期行为：**
1. MuJoCo窗口打开，显示3D机器人模型
2. 机器人执行初始化姿态（约1秒）
3. 等待控制命令

### 步骤3：手动控制机器人

```bash
# 在另一个终端
source install/local_setup.bash

# 连接手柄并控制
ros2 launch neural_controller launch.py

# 操作说明：
# 左摇杆上下：前进/后退
# 左摇杆左右：左右移动
# 右摇杆左右：转向
# R2按钮：急停（estop）
```

### 步骤4：使用Foxglove可视化

```bash
# 方式1：直接启动Foxglove bridge
ros2 run foxglove_bridge foxglove_bridge

# 方式2：通过launch启动（推荐）
ros2 launch neural_controller launch.py
# launch.py已包含Foxglove bridge

# 然后在电脑上：
# 1. 打开Foxglove Studio
# 2. 连接到 ws://localhost:8765
# 3. 导入布局文件查看机器人状态
```

**可观察的数据：**
- 关节位置/速度
- IMU数据（加速度、角速度）
- 命令速度
- 可视化3D模型

### 步骤5：训练时生成视频

训练脚本已包含视频生成，使用 `mediapy`：

```python
# 在训练代码中已包含
media.show_video(
    eval_env.render(rollout[::render_every], camera='tracking_cam'),
    fps=1.0 / eval_env.dt / render_every,
    codec='gif'
)
```

视频保存在训练输出目录，可以用浏览器打开查看。

---

## 目标三：部署训练好的策略到机器人

### 步骤1：准备策略文件

```bash
# 确保你有训练好的policy.json
# 假设在 ai/rl/outputs/output_xxx/policy_xxx_max_reward_yy.zz.json

# 复制到正确位置
cp ai/rl/outputs/output_xxx/policy_xxx_max_reward_yy.zz.json \
   ros2_ws/src/neural_controller/launch/my_policy.json
```

### 步骤2：更新配置文件

编辑 `ros2_ws/src/neural_controller/launch/config.yaml`:

```yaml
# 找到这一行（第86行）：
# model_path: "$(find-pkg-share neural_controller)/launch/policy_latest.json"

# 改为：
model_path: "$(find-pkg-share neural_controller)/launch/my_policy.json"
```

或者你可以直接覆盖现有策略：

```bash
# 直接覆盖默认策略
cp ai/rl/outputs/output_xxx/policy_xxx_max_reward_yy.zz.json \
   ros2_ws/src/neural_controller/launch/policy_latest.json
```

这样不需要修改config.yaml。

### 步骤3：在仿真中测试

```bash
cd ros2_ws

# 重新构建（确保新配置生效）
./build.sh

# 启动仿真测试
source install/local_setup.bash
ros2 launch neural_controller launch_sim.py

# 如果机器人行为正常，继续部署到真实硬件
```

### 步骤4：部署到真实机器人

```bash
# SSH到机器人
ssh pi@pupper.local

# 停止自动启动的机器人服务
sudo systemctl stop robot
sudo systemctl disable robot

# 进入工作目录
cd ~/pupperv3-monorepo

# 上传你的策略文件（从本机）
# 在本机执行：
scp ros2_ws/src/neural_controller/launch/my_policy.json \
    pi@pupper.local:~/pupperv3-monorepo/ros2_ws/src/neural_controller/launch/

# 在机器人上执行：
cd ~/pupperv3-monorepo/ros2_ws
./build.sh

# 启动机器人
ros2 launch neural_controller launch.py
```

### 步骤5：验证部署

```bash
# 在机器人上，观察：
# 1. 机器人初始化到站立姿态（约1-2秒）
# 2. 使用手柄控制，机器人应响应命令
# 3. 检查/joint_states话题，确认关节运动正常

# 如有问题，检查：
ros2 topic echo /joint_states --once
```

---

## 目标四：添加新的动画动作

### 步骤1：在机器人上录制动作

```bash
# SSH到机器人
ssh pi@pupper.local

# 确保机器人服务正在运行
ros2 launch neural_controller launch.py

# 开始录制
# 按住手柄 L1 按钮（约1秒）开始录制
# BAG状态图标变绿表示正在录制

# 执行你想要录制的动作
# 例如：做一个新的舞蹈动作

# 停止录制
# 按手柄 R1 按钮停止录制
```

录制的bag文件保存在 `~/bags/` 目录，格式为：
`动作名_recording_YYYY-MM-DD_HH-MM-SS_0.mcap`

### 步骤2：查看录制内容

```bash
# 在机器人上，安装Foxglove后查看
ros2 run foxglove_bridge foxglove_bridge

# 或用mcap工具查看bag内容
ros2 bag info ~/bags/your_action.mcap

# 预期输出：
# Duration: 12.5 seconds
# Message count: 15991
# Topics: /joint_states (4591 messages)
```

### 步骤3：转换为CSV格式

```bash
cd ~/pupperv3-monorepo

# 使用转换脚本
python scripts/mcap_to_csv.py \
    ~/bags/your_action.mcap \
    -s ABSOLUTE_START_TIME \
    -e ABSOLUTE_END_TIME

# 如果不确定时间，可以只用开始时间
python scripts/mcap_to_csv.py ~/bags/your_action.mcap -s 0

# 转换后的CSV文件
# 保存到 bags/ 目录
```

### 步骤4：移动到正确位置

```bash
# 复制CSV到动画目录
cp bags/your_action_recording_*.csv \
    ros2_ws/src/animation_controller_py/launch/animations/my_action.csv

# 验证文件
ls -la ros2_ws/src/animation_controller_py/launch/animations/
```

### 步骤5：重新构建

```bash
cd ~/pupperv3-monorepo/ros2_ws
./build.sh

# 预期输出：
# Starting >>> animation_controller_py
# Finished <<< animation_controller_py
```

### 步骤6：测试新动作

```bash
# 启动机器人
ros2 launch neural_controller launch.py

# 播放新动作
ros2 topic pub --once /animation_controller_py/animation_select \
    std_msgs/String "data: 'my_action'"

# 机器人应该执行你录制的动作
```

**动画播放流程：**
1. 控制器从neural切换到forward模式
2. 初始化阶段（1-2秒）：平滑移动到动画起始位置
3. 播放阶段：以40Hz播放关键帧
4. 完成后自动返回neural模式

---

## 故障排除

### 训练问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| `Cannot communicate with GPU` | 没有GPU或驱动问题 | 检查nvidia-smi，安装正确的驱动 |
| 训练速度很慢 | GPU内存不足 | 减少 `training.ppo.num_envs` 到 4096 |
| 奖励一直很低 | 配置有问题 | 检查奖励权重是否冲突 |
| 策略部署后不工作 | 网络结构不匹配 | 确认训练和部署的hidden_layer_sizes一致 |

### 仿真问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| MuJoCo窗口打不开 | glfw库缺失 | `sudo apt install libglfw3-dev` |
| 机器人倒下 | 初始姿态错误 | 检查 `default_joint_pos` 配置 |
| 没有3D显示 | EGL后端问题 | 设置 `MUJOCO_GL=egl` 环境变量 |

### 部署问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 机器人不动 | 策略路径错误 | 检查 config.yaml 中的 model_path |
| 关节抖动 | Kp/Kd参数不合适 | 调整 init_kps 和 init_kds |
| 急停频繁触发 | max_body_angle太小 | 增加 config.yaml 中的 max_body_angle |

---

## 配置文件速查表

| 文件 | 用途 | 关键参数 |
|------|------|---------|
| `ai/rl/conf/training/default.yaml` | 训练设置 | num_timesteps, num_envs, learning_rate |
| `ai/rl/conf/reward/default.yaml` | 奖励函数 | tracking_lin_vel, feet_air_time, torques |
| `ai/rl/conf/policy/default.yaml` | 网络结构 | hidden_layer_sizes, activation |
| `ros2_ws/src/neural_controller/launch/config.yaml` | 部署配置 | model_path, kps, kds |

---

## 现有策略列表

当前已训练的策略（`ros2_ws/src/neural_controller/launch/`）：

| 策略文件 | 大小 | 说明 |
|----------|------|------|
| `policy.json` | 1.2MB | 小网络策略，快速推理 |
| `policy_latest.json` | 38.9MB | 最新训练的策略 |
| `policy_ancient-surf-216_max_reward_20.27.json` | 38.9MB | Run 216，奖励20.27 |
| `policy_pretty-spaceship-243_max_reward_17.57.json` | 38.9MB | Run 243，奖励17.57 |
| `policy_rich-donkey-233_max_reward_19.16.json` | 38.9MB | Run 233，3腿策略，奖励19.16 |

---

## 现有动画列表

当前可用的动画（`ros2_ws/src/animation_controller_py/launch/animations/`）：

| 动作文件 | 帧数 | 描述 |
|----------|------|------|
| `sneeze_recording_*.csv` | ~130 | 打喷嚏动作 |
| `pee2_recording_*.csv` | ~280 | 撒尿动作 |
| `push_up_recording_*.csv` | ~480 | 俯卧撑 |
| `swim_recording_*.csv` | ~430 | 游泳动作 |
| `twerk_recording_*.csv` | ~450 | Twerk舞蹈 |
| `stand_sit_stand_recording_*.csv` | ~540 | 站-坐-站 |
| `spider_recording_*.csv` | ~520 | 蜘蛛式 |
| `superman_recording_*.csv` | ~680 | 超人式 |
| `lie_downward_dog_recording_*.csv` | ~390 | 下犬式 |
| `upward_dog_recording_*.csv` | ~540 | 上犬式 |

---

## 快速开始指南

### 我想快速测试仿真

```bash
cd ros2_ws
source build.sh
ros2 launch neural_controller launch_sim.py
```

### 我想用现有策略

不需要训练，直接使用：

```bash
# 配置已指向 policy_latest.json
cd ros2_ws
source build.sh
ros2 launch neural_controller launch_sim.py  # 仿真
# 或
ros2 launch neural_controller launch.py      # 真实机器人
```

### 我想训练一个快速走路策略

```bash
cd ai/rl
uv run python pupper_mjx_rl_training.py \
    reward=fast_walk \
    training.ppo.num_timesteps=50000000
```

### 我想添加新动画

1. 在机器人上：按L1开始录制 → 做动作 → 按R1停止
2. 在机器人上：`python scripts/mcap_to_csv.py ~/bags/xxx.mcap -s 0`
3. 复制CSV到 `animation_controller_py/launch/animations/`
4. `cd ros2_ws && ./build.sh`

---

*最后更新: 2026-04-11*
