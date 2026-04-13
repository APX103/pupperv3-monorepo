# Pupper V3 AI 加速器需求分析

> 本文档分析 Pupper V3 四足机器人项目中各 AI 算法的计算需求，解释为什么需要 Hailo-8L AI 加速器。

---

## 1. 核心结论

**Hailo-8L AI 加速器不是给运动控制策略用的，而是给视觉感知管线用的。** 项目中有两套完全不同的 AI 推理任务，计算需求差异巨大：

| 任务 | 模型 | 参数量 | 运行位置 | 原因 |
|------|------|--------|----------|------|
| 运动控制策略 | MLP [256,128,128,128] | ~17 万 | **CPU**（RTNeural） | 模型太小，CPU 跑得又快又稳 |
| 人物检测 | YOLOv8m | ~2500 万 | **Hailo-8L NPU** | 模型太大，CPU 根本跑不动 |
| 深度估计 | SC-Depth v3 | 编解码器架构 | **Hailo-8L NPU** | 模型更大，CPU 完全不可用 |

---

## 2. 系统中的 AI 推理任务全景

```
┌─────────────────────────────────────────────────────────────┐
│                   Pupper V3 AI 推理全景                      │
├──────────────────┬──────────────────────────────────────────┤
│                  │                                          │
│  不需要加速器     │  RL 运动策略 (MLP, 17 万参数, 52Hz)       │
│  CPU 即可        │  → RTNeural C++ 实时推理, <1ms            │
│                  │  → 实时性优先，不用加速器反而更好           │
│                  │                                          │
├──────────────────┼──────────────────────────────────────────┤
│                  │                                          │
│  必须要加速器     │  YOLOv8m 人物检测 (2500 万参数, 10+fps)    │
│  CPU 跑不动      │  → 78.9 GFLOPs/帧, CPU 只有 2-5fps       │
│                  │  → Hailo-8L: 13 TOPS, 轻松 10+fps        │
│                  │                                          │
│                  │  SC-Depth v3 深度估计 (更重的模型)         │
│                  │  → CPU 完全不可用 (<1fps)                  │
│                  │  → Hailo-8L 实现实时推理                   │
│                  │                                          │
├──────────────────┼──────────────────────────────────────────┤
│                  │                                          │
│  不在设备上       │  OpenAI Realtime API (语音, 云端)          │
│  在云端跑        │  Gemini 2.5 Flash (视觉问答, 云端)         │
│                  │  Deepgram (语音转文字, 云端)               │
│                  │                                          │
└──────────────────┴──────────────────────────────────────────┘
```

---

## 3. 运动控制策略 — 不需要加速器

### 3.1 模型架构

```
观测向量 (168 floats) → MLP [256,128,128,128] → 12 个关节位置目标
                        ~17 万参数, ~1.3MB
```

策略网络是一个用强化学习（PPO）在 MuJoCo 仿真中训练出来的**全连接 MLP**，配置如下：

```yaml
# ai/rl/conf/policy/default.yaml
use_imu: true
observation_history: 4
action_scale: 0.75
hidden_layer_sizes: [256, 128, 128, 128]
activation: "elu"
```

### 3.2 运行参数

| 参数 | 值 | 说明 |
|------|----|------|
| 控制循环频率 | 520 Hz | ros2_control 主循环 |
| 策略推理频率 | ~52 Hz | 每 10 个 tick 推理一次（`repeat_action=10`） |
| 推理引擎 | RTNeural | C++ 实时推理库，零动态内存分配 |
| 模型大小 | ~1.3 MB | JSON 格式权重文件 |
| 推理延迟 | <1 ms | 用 `std::chrono::high_resolution_clock` 实测 |

### 3.3 为什么不用加速器

1. **模型太小**：17 万参数的 MLP，CPU 单次前向传播不到 1ms
2. **实时性要求**：运动控制需要**确定性的延迟**（deterministic latency），不能有 jitter
3. **RTNeural 的设计目标**：专门为实时音频/控制场景设计，避免 PyTorch/TensorFlow 的非确定性延迟

