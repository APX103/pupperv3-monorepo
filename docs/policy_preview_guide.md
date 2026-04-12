# 预览已训练策略的完整指南

本文档提供多种方式来预览和可视化项目中已有的训练策略。

---

## 一、方法1: 仿真中运行策略（推荐）

### 步骤1: 选择要预览的策略

当前可用策略（`ros2_ws/src/neural_controller/launch/`）:

| 策略文件 | 说明 | 文件大小 |
|----------|------|---------|
| `policy.json` | 小网络快速策略 | 1.2MB |
| `policy_latest.json` | **当前默认策略** (Run 243) | 38.9MB |
| `policy_ancient-surf-216.json` | 大网络策略（腿伸出问题） | 38.9MB |
| `policy_rich-donkey-233.json` | **三足策略** (Run 233) | 38.9MB |
| `policy_pretty-spaceship-243.json` | 四足重训练策略 | 38.9MB |

### 步骤2: 配置策略路径

编辑 `ros2_ws/src/neural_controller/launch/config.yaml`:

```yaml
# 找到这一行（第86行）：
model_path: "$(find-pkg-share neural_controller)/launch/policy_latest.json"

# 改为你想预览的策略，例如：
model_path: "$(find-pkg-share neural_controller)/launch/policy_rich-donkey-233.json"
```

或者直接覆盖：
```bash
# 备份原策略
cp ros2_ws/src/neural_controller/launch/policy_latest.json \
   ros2_ws/src/neural_controller/launch/policy_latest.json.bak

# 复制你想预览的策略
cp ros2_ws/src/neural_controller/launch/policy_rich-donkey-233.json \
   ros2_ws/src/neural_controller/launch/policy_latest.json
```

这样不需要修改config.yaml。

### 步骤3: 构建并启动仿真

```bash
cd D:/work/pupperv3-monorepo/ros2_ws

# 构建工作空间
./build.sh

# 激活环境
source install/local_setup.bash

# 启动仿真（带手柄控制）
ros2 launch neural_controller launch.py sim:=True

# 预期行为：
# 1. MuJoCo窗口打开，显示3D机器人
# 2. 机器人初始化到站立姿态（约1-2秒）
# 3. 可以用PS5手柄控制机器人
```

### 步骤4: 用手柄测试

使用PS5手柄测试策略行为：

| 手柄操作 | 机器人行为 |
|----------|------------|
| 左摇杆前推 | 前进 |
| 左摇杆后拉 | 后退 |
| 左摇杆右推 | 右移 |
| 左摇杆左推 | 左移 |
| 右摇杆右推 | 顺时针转 |
| 右摇杆左推 | 逆时针转 |
| R3按住 | 急停 |
| PS按钮 | 解除急停 |
| X按钮 | 四足模式 |
| O按钮 | 三足模式（如果策略支持） |

### 仿真启动参数选项

从 `launch.py` 分析得出的参数：

```bash
# 默认启动（真实硬件模式）
ros2 launch neural_controller launch.py

# 仿真模式
ros2 launch neural_controller launch.py sim:=True

# 禁用手柄（仅自动命令）
ros2 launch neural_controller launch.py teleop:=False

# 组合使用
ros2 launch neural_controller launch.py sim:=True teleop:=True
```

---

## 二、方法2: 生成策略行为视频

### 前置条件

```bash
cd D:/work/pupperv3-monorepo/ai/rl

# 安装依赖
uv sync
```

### 运行预览脚本

```bash
# 使用Colab生成的脚本
uv run python pupper_mjx_rl_use_this.py
```

这个脚本会：

1. **加载策略模型** - 从配置中读取参数
2. **创建仿真环境** - 使用指定的MuJoCo模型
3. **运行轨迹** - 生成200步的运动
4. **生成视频** - 使用mediapy保存为GIF
5. **生成图表** - 使用Plotly显示：
   - 策略输出（关节目标位置）
   - 关节力矩
   - 关节位置
   - 世界速度

### 自定义命令参数

你可以修改脚本中的命令来测试不同场景：

```python
# 在脚本末尾找到这些参数：
x_vel = 0.3      # 前进速度 m/s
y_vel = -0.0     # 侧移速度 m/s
ang_vel = 0.0     # 转向速度 rad/s
pitch_degs = 0    # 俯仰角度 度

# 测试场景示例：

# 场景1: 快速前进
x_vel = 0.6

# 场景2: 原地转向
x_vel = 0.0
ang_vel = 1.5

# 场景3: 侧向移动
y_vel = 0.4

# 场景4: 向前倾
x_vel = 0.3
pitch_degs = 10
```

### 输出文件

运行后会在当前目录生成：

```
output_{run_name}/
├── policy_*.json          # 策略文件
├── mjx_params_*          # checkpoint
└── video/               # 生成的GIF视频
    └── policy_*.gif     # 可在浏览器中打开查看
```

---

## 三、方法3: 下载最新策略预览

### 从WandB下载

```bash
cd ros2_ws/src/neural_controller

# 安装wandb（如果未安装）
pip install wandb

# 下载最新策略
python3 download_latest_policy.py

# 脚本会：
# 1. 询问WandB API key
# 2. 从 hands-on-robotics/pupperv3-mjx-rl 下载
# 3. 保存到 launch/policy_latest.json
```

