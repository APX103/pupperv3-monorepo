#!/bin/bash
#
# emergency_shutdown.sh - Pupper V3 紧急停机脚本
#
# 用途: 检测到异常情况时执行安全停机
# 使用: sudo ./emergency_shutdown.sh 或自动调用
#

set -e

# 配置
EMERGENCY_LOG="/tmp/pupper_emergency.log"
EMERGENCY_FILE="/tmp/emergency_shutdown_triggered"
MAX_TEMP=85               # 最大温度 (°C)
MAX_CURRENT=6              # 最大电流 (A)
MIN_VOLTAGE=4.8           # 最小电压 (V)
MAX_VOLTAGE=5.2           # 最大电压 (V)

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${message}" >> "$EMERGENCY_LOG"

    case $level in
        "ERROR")
            echo -e "${RED}${message}${NC}"
            ;;
        "WARN")
            echo -e "${YELLOW}${message}${NC}"
            ;;
        *)
            echo -e "${GREEN}${message}${NC}"
            ;;
    esac
}

get_temperature() {
    local temp_files="/sys/class/thermal/thermal_zone*/temp"
    local max_temp=0

    for temp_file in $temp_files; do
        if [ -f "$temp_file" ]; then
            local temp=$(cat "$temp_file" 2>/dev/null || echo 0)
            temp=$((temp / 1000))
            if [ $temp -gt $max_temp ]; then
                max_temp=$temp
            fi
        fi
    done

    echo $max_temp
}

get_current() {
    local current_files="/sys/class/power_supply/*/current_now"
    local max_current=0

    for current_file in $current_files; do
        if [ -f "$current_file" ]; then
            local current=$(cat "$current_file" 2>/dev/null || echo 0)
            current=$((current / 1000000))
            if [ $current -gt $max_current ]; then
                max_current=$current
            fi
        fi
    done

    echo $max_current
}

get_voltage() {
    local voltage_5v_file="/sys/class/regulator/regulator.*5v/voltage"
    local voltage=0

    for v_file in $voltage_5v_file; do
        if [ -f "$v_file" ]; then
            voltage=$(cat "$v_file" 2>/dev/null || echo 5000000)
            voltage=$((voltage / 1000000))
            break
        fi
    done

    echo $voltage
}

check_emergency_conditions() {
    local emergency_reason=""

    # 检查温度
    local temp=$(get_temperature)
    log "INFO" "Current temperature: ${temp}°C"

    if [ $temp -gt $MAX_TEMP ]; then
        log "ERROR" "Temperature ${temp}°C exceeds ${MAX_TEMP}°C threshold"
        emergency_reason="High temperature: ${temp}°C"
    fi

    # 检查电流
    local current=$(get_current)
    log "INFO" "Current draw: ${current}A"

    if [ $current -gt $MAX_CURRENT ]; then
        log "ERROR" "Current ${current}A exceeds ${MAX_CURRENT}A threshold"
        emergency_reason="High current: ${current}A"
    fi

    # 检查电压
    local voltage=$(get_voltage)
    log "INFO" "Voltage: ${voltage}V"

    if [ $(echo "$voltage < $MIN_VOLTAGE" | bc -l) -eq 1 ] || \
       [ $(echo "$voltage > $MAX_VOLTAGE" | bc -l) -eq 1 ]; then
        log "ERROR" "Voltage ${voltage}V outside range [${MIN_VOLTAGE}V, ${MAX_VOLTAGE}V]"
        emergency_reason="Abnormal voltage: ${voltage}V"
    fi

    # 如果有紧急情况，记录到文件
    if [ -n "$emergency_reason" ]; then
        echo "$emergency_reason" > "$EMERGENCY_FILE"
        return 1
    fi

    return 0
}

safe_shutdown_gpio() {
    log "WARN" "Performing GPIO safe shutdown..."

    # 使用 Python GPIO 适配器安全关闭
    python3 << 'PYTHON_EOF'
import sys
import os
sys.path.insert(0, '/home/sunrise/pupperv3-monorepo/ros2_ws/src/pupper_feelings/pupper_feelings')

try:
    from gpio_adapter import ServoAdapter
    print("Creating servo instances...")
    servo_l = ServoAdapter(16)
    servo_r = ServoAdapter(26)

    print("Detaching servos...")
    servo_l.detach()
    servo_r.detach()

    print("Cleaning up GPIO...")
    servo_l.cleanup()
    servo_r.cleanup()

    print("GPIO safe shutdown completed")

except ImportError as e:
    print(f"Error importing GPIO adapter: {e}")
    print("Manual GPIO cleanup recommended")
except Exception as e:
    print(f"Error during GPIO cleanup: {e}")
PYTHON_EOF
}

stop_ros2_nodes() {
    log "WARN" "Stopping ROS2 nodes..."

    # 尝试停止主要的 ROS2 节点
    pkill -f "ros2" || true
    pkill -f "puperv3" || true
    pkill -f "ear_control" || true
    pkill -f "face_control" || true

    # 等待进程结束
    sleep 2

    # 检查是否还有进程在运行
    if pgrep -f "ros2" > /dev/null; then
        log "ERROR" "Some ROS2 processes still running"
        killall -9 ros2 || true
    fi

    log "INFO" "ROS2 nodes stopped"
}

