/*!
 * @file spi_platform_config.cpp
 * @brief SPI platform configuration implementation
 */

#include "spi_platform_config.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#define MAX_LINE_LENGTH 1024

/**
 * @brief Detect the current hardware platform
 *
 * @return int Platform code (0=Pi, 1=RDK X5, -1=unknown)
 */
int detect_hardware_platform(void) {
    FILE* cpuinfo = fopen("/proc/cpuinfo", "r");
    if (!cpuinfo) {
        return PLATFORM_UNKNOWN;
    }

    char line[MAX_LINE_LENGTH];
    int platform = PLATFORM_UNKNOWN;

    while (fgets(line, sizeof(line), cpuinfo)) {
        // Check for Raspberry Pi
        if (strstr(line, "Raspberry Pi") || strstr(line, "BCM2835") || strstr(line, "BCM2711")) {
            platform = PLATFORM_RASPBERRY_PI;
            break;
        }

        // Check for RDK X5
        if (strstr(line, "RDK X5") || strstr(line, "horizon.ai")) {
            platform = PLATFORM_RDK_X5;
            break;
        }
    }

    fclose(cpuinfo);

    // Additional check for RDK X5 using device tree model
    if (platform == PLATFORM_UNKNOWN) {
        FILE* model_file = fopen("/sys/firmware/devicetree/base/model", "r");
        if (model_file) {
            char model[MAX_LINE_LENGTH];
            if (fgets(model, sizeof(model), model_file)) {
                if (strstr(model, "RDK") || strstr(model, "horizon")) {
                    platform = PLATFORM_RDK_X5;
                }
            }
            fclose(model_file);
        }
    }

    return platform;
}

/**
 * @brief Get SPI configuration for current platform
 *
 * @return SPIPlatformConfig Platform-specific configuration
 */
SPIPlatformConfig get_spi_platform_config(void) {
    int platform = detect_hardware_platform();
    SPIPlatformConfig config;

    switch (platform) {
        case PLATFORM_RASPBERRY_PI:
            config.spi_device_1 = "/dev/spidev0.0";
            config.spi_device_2 = "/dev/spidev0.1";
            config.spi_speed = 6000000;      // 6 MHz
            config.spi_mode = 0;             // SPI Mode 0
            config.spi_bits_per_word = 8;    // 8 bits per word
            break;

        case PLATFORM_RDK_X5:
            config.spi_device_1 = "/dev/spidev1.0";
            config.spi_device_2 = "/dev/spidev1.1";
            config.spi_speed = 6000000;      // 6 MHz
            config.spi_mode = 0;             // SPI Mode 0
            config.spi_bits_per_word = 8;    // 8 bits per word
            break;

        default:
            // Default to Raspberry Pi configuration
            config.spi_device_1 = "/dev/spidev0.0";
            config.spi_device_2 = "/dev/spidev0.1";
            config.spi_speed = 6000000;      // 6 MHz
            config.spi_mode = 0;             // SPI Mode 0
            config.spi_bits_per_word = 8;    // 8 bits per word
            break;
    }

    return config;
}