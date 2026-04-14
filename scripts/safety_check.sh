#!/bin/bash
#
# safety_check.sh - Pupper V3 系统安全检查脚本
#
# 用途: 在启动机器人系统前进行全面的安全检查
# 使用: ./safety_check.sh
#

set -e

# 配置
LOG_FILE="/tmp/pupper_safety_check.log"
MAX_TEMP=70               # 启动前最大温度 (°C)
MAX_CURRENT=4              # 启动前最大电流 (A)
MIN_VOLTAGE=4.9           # 最小电压 (V)
MAX_VOLTAGE=5.1           # 最大电压 (V)

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    local level=$1
    shift
    local message="$@"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${timestamp} [${level}] ${message}" | tee -a "$LOG_FILE"
}

print_header() {
    echo ""
    echo "╔════════════════════════════════════════════════════════╗"
    echo "║                                                              ║"
    echo "║       Pupper V3 - RDK X5 迁移安全检查                   ║"
    echo "║                                                              ║"
    echo "╚════════════════════════════════════════════════════════╝"
    echo ""
}

check_permissions() {
    log "INFO" "检查系统权限..."

    # 检查 GPIO 访问权限
    if [ -c /dev/gpiochip0 ]; then
        local gpio_group=$(stat -c "%G" /dev/gpiochip0)
        local current_user=$(whoami)
        log "INFO" "GPIO 设备组: $gpio_group"

        if groups "$current_user" | grep -q "$gpio_group"; then
            echo -e "${GREEN}✅${NC} GPIO 访问权限正常"
        else
            echo -e "${YELLOW}⚠️${NC} GPIO 访问权限不足"
            echo "   建议: sudo usermod -a -G $gpio_group $current_user"
            return 1
        fi
    else
        echo -e "${RED}❌${NC} GPIO 设备不存在"
        return 1
    fi

    # 检查 I2C 访问权限
    if [ -c /dev/i2c-0 ]; then
        local i2c_group=$(stat -c "%G" /dev/i2c-0)
        if groups "$current_user" | grep -q "$i2c_group"; then
            echo -e "${GREEN}✅${NC} I2C 访问权限正常"
        else
            echo -e "${YELLOW}⚠️${NC} I2C 访问权限不足"
            echo "   建议: sudo usermod -a -G $i2c_group $current_user"
            return 1
        fi
    else
        echo -e "${YELLOW}⚠️${NC} I2C 设备不存在（可能正常）"
    fi

    # 检查 SPI 访问权限
    if [ -c /dev/spidev1.0 ]; then
        local spi_group=$(stat -c "%G" /dev/spidev1.0)
        if groups "$current_user" | grep -q "$spi_group"; then
            echo -e "${GREEN}✅${NC} SPI 访问权限正常"
        else
            echo -e "${YELLOW}⚠️${NC} SPI 访问权限不足"
            echo "   建议: sudo usermod -a -G $spi_group $current_user"
            return 1
        fi
    else
        echo -e "${RED}❌${NC} SPI 设备不存在"
        return 1
    fi

    return 0
}

check_platform_detection() {
    log "INFO" "检查平台检测..."

    cd /home/sunrise/pupperv3-monorepo/ros2_ws/src/pupper_feelings/pupper_feelings

    python3 << 'PYTHON_EOF'
import sys
try:
    from platform_detection import get_platform_info
    info = get_platform_info()

    print(f"平台: {info['platform']}")
    print(f"GPIO 库: {info['gpio_library']}")
    print(f"Python 版本: {info['python_version']}")

    if info['platform'] == 'rdk_x5':
        print("✅ 平台检测正常: RDK X5")
    elif info['platform'] == 'raspberry_pi':
        print("✅ 平台检测正常: Raspberry Pi")
    else:
        print("⚠️ 未知平台")
        sys.exit(1)

    device_paths = info['device_paths']
    print(f"I2C 总线: {device_paths['i2c_bus']}")
    print(f"SPI 设备: {device_paths['spi_device_1']}")

except ImportError as e:
    print(f"❌ 导入错误: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ 平台检测错误: {e}")
    sys.exit(1)
PYTHON_EOF
}

check_gpio_basic() {
    log "INFO" "检查 GPIO 基础功能..."

    cd /home/sunrise/pupperv3-monorepo/ros2_ws/src/pupper_feelings/pupper_feelings

    python3 << 'PYTHON_EOF'
import sys
try:
    from gpio_adapter import ServoAdapter
    import time

    print("测试 GPIO 初始化...")
    servo = ServoAdapter(16)
    print("✅ GPIO 16 初始化成功")

    print("测试基本控制...")
    servo.value = 0.0
    time.sleep(0.1)
    servo.value = 0.5
    time.sleep(0.1)
    servo.value = 0.0
    print("✅ GPIO 16 基本控制正常")

    servo.cleanup()
    print("✅ GPIO 16 清理完成")

except ImportError as e:
    print(f"❌ 导入错误: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ GPIO 测试错误: {e}")
    sys.exit(1)
PYTHON_EOF
}

check_i2c_devices() {
    log "INFO" "扫描 I2C 设备..."

    cd /home/sunrise/pupperv3-monorepo/ros2_ws/src/pupper_feelings/pupper_feelings

    python3 << 'PYTHON_EOF'
from i2c_adapter import detect_i2c_devices

print("扫描 I2C 总线...")
devices = detect_i2c_devices()

if devices:
    print("发现的 I2C 设备:")
    for bus_num, addr_list in devices.items():
        print(f"  总线 {bus_num}: {[hex(addr) for addr in addr_list]}")
else:
    print("⚠️ 未发现 I2C 设备（可能正常，如果没有传感器连接）")
PYTHON_EOF
}