neural_controller 的 README 明确说明了选择 RTNeural 的原因：

> "Common neural network libraries such as Torch are not designed to run in a real-time control loop, introducing latency/jitter that increases the difficulty of sim-to-real transfer."

如果用 GPU/NPU 来跑这个小 MLP，数据搬运的开销和调度的不确定性反而会引入 jitter，破坏实时性。

### 3.4 关键代码

推理发生在 `neural_controller.cpp` 的 `update()` 方法中：

```cpp
// 组装观测向量 (168 floats)
// ... IMU 数据、关节位置、速度指令、上一步动作 ...

// 执行策略推理（RTNeural）
model_->forward(observation_.data());

// 获取输出（12 个关节目标位置）
const float *policy_output = model_->getOutputs();

// 缩放 + 去归一化 → 发送到硬件
float unclipped = fade_in_multiplier * action * action_scale + default_joint_pos;
action_.at(i) = std::clamp(unclipped, lower_limit, upper_limit);
```

### 3.5 观测向量结构

| 索引 | 内容 | 维度 | 来源 |
|------|------|------|------|
| 0-2 | 角速度 (ωx, ωy, ωz) | 3 | IMU |
| 3-5 | 投影重力向量 (gx, gy, gz) | 3 | IMU 四元数 → 旋转矩阵逆变换 |
| 6-8 | 速度指令 (vx, vy, ωz) | 3 | /cmd_vel |
| 9-11 | 期望姿态向量 | 3 | /cmd_pose |
| 12-23 | 关节位置偏差 | 12 | hardware_interface - default_joint_pos |
| 24-35 | 上一步动作 | 12 | 策略输出反馈 |

单步观测 = 36 维 × `observation_history=4` = **144 维**（另有 24 维额外状态，总共 168 维输入）

---

## 4. 视觉感知 — 必须要加速器

### 4.1 人物检测管线

```
鱼眼相机 (1400×1050 @ 20fps)
  → 鱼眼去畸变 + 等距柱状投影 (fisheye_utils.py)
  → resize 到 640×640
  → YOLOv8m 推理 (~2500 万参数)
  → 人物检测框 + 置信度
  → person_follower → /person_follow_cmd_vel → cmd_vel_mux → /cmd_vel
  → 同时通过 ZMQ (tcp://127.0.0.1:5556) 发送给 pupper-rs 眼球追踪
```

### 4.2 YOLOv8m 的计算量

| 指标 | 值 |
|------|----|
| 模型参数 | ~25,000,000 (2500 万) |
| 输入分辨率 | 640 × 640 × 3 |
| 计算量 | ~78.9 GFLOPs / 帧 |
| 帧率要求 | ≥ 10 fps（实时跟随） |
| 编译后格式 | `yolov8m.hef`（Hailo Executable Format） |

**对比运动策略**：YOLOv8m 的参数量是运动策略 MLP 的 **~150 倍**，每帧计算量是运动策略单次推理的 **数千倍**。

### 4.3 在树莓派 5 CPU 上跑会怎样

| 指标 | 树莓派 5 CPU | Hailo-8L NPU |
|------|-------------|--------------|
| 算力 | ~19.2 GFLOPS (4×Cortex-A76 @ 2.4GHz) | **13 TOPS** (13,000 GFLOPS) |
| YOLOv8m 推理速度 | 2-5 fps | **10+ fps** |
| 延迟 | 200-500 ms | <100 ms |
| 对控制循环的影响 | 严重抢占 CPU | 无影响（独立 NPU） |

**2-5 fps 意味着什么？** 人物跟随的延迟是 200-500ms。如果人走得快一点，机器人就跟丢了。而且推理过程会严重占用 CPU，影响 520Hz 的运动控制循环。

### 4.4 Hailo-8L 的优势

