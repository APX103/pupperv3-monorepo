# Pupster Agent Architecture: 仿真 vs 真机

## 1. 仿真架构

```
┌─────────────────────────────────────────────────────────────────┐
│                       手机 / 浏览器                               │
│  🎤 麦克风 ─── 音频 ──→ WebRTC ──→ 🔊 扬声器 ←── 音频 ←────   │
└────────────────────────────┬────────────────────────────────────┘
                             │ WebRTC (局域网)
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                LiveKit Server (localhost:7880)                    │
│              自建 Go 二进制, 纯音频中转, 无业务逻辑                 │
└──────────┬──────────────────────────────────┬────────────────────┘
           │ LiveKit Agent Protocol           │ LiveKit Agent Protocol
           ▼                                  ▲
┌────────────────────────────────────┐        │
│         Pupster Agent 进程           │        │
│         pupster_agent.py            │        │
│                                    │        │
│   ┌──────────┐   文字   ┌────────┐ │ 文字   ┌──────────┐        │
│   │  STT     │────────→│  LLM   │ ├───────→│  TTS     │────────┘
│   │Sherpa-ONNX│       │  GLM-5 │ │        │  Piper   │
│   │  本地 CPU  │       │ 云端API │ │        │  本地 CPU │
│   └──────────┘       └───┬────┘ │        └──────────┘
│                          │      │
│                    function_tool│
│                    queue_animation│
│                    queue_move     │
│                    immediate_stop │
│                          │      │
│                    ┌─────┴──────┐│
│                    │ ZMQ PUB   ││
│                    └─────┬──────┘│
└──────────────────────────┼───────┘
                           │
              ipc:///tmp/pupper_sim_cmd
              (JSON: move / animation / stop / reset)
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                  MuJoCo 仿真进程                                   │
│                  pupperv3_sim.py                                  │
│                                                                  │
│   ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐     │
│   │  GLFW    │   │ ZMQ SUB  │   │ MuJoCo   │   │ 12关节数据 │     │
│   │ 渲染窗口  │   │ 接收命令  │   │ 物理引擎  │   │ CSV 动画  │     │
│   │ 键盘控制  │   │          │   │ 50Hz     │   │          │     │
│   └──────────┘   └────┬─────┘   └──────────┘   └──────────┘     │
│                        │                                         │
│                 handle_command()                                  │
│                 "move"      → cmd_vel → 步态策略 → 电机目标       │
│                 "animation" → load CSV → 插值 → 电机目标          │
│                 "stop"      → 清零速度 + 清除动画                  │
│                 "reset"     → 复位到站立姿态                      │
└──────────────────────────────────────────────────────────────────┘
```

### 语音交互时序 (仿真)

```
  用户手机 🎤                          Agent                           Sim (MuJoCo)
     │                                  │                                │
     │──── "做俯卧撑" (音频) ─────────→│                                │
     │                                  │ Sherpa-ONNX (本地)             │
     │                                  │ "做俯卧撑" (文字)              │
     │                                  │ GLM-5 (云端)                   │
     │                                  │ → queue_animation("push_up")  │
     │                                  │ ZMQ: {"type":"animation",      │
     │                                  │        "name":"push_up_..."}   │
     │                                  │────────────────────────────────→│
     │                                  │                          load CSV & play
     │                                  │                                │
     │                                  │ GLM 回复: "好的!"              │
     │                                  │ Piper (本地) → 语音            │
     │←── "好的!" (音频) ──────────────│                                │
     │                                  │                          动画播放中...
  🔊                                   │                                │
```

### 特点

- **3 个独立进程**: LiveKit Server / Agent / Sim，任一崩溃不影响其他
- **所有 AI 本地运行**: STT (Sherpa-ONNX) + TTS (Piper) 在 CPU 上，延迟低
- **仅 LLM 需要网络**: GLM API 调用，~1-3s 延迟
- **ZMQ IPC 通信**: Agent → Sim，零网络开销
- **无需 ROS2**: Sim 独立运行，不依赖任何 ROS2 节点

---

## 2. 真机架构