check_spi_devices() {
    log "INFO" "检查 SPI 设备..."

    echo "检查 SPI 设备文件..."
    if [ -c /dev/spidev1.0 ] && [ -c /dev/spidev1.1 ]; then
        echo -e "${GREEN}✅${NC} SPI 设备存在"
        ls -l /dev/spidev*
        return 0
    else
        echo -e "${RED}❌${NC} SPI 设备缺失"
        return 1
    fi
}

check_power_status() {
    log "INFO" "检查电源状态..."

    # 温度
    local temp=$(cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | sort -n | head -1)
    temp=$((temp / 1000))
    echo "系统温度: ${temp}°C (阈值: ${MAX_TEMP}°C)"

    if [ $temp -gt $MAX_TEMP ]; then
        echo -e "${RED}❌${NC} 温度过高！"
        return 1
    else
        echo -e "${GREEN}✅${NC} 温度正常"
    fi

    # 电流
    local current=0
    for current_file in /sys/class/power_supply/*/current_now; do
        if [ -f "$current_file" ]; then
            local val=$(cat "$current_file")
            val=$((val / 1000000))
            if [ $val -gt $current ]; then
                current=$val
            fi
        fi
    done

    if [ $current -gt 0 ]; then
        echo "系统电流: ${current}A (阈值: ${MAX_CURRENT}A)"
        if [ $current -gt $MAX_CURRENT ]; then
            echo -e "${YELLOW}⚠️${NC} 电流较高（可能需要更强电源）"
        else
            echo -e "${GREEN}✅${NC} 电流正常"
        fi
    else
        echo "⚠️ 无法读取电流"
    fi

    # 电压
    local voltage=0
    for voltage_file in /sys/class/regulator/regulator.*5v/voltage; do
        if [ -f "$voltage_file" ]; then
            voltage=$(cat "$voltage_file")
            voltage=$((voltage / 1000000))
            break
        fi
    done

    if [ $voltage -gt 0 ]; then
        echo "系统电压: ${voltage}V (范围: ${MIN_VOLTAGE}V-${MAX_VOLTAGE}V)"
        if [ $(echo "$voltage < $MIN_VOLTAGE" | bc -l) -eq 1 ] || \
           [ $(echo "$voltage > $MAX_VOLTAGE" | bc -l) -eq 1 ]; then
            echo -e "${YELLOW}⚠️${NC} 电压异常"
            return 1
        else
            echo -e "${GREEN}✅${NC} 电压正常"
        fi
    else
        echo "⚠️ 无法读取电压"
    fi

    return 0
}

check_system_resources() {
    log "INFO" "检查系统资源..."

    # CPU
    local cpu_cores=$(nproc)
    echo "CPU 核心: $cpu_cores"

    # 内存
    local mem_total=$(free -h | grep Mem | awk '{print $2}')
    local mem_used=$(free -h | grep Mem | awk '{print $3}')
    local mem_percent=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
    echo "内存: $mem_used / $mem_total (${mem_percent}%)"

    if [ ${mem_percent%.*} -gt 80 ]; then
        echo -e "${YELLOW}⚠️${NC} 内存使用率较高"
    else
        echo -e "${GREEN}✅${NC} 内存使用正常"
    fi

    # 磁盘
    local disk_usage=$(df -h / | awk 'NR==2 {print $5}')
    echo "磁盘使用: $disk_usage"

    if [ ${disk_usage%.*} -gt 90 ]; then
        echo -e "${YELLOW}⚠️${NC} 磁盘使用率较高"
    else
        echo -e "${GREEN}✅${NC} 磁盘使用正常"
    fi
}

run_integration_test() {
    log "INFO" "运行集成测试..."

    cd /home/sunrise/pupperv3-monorepo/ros2_ws/src/pupper_feelings/pupper_feelings

    python3 integration_test.py
}

print_summary() {
    echo ""
    echo "════════════════════════════════════════════════════════"
    echo "                  安全检查总结"
    echo "════════════════════════════════════════════════════════"
    echo ""

    echo "✅ 所有系统检查完成"
    echo ""
    echo "建议:"
    echo "1. 如果所有检查通过，可以安全启动机器人系统"
    echo "2. 启动后，运行: sudo ./emergency_shutdown.sh monitor &"
    echo "3. 遇到任何异常，查看: cat $LOG_FILE"
    echo "4. 详细风险分析请参阅: docs/RDK_X5_Risk_Analysis.md"
    echo ""
}

main() {
    # 清空日志文件
    > "$LOG_FILE"

    print_header

    local failed=0

    # 执行所有检查
    check_permissions || failed=1
    echo ""

    check_platform_detection || failed=1
    echo ""

    check_gpio_basic || failed=1
    echo ""

    check_i2c_devices
    echo ""

    check_spi_devices || failed=1
    echo ""

    check_power_status || failed=1
    echo ""

    check_system_resources
    echo ""

    # 如果没有关键错误，运行集成测试
    if [ $failed -eq 0 ]; then
        echo -e "${GREEN}所有基础检查通过，运行集成测试...${NC}"
        run_integration_test
    else
        echo -e "${RED}发现关键问题，跳过集成测试${NC}"
        return 1
    fi

    print_summary
}

main