- **算力**：13 TOPS（每秒 13 万亿次运算），是树莓派 5 CPU 的 **~675 倍**
- **功耗**：~2.5W（树莓派 5 的功耗预算能承受）
- **接口**：通过 HAT 连接树莓派 5
- **独立性**：NPU 独立运行推理，不占用 CPU 资源

### 4.5 关键代码

`hailo_inference.py` — Hailo NPU 推理封装：

```python
from hailo_platform import HEF, VDevice, FormatType, HailoSchedulingAlgorithm

# 加载编译好的 HEF 模型（YOLOv8m 编译为 Hailo 原生格式）
params = VDevice.create_params()
params.scheduling_algorithm = HailoSchedulingAlgorithm.ROUND_ROBIN
params.group_id = "SHARED"
vDevice = VDevice(params)

self.hef = HEF(hef_path)  # yolov8m.hef
self.infer_model = self.target.create_infer_model(hef_path)

# 异步推理，round-robin 调度
self.configured_model.run_async(bindings_list, callback)
```

`hailo_detection.py` — ROS2 检测节点，真实模式 vs 仿真模式：

```python
if self.sim_mode:
    # 仿真模式：用 PyTorch YOLOv8 在 CPU/GPU 上跑
    self.yolo_model = YOLO(self.yolo_model_name)
    results = self.yolo_model(equirect_frame, conf=self.score_threshold)
else:
    # 真实模式：用 Hailo NPU 跑编译好的 HEF 模型
    self.hailo_inference = HailoAsyncInference(hef_path=self.model_path, ...)
    self.input_queue.put([preprocessed_frame])
    _, results = self.output_queue.get()
```

### 4.6 深度估计

`hailo_depth.py` 使用 SC-Depth v3 模型进行单目深度估计：

```python
self.hailo_inference = HailoInfer(
    hef_path="/home/pi/pupperv3-monorepo/ros2_ws/src/hailo/config/scdepthv3.hef",
)
```

SC-Depth v3 是 encoder-decoder 架构，比 YOLOv8m 更重，在 CPU 上完全不可用（<1fps）。Hailo-8L 可以实现实时推理。

---

## 5. 其他 AI 任务（不在设备上运行）

以下 AI 任务在云端运行，不占用本地计算资源：

| 任务 | 服务 | 通信方式 |
|------|------|----------|
| 语音对话 | OpenAI Realtime API | WebSocket |
| 视觉问答 | Google Gemini 2.5 Flash | HTTP API |
| 语音转文字 | Deepgram Nova-3 | Cloud API |
| 文字转语音 | Cartesia | Cloud API |

此外，`moonshine-test/` 目录中有本地 ONNX 语音识别的实验代码（Moonshine + Silero VAD），但尚未集成到主系统中。

---

## 6. 整体系统架构中的 AI 位置

```
┌─────────────────────────────────────────────────────────────────┐
│                      Pupper V3 系统架构                          │
├─────────────┬───────────────────────────────────────────────────┤
│             │                                                   │
│   用户交互层 │  PS5 手柄 ──→ joy_linux ──→ teleop_twist_joy     │
│             │  语音助手 ──→ live-audio ──→ WebSocket Server     │
│             │                                                   │
├─────────────┼───────────────────────────────────────────────────┤
│             │                                                   │
│   指令调度层 │  cmd_vel_mux ──→ /cmd_vel (优先级多路复用)        │
│             │                                                   │
├─────────────┼───────────────────────────────────────────────────┤
│             │                                                   │
│   控制层     │  neural_controller (RTNeural, CPU, 52Hz)          │
│             │  animation_controller (关键帧动画)                 │
│             │                                                   │
├─────────────┼───────────────────────────────────────────────────┤
│             │                                                   │
│   硬件抽象层 │  ros2_control 框架                                │
│             │  ├─ control_board_hardware_interface (真实硬件)    │
│             │  └─ pupperv3_mujoco_sim (仿真)                    │
│             │                                                   │
├─────────────┼───────────────────────────────────────────────────┤
│             │                                                   │
│   硬件层     │  CAN 总线 (12 个舵机) + IMU + 相机 + Hailo-8L    │
│             │                                                   │
├─────────────┼───────────────────────────────────────────────────┤
│             │                                                   │
│   感知层     │  Hailo 检测 (NPU) ──→ person_follower → /cmd_vel │
│             │  ZMQ ──→ pupper-rs (眼球追踪)                     │
│             │                                                   │
├─────────────┼───────────────────────────────────────────────────┤
│             │                                                   │
│   表情界面层 │  pupper-rs (Rust egui 全屏应用)                   │
│             │                                                   │
└─────────────┴───────────────────────────────────────────────────┘
```

