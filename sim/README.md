# Pupper V3 Standalone MuJoCo Simulation

独立于 ROS2 的 MuJoCo 仿真环境，直接加载训练好的 RL 策略控制四足机器人行走。

## 前置条件

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)

## 安装

```bash
cd sim
uv sync
```

## 使用

```bash
# 拉取策略文件（Git LFS）
git lfs pull --include="ros2_ws/src/neural_controller/launch/policy_latest.json"

# 启动仿真
uv run python pupperv3_sim.py ../ros2_ws/src/neural_controller/launch/policy_latest.json
```

不带策略启动（零动作，仅渲染）：

```bash
uv run python pupperv3_sim.py
```

## 键盘控制

| 按键 | 功能 |
|------|------|
| `↑` / `↓` | 前进 / 后退 |
| `←` / `→` | 左平移 / 右平移 |
| `Z` / `X` | 左转 / 右转 |
| `C` | 归零速度指令 |
| `R` | 重置仿真 |

## 架构

```
pupperv3_sim.py   主循环：加载模型、策略推理、键盘监听、渲染
policy.py         RTNeural JSON 加载 + NumPy 前向传播
observations.py   36 维观测向量构造 + 历史缓冲
config.py         常量（关节名、默认姿态、物理参数）
```

## 关键设计

使用**训练时的 MuJoCo XML**（`pupper_v3_complete.mjx.position.xml`），而非 ROS2 部署版本。差异详见 `docs/plans/2026-04-13-mujoco-standalone-sim-design.md`。

- 物理步长 0.004s，策略推理 50Hz（每周期 5 步）
- PD 控制内置于 MuJoCo actuator（kp=5.0, kd=0.1）
- `data.ctrl` 设为目标关节位置，由 actuator 自动 PD 跟踪

## 测试

```bash
uv run pytest test_policy.py test_observations.py -v
```
