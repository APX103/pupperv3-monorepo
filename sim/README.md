# Pupper V3 Standalone MuJoCo Simulation

独立于 ROS2 的 MuJoCo 仿真环境，支持加载 RL 策略、播放预录制的动作动画、以及语音控制。

## 前置条件

- Python >= 3.11
- [uv](https://docs.astral.sh/uv/)

## 安装

```bash
cd sim
uv sync
```

### Agent 依赖（可选）

```bash
uv sync --extra agent
```

下载本地 STT/TTS 模型（~600MB）：

```bash
bash download_models.sh
```

### 模型下载地址

如需手动下载：

| 模型 | 用途 | 大小 | 下载 |
|------|------|------|------|
| [sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20](https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20.tar.bz2) | 语音识别 (STT), 中英双语 | ~487MB | GitHub Releases |
| [en_US-lessac-medium.onnx](https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx) + [.onnx.json](https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json) | 语音合成 (TTS), 英文 | ~60MB | HuggingFace |
| [zh_CN-huayan-medium.onnx](https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx) + [.onnx.json](https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx.json) | 语音合成 (TTS), 中文 | ~60MB | HuggingFace |

## 使用

### 仿真（键盘控制）

```bash
# 加载 RL 策略
git lfs pull --include="ros2_ws/src/neural_controller/launch/policy_latest.json"
uv run python pupperv3_sim.py ../ros2_ws/src/neural_controller/launch/policy_latest.json
```

播放预录制动画：

```bash
uv run python pupperv3_sim.py --animation <动画名>
```

可用的动画：`stand_sit_stand`、`stand_sit_shake_sit_stand`、`lie_sit_lie`、`push_up`、`spider`、`swim`、`twerk`、`sneeze`、`stand_downward_dog`、`lie_downward_dog`、`upward_dog`、`superman`、`pee2`。

动画播放完后保持最后一帧，按 `R` 重置后重新播放。

### 语音控制

需要 3 个终端：

```bash
# 终端 1: 自建 LiveKit Server (需先编译)
cd /path/to/livekit && ./livekit-server --config livekit.yaml

# 终端 2: 仿真 (ZMQ 模式, 等待语音命令)
uv run python pupperv3_sim.py --zmq

# 终端 3: Agent (本地 STT/TTS + 云端 GLM)
uv run python pupster_agent.py \
  --stt-provider local --stt-model models/sherpa-onnx-streaming-zipformer-bilingual-zh-en-2023-02-20 \
  --tts-provider local --tts-voice models/piper-voices/en_US-lessac-medium.onnx \
  --llm-provider glm --llm-model glm-5-turbo
```

环境变量配置见 `.env.example`。

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
pupster_agent.py  Agent 入口：LiveKit 连接 + STT/LLM/TTS 组装
agent/agent.py    LiveKit Agent 定义 + function_tools (move/animation/stop)
agent/config.py   动画名映射、ZMQ 地址、速度限制等常量
agent/voices/stt.py  Sherpa-ONNX 本地语音识别
agent/voices/tts.py  Piper 本地语音合成
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
