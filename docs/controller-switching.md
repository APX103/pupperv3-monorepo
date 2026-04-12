# 控制器切换机制

## 概述

Pupper V3 支持在多个 neural controller 之间热切换（如四足↔三足 policy），切换过程中机器人不会倒下。核心是一个 **init + fade-in 三阶段平滑过渡**。

## 切换流程

```
手柄按钮 (X/O) → joy_utils 检测边沿触发
       ↓
switch_controller(BEST_EFFORT) → 激活新 controller，停掉旧的
       ↓
旧 controller on_deactivate → 关节指令归零，设轻阻尼 (kd=0.1~0.3)
       ↓
新 controller on_activate → 三阶段过渡开始
```

## 三个阶段

### 1. Init（1~2 秒）

激活瞬间，`on_activate()` 捕获当前实际关节位置作为起点，线性插值到默认站立姿态：

```
t=0:  target = 当前实际关节位置（无论在哪）
t=T:  target = default_joint_pos（标准站姿）
中间: target = lerp(current, default, t / init_duration)
```

全程只做 PD 轨迹跟踪，不跑 policy。PD 公式：

```
τ = kp * (target - actual) + kd * (target_vel - actual_vel)
```

PD 控制器负责让物理关节跟着这条插值轨迹走。不是录制的轨迹，是数学算出来的直线。

### 2. Fade-in（1~2 秒）

开始跑 policy 推理，但输出乘以渐变系数：

```
joint_cmd = fade_in * policy_output * action_scale + default_joint_pos
```

- `fade_in` 从 0 线性增长到 1
- 观测历史中的前序动作也乘以 fade_in，保证 policy 看到的自身动作是连续的
- 没有阶跃跳变，policy 控制力被逐渐混入

### 3. 正常运行

`fade_in = 1.0`，全量 policy 控制，50Hz 推理频率。

## 关键配置参数

```yaml
neural_controller:
  ros__parameters:
    repeat_action: 10          # 每个 action 保持 10 个控制周期 (~50ms)，平滑噪声
    init_duration: 1.0         # init 阶段时长（秒）
    fade_in_duration: 1.0      # fade-in 阶段时长（秒）
    init_kps: [7.5, ...]       # init 阶段 PD 位置增益
    init_kds: [0.25, ...]      # init 阶段 PD 速度增益
    estop_kd: 0.1              # 退出时的轻阻尼

neural_controller_three_legged:
  ros__parameters:
    init_duration: 2.0         # 三足模式需要更长时间稳定
    fade_in_duration: 2.0
```

## 手柄按钮映射

```yaml
joy_util_node:
  ros__parameters:
    estop_index: 12              # 急停按钮
    estop_release_index: 9       # 解除急停
    switch_button_indices: [0, 1] # 切换控制器按钮
    controller_names:            # 按钮对应的控制器列表
      - "neural_controller"           # 按钮 0 (X)
      - "neural_controller_three_legged"  # 按钮 1 (O)
```

按钮为边沿触发（按一下切换一次，长按不重复）。

## 防倒机制总结

| 机制 | 作用 |
|------|------|
| `init_joint_pos_` = 当前实际位置 | 起点 = 物理真实位置，无跳变 |
| 线性插值到站姿 | 到达已知稳定状态 |
| `fade_in_multiplier` 0→1 | 渐入 policy，无阶跃 |
| `repeat_action: 10` | 每个 action 保持 ~50ms，平滑高频抖动 |
| 旧 controller 设轻阻尼 | 切换间隙不完全失控 |
| ros2_control `BEST_EFFORT` 模式 | 切换失败不阻塞，系统保持运行 |

## 动画回放（独立功能）

项目另有录制回放功能，与控制器切换无关：
- `forward_command_controller`：接收外部关节轨迹指令直接驱动
- `animation_controller_py`：Python 节点，从文件读取关键帧动画，通过话题发送到 forward_command_controller
- 配置帧率 40fps，init_duration 1 秒
