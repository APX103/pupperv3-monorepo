# 动作录制与回放

## 概述

录制自定义动作（如招财猫、握手、作揖等），保存为关键帧序列，映射到按键/按钮一键回放。

## 动画系统原理

动画本质是一组**关键帧**（keyframe），每帧包含 12 个关节的目标位置 + 过渡时间：

```json
{
  "name": "wave",
  "keyframes": [
    { "time": 0.0, "positions": [0.26, 0.0, -0.52, -0.26, 0.0, 0.52, 0.26, 0.0, -0.52, -0.26, 0.0, 0.52] },
    { "time": 0.5, "positions": [0.26, 0.0, -0.52, -0.26, 1.5, 0.52, 0.26, 0.0, -0.52, -0.26, 0.0, 0.52] },
    { "time": 1.0, "positions": [0.26, 0.0, -0.52, -0.26, 0.8, 0.52, 0.26, 0.0, -0.52, -0.26, 0.0, 0.52] },
    { "time": 1.5, "positions": [0.26, 0.0, -0.52, -0.26, 1.5, 0.52, 0.26, 0.0, -0.52, -0.26, 0.0, 0.52] },
    { "time": 2.0, "positions": [0.26, 0.0, -0.52, -0.26, 0.0, 0.52, 0.26, 0.0, -0.52, -0.26, 0.0, 0.52] }
  ],
  "loop": false
}
```

回放时，对关键帧之间做**线性插值**（或三次样条），用 PD 控制跟踪目标轨迹。

## 项目现有动画系统

### ROS2 端

- `animation_controller_py`：Python 节点，从文件读取关键帧动画
  - 帧率 40fps，init_duration 1 秒
  - 通过话题发送到 `forward_command_controller`
  - 与 neural controller 互斥（同时只激活一个）

- `forward_command_controller`：ROS2 通用前馈控制器，接收关节位置/增益指令直接驱动

- MuJoCo XML 中的 `<keyframe>`：`home_keyframe.xml` 定义了默认站立姿态

### 切换逻辑

```
neural_controller (行走)
    ↕ switch_controller()
animation_controller_py (动画回放)
```

动画模式下 policy 不运行，直接驱动关节。

## 纯 MuJoCo 仿真中的实现方案

### 录制模式

进入录制模式后，policy 停止推理，用户通过以下方式摆姿态：

**鼠标拖拽（MuJoCo viewer 内置）：**
- MuJoCo viewer 原生支持鼠标拖拽关节（Ctrl+左键拖拽 body，Shift+左键拖拽相机）
- 拖到目标位置后按一个键拍一帧（如 Enter）
- 自动记录当前 12 个关节位置 + 时间戳

**键盘微调：**
- Tab 切换当前选中关节
- ↑↓ 调整角度（步长 0.05 rad）
- Enter 拍一帧

### 按键映射设计

| 按键 | 模式 | 功能 |
|------|------|------|
| 1~9 | 行走模式 | 回放对应编号的动画 |
| Tab | 录制模式 | 切换选中关节 |
| ↑/↓ | 录制模式 | 调整当前关节角度 |
| Enter | 录制模式 | 拍一帧关键帧 |
| Backspace | 录制模式 | 删除最后一帧 |
| F1 | 任意模式 | 进入/退出录制模式 |
| F5 | 录制模式 | 保存动画到文件 |
| Esc | 任意模式 | 退出仿真 |

### 文件格式

存为 `sim/animations/wave.json`：

```json
{
  "name": "wave",
  "description": "招财猫",
  "keyframes": [...],
  "loop": false,
  "fps": 20
}
```

### 回放实现

```python
def playback_animation(keyframes, current_time, joint_ids, data, model):
    """线性插值回放关键帧动画"""
    # 找到当前时间所在的两个关键帧
    for i in range(len(keyframes) - 1):
        t0, pos0 = keyframes[i]["time"], keyframes[i]["positions"]
        t1, pos1 = keyframes[i+1]["time"], keyframes[i+1]["positions"]
        if t0 <= current_time <= t1:
            alpha = (current_time - t0) / (t1 - t0)
            target = [a + (b - a) * alpha for a, b in zip(pos0, pos1)]
            for j, jid in enumerate(joint_ids):
                data.ctrl[j] = target[j]
            return
    # 超出最后一帧：回到站姿或循环
```

## 示例动作：招财猫

1. 初始站姿（12 关节默认位置）
2. 0.5s：左前腿抬起，hip=1.5 rad
3. 1.0s：左前腿放下，hip=0.8 rad
4. 1.5s：左前腿再抬起，hip=1.5 rad
5. 2.0s：左前腿回到站姿

关节顺序参考：
```
[0]  leg_front_r_1   前右髋外展
[1]  leg_front_r_2   前右髋
[2]  leg_front_r_3   前右膝
[3]  leg_front_l_1   前左髋外展
[4]  leg_front_l_2   前左髋      ← 抬这条腿
[5]  leg_front_l_3   前左膝
[6]  leg_back_r_1    后右髋外展
[7]  leg_back_r_2    后右髋
[8]  leg_back_r_3    后右膝
[9]  leg_back_l_1    后左髋外展
[10] leg_back_l_2    后左髋
[11] leg_back_l_3    后左膝
```

## 回放时如何不倒

与 controller 切换同理：
- 回放前先 init 到站姿（如果当前不在站姿）
- 第一帧用当前实际位置作为起点，线性过渡到动画第一帧
- 回放结束后线性回到站姿，再交还给 policy（或保持在站姿）

## 扩展：三次样条插值

线性插值在关键帧处有速度跳变，关节运动会"卡顿"。用三次样条（cubic spline）可以让过渡更平滑：

```python
from scipy.interpolate import CubicSpline

times = [kf["time"] for kf in keyframes]
positions = [kf["positions"] for kf in keyframes]  # shape: (N, 12)
cs = CubicSpline(times, positions)
target = cs(current_time)  # 自动平滑插值
```

需要在 `pyproject.toml` 中添加 `scipy` 依赖。
