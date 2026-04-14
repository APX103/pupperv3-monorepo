# Pupper V3 启动指南

## 开机自启

机器人开机后，systemd 自动启动 `robot.service`，执行：

```bash
source /opt/ros/jazzy/setup.bash
source /home/pi/pupperv3-monorepo/ros2_ws/install/local_setup.bash
ROS_LOCALHOST_ONLY=1 ros2 launch neural_controller launch.py
```

所有默认参数：`sim:=False teleop:=True bag_recorder:=True hailo:=False`

## 手动启动（开发机）

```bash
source /opt/ros/humble/setup.bash
source $HOME/pupperv3-monorepo/ros2_ws/install/local_setup.bash

# 实体机器人（默认）
ros2 launch neural_controller launch.py

# 仿真器模式
ros2 launch neural_controller launch.py sim:=True

# 启用 Hailo 物体检测 + 人员跟随
ros2 launch neural_controller launch.py hailo:=True

# 关闭手柄控制 / bag录制
ros2 launch neural_controller launch.py teleop:=False bag_recorder:=False
```

## Launch 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `sim` | `False` | `True` 运行 MuJoCo 仿真，`False` 运行实体机器人 |
| `teleop` | `True` | `True` 启动手柄遥控节点 |
| `bag_recorder` | `True` | `True` 启用数据包录制节点 |
| `hailo` | `False` | `True` 启用 Hailo 检测和人员跟随（需要 Hailo 硬件） |

## 手柄操作

使用 PS4/PS5 蓝牙手柄，连接后自动识别为 `/dev/input/js0`。

### 按键功能

| 按键 | 索引 | 功能 |
|------|------|------|
| X | 0 | 切换到四足行走控制器 |
| O | 1 | 切换到三足行走控制器 |
| L1 | 4 | 长按 1 秒开始录制 bag |
| R1 | 5 | 停止录制 bag |
| Start | 9 | 解除急停，恢复上一个控制器 |
| R3（右摇杆按下）| 12 | **急停**（立即停机） |

### 摇杆控制

| 摇杆 | 轴 | 功能 | 灵敏度 |
|------|-----|------|--------|
| 左摇杆 Y | 轴 1 | 前进 / 后退 | 0.75 |
| 左摇杆 X | 轴 0 | 左右平移 | 0.5 |
| 右摇杆 X | 轴 3 | 原地旋转 | 2.0 |

## 启动后如何让机器人走路

1. 开机 → systemd 自动启动所有节点，所有控制器处于 **inactive** 状态，机器人保持静止
2. 连接蓝牙手柄
3. 按 **X 键** → 激活四足神经网络行走控制器
   - 1 秒内插值到默认站立姿态
   - 再 1 秒内渐入策略输出
   - 之后策略以 ~50 Hz 运行
4. 用左摇杆控制行走，右摇杆控制转向
5. 随时按 **R3** 急停，按 **Start** 恢复

## 节点架构

```
蓝牙手柄 → joy_linux_node → /joy
                              ├→ teleop_twist_joy → /teleop_cmd_vel
                              ├→ joy_util_node → 急停 / 切换控制器
                              └→ bag_recorder → 录制控制

              /teleop_cmd_vel ─┐
              /llm_cmd_vel    ─┤→ cmd_vel_mux_node → /cmd_vel
              /person_following_cmd_vel ─┘

/camera → hailo_detection → /detections → person_follower → /person_following_cmd_vel
                                          (仅 hailo:=True 时启动)

/cmd_vel + IMU + 关节状态 → neural_controller (RTNeural, ~50Hz) → 12 关节指令
```

### 核心节点列表

| 节点 | 功能 |
|------|------|
| `ros2_control_node` | 控制器管理器，520 Hz 主循环 |
| `neural_controller` | 四足 RL 行走策略（RTNeural 推理） |
| `neural_controller_three_legged` | 三足行走策略（备选） |
| `joy_linux_node` | 蓝牙手柄驱动 |
| `joy_util_node` | 急停和控制器切换 |
| `teleop_twist_joy_node` | 摇杆 → 速度指令 |
| `cmd_vel_mux_node` | 多源速度指令优先级复用 |
| `animation_controller_py_node` | 预录制动画播放 |
| `bag_recorder_node` | 手柄触发数据录制 |
| `imu_to_tf_node` | IMU → TF 坐标变换 |
| `robot_state_publisher` | URDF → TF |
| `camera_node` | 摄像头（仅实体机器人） |
| `foxglove_bridge` | Foxglove 可视化桥接 |
| `hailo_detection_node` | Hailo 物体检测（仅 `hailo:=True`） |
| `person_follower_node` | 人员跟随（仅 `hailo:=True`） |

### 速度指令优先级（cmd_vel_mux）

1. `/teleop_cmd_vel` — 手柄（最高优先）
2. `/llm_cmd_vel` — LLM 语音控制
3. `/person_following_cmd_vel` — 人员跟随

## 仿真器模式

```bash
ros2 launch neural_controller launch.py sim:=True
```

- 使用 `pupper_v3_mujoco.urdf.xacro`（MuJoCo 硬件接口）
- 不启动摄像头节点
- 其余行为与实体机器人一致

## 构建工作区

```bash
cd ~/pupperv3-monorepo/ros2_ws
colcon build --cmake-args -DCMAKE_BUILD_TYPE=RelWithDebInfo -DPython3_EXECUTABLE=/usr/bin/python3 -DCMAKE_CXX_FLAGS="-g0"
```