```
┌─────────────────────────────────────────────────────────────────┐
│                       手机 / 浏览器                               │
│  🎤 麦克风 ─── 音频 ──→ WebRTC ──→ 🔊 扬声器 ←── 音频 ←────   │
└────────────────────────────┬────────────────────────────────────┘
                             │ WebRTC (互联网)
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│              LiveKit Cloud (cloud.livekit.io)                     │
│            云端托管, 负责音频中转 + 云端 STT/TTS                    │
│                                                                  │
│   ┌──────────┐        ┌──────────┐        ┌──────────┐          │
│   │ Deepgram │        │ OpenAI / │        │ Cartesia │          │
│   │   STT    │──文字──→│  GLM LLM │──文字──→│   TTS    │          │
│   │ (云端)   │        │ (云端)   │        │ (云端)   │          │
│   └──────────┘        └──────────┘        └──────────┘          │
└────────────────────────────┬─────────────────────────────────────┘
                             │ LiveKit Agent Protocol
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│            真机上的 Agent 进程 (单进程)                             │
│            ai/llm-ui/agent-starter-python/                       │
│                                                                  │
│   LiveKit SDK ←→ RosToolServer                                   │
│                     │                                            │
│            function_tool 调用 → ROS2 API                          │
└────────────────────────────┬─────────────────────────────────────┘
                             │ rclpy (ROS2 Python)
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
┌──────────────────┐ ┌──────────────┐ ┌──────────────┐
│ /cmd_vel         │ │ /animation_  │ │ /controller_ │
│ Twist 消息       │ │ controller_  │ │ manager/     │
│                  │ │ py/animation_│ │ switch_      │
│ ▼                │ │ select       │ │ controller   │
│ neural_controller│ │ String 消息   │ │ 服务调用       │
│ (步态策略)        │ │              │ │              │
└────────┬─────────┘ └──────┬───────┘ └──────┬───────┘
         │                  │                │
         ▼                  ▼                ▼
┌──────────────────────────────────────────────────────────────────┐
│                    ROS2 控制栈                                     │
│                                                                  │
│   ┌────────────────┐  ┌─────────────────┐  ┌────────────────┐   │
│   │ neural_        │  │ animation_      │  │ cmd_vel_mux    │   │
│   │ controller     │  │ controller_py   │  │ (优先级仲裁)    │   │
│   │ (强化学习步态)  │  │ (CSV 关键帧回放) │  │                │   │
│   └───────┬────────┘  └───────┬─────────┘  └───────┬────────┘   │
│           │                  │                     │             │
│           ▼                  ▼                     ▼             │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              Hardware Interface (硬件抽象层)               │   │
│   │              12 路无刷电机 · 阻抗控制 (PD gains)           │   │
│   └─────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

### 语音交互时序 (真机)

```
  用户手机 🎤           LiveKit Cloud              真机 Agent              ROS2
     │                     │                          │                      │
     │─ "往前走" ─────────→│                          │                      │
     │                     │ Deepgram STT             │                      │
     │                     │ "往前走" (文字)           │                      │
     │                     │ LLM: queue_move(...)     │                      │
     │                     │── LiveKit tools ────────→│                      │
     │                     │                          │ RosToolServer         │
     │                     │                          │ /cmd_vel (Twist)      │
     │                     │                          │─────────────────────→│
     │                     │                          │                 neural_controller
     │                     │                          │                      │→ 电机
     │                     │ LLM 回复: "好的!"         │                      │
     │                     │ Cartesia TTS → 语音       │                      │
     │←── "好的!" ─────────│                          │                 行走中...
  🔊                     │                          │                      │
```

### 特点

- **云端 AI**: STT / LLM / TTS 全部在 LiveKit Cloud 处理
- **需要互联网**: 音频和命令都经过云端，网络延迟高
- **单进程 Agent**: LiveKit SDK + RosToolServer 在同一个 Python 进程中
- **依赖 ROS2**: 需要完整的 ROS2 控制栈 (controller_manager, neural_controller 等)
- **真机硬件**: 12 路无刷电机 + 阻抗控制，有物理碰撞和惯性

---

## 3. 对比

### 部署架构

```
 仿真 (3进程, 局域网)                    真机 (ROS2全栈, 互联网)
 ┌──────────┐                          ┌──────────┐
 │ 手机      │                          │ 手机      │
 └────┬─────┘                          └────┬─────┘
      │ WebRTC (局域网)                      │ WebRTC (互联网)
      ▼                                      ▼
 ┌──────────┐                          ┌──────────────┐
 │LiveKit   │                          │LiveKit Cloud │
 │Server    │                          │+ Deepgram STT│
 │(自建,仅转发)│                          │+ Cartesia TTS│
 └────┬─────┘                          │+ LLM         │
      │                                  └────┬─────────┘
      ▼                                       │
 ┌────────────────┐                          ▼
 │Agent 进程       │                   ┌────────────┐
 │STT: Sherpa-ONNX│                   │Agent 进程    │
 │LLM: GLM-5      │                   │RosToolServer│
 │TTS: Piper      │                   │(ROS2 node)  │
 └────┬───────────┘                   └────┬────────┘
      │ ZMQ IPC                             │ rclpy
      ▼                                     ▼
 ┌──────────┐                         ┌────────────┐
 │MuJoCo Sim│                         │ROS2 控制栈  │
 │(纯仿真)   │                         │neural_ctrl  │
 └──────────┘                         │anim_ctrl    │
                                      │12路电机     │
                                      └────────────┘
