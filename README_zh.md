# Pupper V3 代码库

# 部署到真实机器人
按照此处的说明 https://pupper-v3-documentation.readthedocs.io/en/latest/guide/software_installation.html 将我们的自定义镜像刷入 Raspberry Pi 5。

# 部署到开发机上的仿真机器人 (x86 Ubuntu 24)
## 安装
```sh
sudo apt install git-lfs
git lfs install
git clone https://github.com/Nate711/pupperv3-monorepo.git --recurse-submodules
./install_dev_dependencies.sh
```

## 构建
```sh
cd ros2_ws
source build.sh
```

# 文档

请参阅 [文档](https://pupper-v3-documentation.readthedocs.io/en/latest/)！

# 注意事项
* 摄像头默认帧率为 10Hz。可在 `ros2_ws/src/neural_controller/launch/config.yaml` 中通过 `FrameDurationLimits: [100000, 100000]` 参数进行调整

# 开发

## 添加动画

1. 长按 L1 直到 BAG 状态图标变为绿色，表示正在录制 mcap bag
1. 操控 Pupper 完成期望的动作
1. 按 R1 停止录制
1. 在 Foxglove 中查看录制的 mcap 文件以验证动画效果
1. 将 bag 文件移动到 pupperv3-monorepo/bags 目录
1. 在机器人上使用 `scripts/mcap_to_csv.py [mcap文件路径] -s 绝对起始时间 -e 绝对结束时间` 转换为 csv
1. 将 csv 文件复制到 ros2_ws/src/animation_controller_py/launch/animations 目录
1. 使用 `./build.sh` 重新构建 ros2 工作空间
1. 在 pupster.py 中更新动画昵称
1. 如果需要编辑动画帧率或淡入淡出时间，请确保同时修改 config.yaml 和 pupster.yaml

## 摄像头
启动模拟摄像头和检测节点，以便在仿真机器人上进行视觉实验
```sh
ros2 launch hailo detection_with_mock_camera_launch.py
```

启动 Foxglove 桥接，以便在 Foxglove Studio 中查看检测结果
```sh
ros2 run foxglove_bridge foxglove_bridge
```
