# Hailo Package 功能记录

## 包描述
Hailo 神经网络包 - 基于 Hailo 硬件加速的 AI 推理包

## 主要功能模块

### 1. hailo_detection.py
- **功能**: 物体检测
- **用途**: 使用 Hailo 硬件加速进行实时物体检测
- **输入**: 相机图像 (sensor_msgs/Image)
- **输出**: 检测结果 (vision_msgs/Detection2DArray)

### 2. hailo_depth.py  
- **功能**: 深度估计处理
- **用途**: 处理深度相关的视觉信息
- **硬件支持**: Hailo 深度相机

### 3. hailo_inference.py
- **功能**: AI 模型推理引擎
- **用途**: 
  - 加载和运行 Hailo 优化的神经网络模型
  - 硬件加速推理
  - 预处理和后处理

### 4. fisheye_utils.py
- **功能**: 鱼眼相机工具函数
- **用途**: 
  - 鱼眼图像去畸变
  - 坐标变换
  - 视觉校正

### 5. mock_camera.py
- **功能**: 模拟相机节点
- **用途**: 
  - 在没有真实硬件时提供模拟图像
  - 用于开发和测试

### 6. camera_params.yaml
- **功能**: 相机参数配置
- **用途**: 存储相机内参、畸变参数等

## 技术特点

### 硬件加速
- 使用 Hailo AI 处理器进行高效推理
- 支持实时性能的物体检测
- 低延迟的深度估计

### ROS2 集成
- 标准的 ROS2 节点接口
- 支持 sensor_msgs, vision_msgs 等标准消息类型
- 与 ROS2 生态系统完全兼容

### 依赖项
- OpenCV (python3-opencv)
- NumPy
- Supervision
- Loguru (日志记录)
- Pillow (图像处理)

## 未来替换方案

由于用户不需要 Hailo 硬件，可以计划用以下方案替换：

1. **RDK X5 自带库**: 使用 RDK X5 开发板的官方 AI 推理库
2. **OpenCV DNN**: 使用 OpenCV 的深度神经网络模块
3. **TensorRT**: 如果需要更高性能，可以使用 NVIDIA TensorRT
4. **ONNX Runtime**: 跨平台的推理引擎

## 移除原因
- 当前环境不支持 Hailo 硬件
- setup.py 存在兼容性问题 (不支持 --editable 选项)
- 需要使用适合当前硬件的替代方案
