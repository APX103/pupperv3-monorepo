/*!
 * @file spi_platform_config.h
 * @brief SPI platform configuration for Pupper V3 robot
 *
 * This file provides platform-specific SPI device configurations
 * for Raspberry Pi and RDK X5 platforms.
 */

#ifndef SPI_PLATFORM_CONFIG_H
#define SPI_PLATFORM_CONFIG_H

#include <string>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * @brief SPI platform configuration structure
 */
struct SPIPlatformConfig {
    const char* spi_device_1;      ///< Primary SPI device path
    const char* spi_device_2;      ///< Secondary SPI device path
    unsigned int spi_speed;         ///< SPI clock speed in Hz
    unsigned char spi_mode;         ///< SPI mode (0-3)
    unsigned char spi_bits_per_word; ///< Bits per word transfer
};

/**
 * @brief Get SPI configuration for current platform
 *
 * @return SPIPlatformConfig Platform-specific configuration
 */
SPIPlatformConfig get_spi_platform_config(void);

/**
 * @brief Detect the current hardware platform
 *
 * @return int Platform code (0=Pi, 1=RDK X5, -1=unknown)
 */
int detect_hardware_platform(void);

/**
 * @brief Platform detection codes
 */
#define PLATFORM_RASPBERRY_PI 0
#define PLATFORM_RDK_X5 1
#define PLATFORM_UNKNOWN -1

#ifdef __cplusplus
}
#endif

#endif // SPI_PLATFORM_CONFIG_H