---

## 7. 控制频率与延迟汇总

| 组件 | 频率 | 延迟预算 | 备注 |
|------|------|----------|------|
| Controller Manager | 520 Hz | 1.92 ms | 硬件读取 + 控制更新 + 写入 |
| SPI 通信 | 520 Hz | 含在上述 | 6 MHz, 132 bytes/board × 2 boards |
| IMU (BNO055) | 100 Hz | 10 ms | I2C, 独立线程以 ~1kHz 轮询 |
| 策略推理 (RTNeural) | ~52 Hz | ~19.2 ms 有效 | 每 10 个 tick 推理一次 |
| YOLOv8m (Hailo NPU) | 10-20 fps | ~50-100 ms | 异步推理，不阻塞控制循环 |
| 相机 | 20 Hz | 50 ms | 独立管线，不在控制循环内 |
| 动画播放 | 40 Hz | 25 ms | 独立管线，绕过 NN 控制器 |

---

## 8. 文件索引

### 运动控制策略

| 文件 | 说明 |
|------|------|
| `ros2_ws/src/neural_controller/src/neural_controller.cpp` | 核心控制器：观测组装 → RTNeural 推理 → 动作执行 |
| `ros2_ws/src/neural_controller/include/neural_controller/neural_controller.hpp` | 观测/动作维度定义 |
| `ros2_ws/src/neural_controller/launch/config.yaml` | 控制参数（520Hz, repeat_action=10, 关节限位等） |
| `ros2_ws/src/neural_controller/launch/policy_latest.json` | 当前部署的策略权重（Git LFS） |
| `ros2_ws/src/neural_controller/modules/RTNeural/` | RTNeural 推理库（vendored submodule） |
| `ai/rl/pupper_mjx_rl_training.py` | RL 训练脚本（Hydra 配置版） |
| `ai/rl/pupper_mjx_rl_use_this.py` | RL 训练脚本（原始版） |
| `ai/rl/conf/policy/default.yaml` | 策略网络结构配置 |

### 视觉感知（Hailo NPU）

| 文件 | 说明 |
|------|------|
| `ros2_ws/src/hailo/hailo/hailo_detection.py` | Hailo 人物检测 ROS2 节点 |
| `ros2_ws/src/hailo/hailo/hailo_inference.py` | Hailo HEF 模型推理封装 |
| `ros2_ws/src/hailo/hailo/hailo_depth.py` | SC-Depth v3 深度估计（Hailo NPU） |
| `ros2_ws/src/hailo/hailo/fisheye_utils.py` | 鱼眼镜头畸变校正 |
| `ros2_ws/src/hailo/config/yolov8m.hef` | YOLOv8m 编译后的 Hailo 原生模型 |
| `ros2_ws/src/hailo/config/coco.txt` | COCO 类别标签 |

### 基础设施

| 文件 | 说明 |
|------|------|
| `infra/pupper_image_builder/provision_pios_full.sh` | 镜像构建：`apt-get install -y hailo-all` |
| `infra/pupper_image_builder/pios_ai_arm64.pkr.hcl` | AI 扩展镜像构建配置 |
