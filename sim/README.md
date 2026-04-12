# Pupper V3 纯 MuJoCo 仿真

独立于 ROS2 的 MuJoCo 仿真环境，使用 numpy 加载 RL policy 权重进行推理，键盘控制机器人运动。

## 前置要求

- Python >= 3.10
- [uv](https://docs.astral.sh/uv/)
- Windows / Linux / macOS

## 快速开始

```bash
cd sim
uv sync
uv run python run.py
```

## 键位

| 按键 | 功能 |
|------|------|
| ↑ / ↓ | 前进 / 后退 |
| ← / → | 左移 / 右移 |
| PgUp / PgDn | 左转 / 右转 |
| Space | E-Stop（按住松开恢复） |
| R | 重置机器人姿态 |
| Esc | 退出 |

> WASDQE 也可用，但可能与 MuJoCo viewer 快捷键冲突。方向键无冲突。

## 切换 Policy

```bash
# 默认使用 policy_latest.json
uv run python run.py

# 指定其他 policy
uv run python run.py --policy ../ros2_ws/src/neural_controller/launch/policy_ancient-surf-216_max_reward_20.27.json
uv run python run.py --policy ../ros2_ws/src/neural_controller/launch/policy_rich-donkey-233_max_reward_19.16.json

# 指定其他 MuJoCo 模型
uv run python run.py --model ../ros2_ws/src/pupper_v3_description/description/mujoco_xml/pupper_v3_complete.position.xml
```

```sh
uv run python run.py --model ../ros2_ws/src/pupper_v3_description/description/mujoco_xml/pupper_v3_complete.position.xml  --policy ../ros2_ws/src/neural_controller/launch/policy_rich-donkey-233_max_reward_19.16.json
```

## 可用 Policy

| 文件 | 最高奖励 |
|------|----------|
| `policy_latest.json` | — |
| `policy_ancient-surf-216_max_reward_20.27.json` | 20.27 |
| `policy_rich-donkey-233_max_reward_19.16.json` | 19.16 |
| `policy_pretty-spaceship-243_max_reward_17.57.json` | 17.57 |

## 原理

- **MuJoCo XML** 引用 STL mesh 渲染机器人模型，包含 IMU 传感器（陀螺仪、加速度计、姿态四元数）
- **Policy** 从 Haiku/JAX 导出的 JSON 加载 5 层 MLP 权重（720→1024→512→512→512→12），用 numpy 前向推理
- **观测向量** 720 维 = 20 帧历史 × 36 维/帧（角速度、重力投影、速度指令、关节位置偏差、上一步动作）
- **键盘输入** 映射为速度指令灌入观测向量，policy 输出 12 维关节位置目标通过 PD actuator 驱动