```

### 核心差异

| 维度 | 仿真 | 真机 |
|------|------|------|
| **AI 推理位置** | STT/TTS 本地, 仅 LLM 上云 | STT/LLM/TTS 全部云端 |
| **网络依赖** | 仅 LLM API (可离线跑 STT/TTS) | 必须联网 (LiveKit Cloud) |
| **进程模型** | 3 独立进程, ZMQ 解耦 | Agent 单进程, rclpy 直调 ROS2 |
| **通信协议** | ZMQ IPC (JSON) | ROS2 Topics + Services |
| **机器人控制** | MuJoCo 物理仿真 50Hz | ROS2 controller_manager → 12路电机 |
| **步态策略** | Python 直接调用 ONNX 模型 | neural_controller ROS2 节点 |
| **动画系统** | CSV → keyframes → MuJoCo | animation_controller_py ROS2 节点 |
| **命令仲裁** | ZMQ 直接覆盖 cmd_vel | cmd_vel_mux 多源优先级仲裁 |
| **部署复杂度** | pip install 即可 | 需要 ROS2 全栈 + 硬件驱动 |
| **启动方式** | `pupperv3_sim.py` + `pupster_agent.py` | `ros2 launch` + agent 进程 |

### 命令映射

两条链路的命令格式不同，但语义一致:

```
 语音: "做俯卧撑"
     │
     ├─ 仿真: queue_animation("push_up")
     │   → ZMQ: {"type": "animation", "name": "push_up_recording_..."}
     │   → Sim: load CSV → MuJoCo 播放
     │
     └─ 真机: queue_animation("push_up")
         → RosToolServer: publish /animation_controller_py/animation_select
         → animation_controller_py: load CSV → 12路电机执行

 语音: "往前走"
     │
     ├─ 仿真: queue_move(vx=0.5, vy=0, wz=0, duration=2)
     │   → ZMQ: {"type": "move", "vx": 0.5, "vy": 0, "wz": 0, "duration": 2}
     │   → Sim: cmd_vel → 步态策略 → MuJoCo
     │
     └─ 真机: queue_move(vx=0.5, vy=0, wz=0, duration=2)
         → RosToolServer: publish /cmd_vel (Twist)
         → cmd_vel_mux → neural_controller → 12路电机
```

### 可用的动画/动作

两条链路共享同一套 CSV 动画文件:

| 动画名 | 文件 | 描述 |
|--------|------|------|
| push_up | push_up_recording_*.csv | 俯卧撑 |
| sit | stand_sit_recording_*.csv | 趴下 |
| shake | stand_sit_shake_stand_recording_*.csv | 趴下摇晃 |
| superman | superman_recording_*.csv | 超人飞行 |
| hand_stand | hand_stand_recording_*.csv | 倒立 |
| pee | pee_recording_*.csv | 抬腿 |
| twerk | twerk_recording_*.csv | 扭动 |
| downward_dog | downward_dog_recording_*.csv | 下犬式 |
| wave | wave_recording_*.csv | 招手 |
| ... | ... | 共 13 个预录制动画 |

动画文件位于 `ros2_ws/src/animation_controller_py/launch/animations/`。

---

## 4. 仿真相比真机的优势 (开发调试)

```
                    仿真                         真机
              ┌─────────────┐              ┌─────────────┐
 反复测试:    │ 随时跑, 0成本 │              │ 电量/磨损   │
 安全性:      │ 不会摔坏      │              │ 可能损坏硬件  │
 调试:        │ 可视化+日志   │              │ 需要串口调试  │
 依赖:        │ pip install  │              │ ROS2 全栈   │
 网络延迟:    │ 仅 LLM ~1s   │              │ 全链路 ~3-5s│
 启动时间:    │ < 5 秒       │              │ 30-60 秒    │
```

仿真可以快速验证 Agent 的 function_tool 逻辑、LLM prompt 效果、语音交互体验，
确认无误后再部署到真机。