get_system_status() {
    log "INFO" "Collecting system status..."

    echo "=== System Status ===" >> "$EMERGENCY_LOG"

    # CPU 信息
    local cpu_cores=$(nproc)
    echo "CPU Cores: $cpu_cores" >> "$EMERGENCY_LOG"

    # 内存信息
    local mem_total=$(free -h | grep Mem | awk '{print $2}')
    local mem_used=$(free -h | grep Mem | awk '{print $3}')
    echo "Memory: $mem_used / $mem_total" >> "$EMERGENCY_LOG"

    # 磁盘使用
    local disk_usage=$(df -h / | awk 'NR==2 {print $5}')
    echo "Disk Usage: $disk_usage" >> "$EMERGENCY_LOG"

    # 网络状态
    local network=$(ip route | grep default | awk '{print $8}')
    echo "Network Interface: $network" >> "$EMERGENCY_LOG"

    # 运行进程
    local processes=$(ps aux | wc -l)
    echo "Running Processes: $processes" >> "$EMERGENCY_LOG"

    echo "===================" >> "$EMERGENCY_LOG"
}

emergency_shutdown_procedure() {
    log "ERROR" "🚨 EMERGENCY SHUTDOWN INITIATED 🚨"
    log "ERROR" "Reason: $(cat $EMERGENCY_FILE 2>/dev/null)"

    # 1. 收集系统状态
    get_system_status

    # 2. 安全关闭 GPIO
    safe_shutdown_gpio

    # 3. 停止 ROS2 节点
    stop_ros2_nodes

    # 4. 可以在这里添加其他硬件关闭操作
    # 例如：关闭相机、停止传感器等

    log "INFO" "✅ Emergency shutdown completed safely"
}

normal_shutdown() {
    log "INFO" "Normal shutdown requested..."

    # 收集系统状态
    get_system_status

    # 正常关闭程序
    safe_shutdown_gpio
    stop_ros2_nodes

    log "INFO" "✅ Normal shutdown completed"
}

# 主程序
case "$1" in
    "monitor")
        # 监控模式：持续检查紧急情况
        log "INFO" "Starting emergency monitoring..."
        log "INFO" "Press Ctrl+C to stop monitoring"

        trap 'echo "Monitoring stopped"; exit 0' INT TERM

        while true; do
            if check_emergency_conditions; then
                emergency_shutdown_procedure
                exit 1
            fi
            sleep 1
        done
        ;;

    "check")
        # 单次检查模式
        log "INFO" "Running single emergency check..."
        if check_emergency_conditions; then
            log "ERROR" "Emergency condition detected!"
            echo "Emergency: $(cat $EMERGENCY_FILE 2>/dev/null)"
            exit 1
        else
            log "INFO" "All systems normal"
            exit 0
        fi
        ;;

    "shutdown")
        # 执行紧急停机
        echo "EMERGENCY: Manual emergency shutdown" > "$EMERGENCY_FILE"
        emergency_shutdown_procedure
        ;;

    "stop")
        # 正常停机
        normal_shutdown
        ;;

    "status")
        # 显示当前状态
        echo "=== Current System Status ==="
        echo "Temperature: $(get_temperature)°C (threshold: ${MAX_TEMP}°C)"
        echo "Current: $(get_current)A (threshold: ${MAX_CURRENT}A)"
        echo "Voltage: $(get_voltage)V (range: ${MIN_VOLTAGE}V-${MAX_VOLTAGE}V)"

        if [ -f "$EMERGENCY_FILE" ]; then
            echo "Last Emergency: $(cat $EMERGENCY_FILE)"
        fi
        ;;

    "log")
        # 显示日志
        if [ -f "$EMERGENCY_LOG" ]; then
            echo "=== Emergency Log ==="
            tail -20 "$EMERGENCY_LOG"
        else
            echo "No emergency log found"
        fi
        ;;

    *)
        # 默认：显示使用说明
        cat << EOF
Pupper V3 Emergency Shutdown Script

用法:
    $0 [command]

命令:
    monitor    - 持续监控紧急情况（按 Ctrl+C 停止）
    check      - 执行单次紧急检查
    shutdown   - 执行紧急停机
    stop       - 执行正常停机
    status     - 显示当前系统状态
    log        - 显示紧急日志

配置:
    最大温度: ${MAX_TEMP}°C
    最大电流: ${MAX_CURRENT}A
    电压范围: ${MIN_VOLTAGE}V - ${MAX_VOLTAGE}V

示例:
    # 持续监控（推荐在后台运行）
    sudo $0 monitor &

    # 单次检查
    sudo $0 check

    # 查看状态
    $0 status

    # 查看日志
    $0 log

EOF
        exit 0
        ;;
esac