### 下载特定Run的策略

```bash
# 查看特定run的策略
python3 download_latest_policy.py --run_number=233

# 常用run号：
# 216 - 大网络通用策略
# 233 - 三足策略
# 243 - 最新四足策略
```

---

## 四、方法4: Foxglove Studio实时可视化

### 启动Foxglove Bridge

```bash
cd ros2_ws
source install/local_setup.bash

# 方法1: 通过launch启动（已集成）
ros2 launch neural_controller launch.py sim:=True

# 方法2: 单独启动
ros2 run foxglove_bridge foxglove_bridge
```

### 连接Foxglove Studio

1. 下载 [Foxglove Studio](https://foxglove.dev/)
2. 打开应用
3. 点击 "Open connection"
4. 连接到: `ws://localhost:8765`
5. (可选) 导入layout文件设置面板

### 可视化内容

Foxglove可以实时显示：

| 面板 | 内容 |
|------|------|
| 3D URDF | 机器人3D模型和关节位置 |
| Twist | 当前速度命令 |
| Joint States | 12个关节的实时位置 |
| IMU | 加速度计和陀螺仪数据 |
| Trajectory | 运动轨迹历史 |

### 端口说明

默认配置下，Foxglove Bridge运行在端口8765。

如需修改端口，编辑 `launch.py`。

---

## 五、方法5: 独立MuJoCo仿真器

### 构建独立仿真器

```bash
cd ros2_ws/build/pupperv3_mujoco_sim

# 直接运行独立仿真
./simulate
```

### 独立仿真器功能

| 功能 | 说明 |
|------|------|
| 交互式3D视图 | 鼠标拖动旋转视角 |
| 关节手动控制 | 通过GUI直接控制关节 |
| 物理调试 | 显示碰撞、力等信息 |
| 模型加载 | 支持加载自定义MJCF模型 |
| 录制功能 | 保存仿真过程为视频 |

---

## 六、各策略的特点预览

### policy_latest.json (Run 243)

**特点:**
- 四足通用策略
- 稳定性好
- 适合平地行走
- 支持前进、后退、转向、侧移

**预期行为:**
- 平稳的步态
- 良好的姿态保持
- 响应敏捷但不过冲

### policy_rich-donkey-233.json (Run 233)

**特点:**
- **三足模式**（后左腿抬起）
- 跛行但可转向
- 后左膝关节几乎禁用

**预期行为:**
- 三足支撑行走
- 转向更灵活
- 适合展示特殊步态

**切换方式:**
- 手柄按O切换到此策略
- config.yaml中 `neural_controller_three_legged` 引用此策略

### policy_ancient-surf-216.json (Run 216)

**特点:**
- 大网络（12M参数）
- 可能有"腿伸出"问题
- 较高的最终奖励（20.27）

**预期行为:**
- 可能不如新策略稳定
- 偶尔出现异常姿态
- 更多样化的行为

---

## 七、快速对比不同策略

### 修改策略快速测试

```bash
# 创建测试脚本
cat > test_policies.sh << 'EOF'
#!/bin/bash
POLICIES=(
    "policy_latest.json"
    "policy_rich-donkey-233.json"
    "policy_ancient-surf-216.json"
)

for policy in "${POLICIES[@]}"; do
    echo "Testing: $policy"
    cp ros2_ws/src/neural_controller/launch/$policy \
       ros2_ws/src/neural_controller/launch/policy_latest.json

    # 在仿真中观察10秒
    timeout 10 ros2 launch neural_controller launch.py sim:=True
done
EOF

chmod +x test_policies.sh
./test_policies.sh
```

### 记录对比观察

| 策略 | 稳定性 | 速度 | 步态 | 其他观察 |
|-------|---------|------|------|----------|
| policy_latest.json | | | | |
| policy_233.json | | | | |
| policy_216.json | | | | |

---

## 八、故障排除

| 问题 | 解决方案 |
|------|---------|
| 仿真窗口不打开 | 检查是否安装了 libglfw3-dev: `sudo apt install libglfw3-dev` |
| 策略加载失败 | 确认policy.json路径正确，文件完整 |
| 机器人不动 | 检查是否连接了手柄，或尝试直接发送cmd_vel |
| 策略行为异常 | 可能是action_scale不匹配，检查训练和部署配置是否一致 |
| Foxglove连接失败 | 确认端口8765未被占用，防火墙允许 |

---

## 九、快速开始命令

### 最简单的预览方式

```bash
# 1. 启动仿真（使用当前策略）
cd ros2_ws && source build.sh
ros2 launch neural_controller launch.py sim:=True

# 2. 用手柄测试
# - 左摇杆：移动
# - 右摇杆：转向
# - 观察行为
```

### 预览特定策略

```bash
# 1. 覆盖策略
cp ros2_ws/src/neural_controller/launch/policy_rich-donkey-233.json \
   ros2_ws/src/neural_controller/launch/policy_latest.json

# 2. 重新构建
cd ros2_ws && ./build.sh

# 3. 启动仿真
source install/local_setup.bash
ros2 launch neural_controller launch.py sim:=True
```

### 生成行为视频

```bash
cd ai/rl
uv run python pupper_mjx_rl_use_this.py
# 视频会保存在 outputs/ 目录
```

---

*最后更新: 2026-04-11*
