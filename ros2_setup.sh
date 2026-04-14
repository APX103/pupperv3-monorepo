#!/bin/bash

# ROS2 环境设置脚本 - Pupper V3 项目

# 设置 ROS2 Humble 环境
if [ -f /opt/ros/humble/setup.bash ]; then
    source /opt/ros/humble/setup.bash
    echo "ROS2 Humble 环境已加载"
else
    echo "错误: ROS2 Humble 未安装"
    return 1
fi

# 设置 ROS2 工作空间
if [ -d "$HOME/pupperv3-monorepo/ros2_ws" ]; then
    source "$HOME/pupperv3-monorepo/ros2_ws/install/local_setup.bash"
    echo "ROS2 工作空间已加载"
else
    echo "错误: ROS2 工作空间不存在"
    return 1
fi

# 设置环境变量
export RCUTILS_COLORIZED_OUTPUT=1

echo "Pupper V3 ROS2 环境设置完成"
echo ""
echo "可用的启动命令:"
echo "  source $HOME/pupperv3-monorepo/ros2_setup.sh"
echo "  ros2 launch neural_controller launch.py       # 启动神经网络控制器"
echo "  ros2 run foxglove_bridge foxglove_bridge # 启动 Foxglove 可视化"
