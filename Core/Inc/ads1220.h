/**
 ******************************************************************************
 * @file           : ads1220.h
 * @brief          : ADS1220 24-bit ADC Driver Header
 * @author         : Capstone Project
 * @date           : 2026-01-13
 ******************************************************************************
 * @attention
 *
 * Driver for Texas Instruments ADS1220 24-bit, 4-channel Delta-Sigma ADC.
 * Used for reading columns in the 12x20 piezoelectric force sensing grid.
 *
 ******************************************************************************
 *
 *                    ADS1220 PIN LAYOUT (TSSOP-16)
 *
 *                         ┌────────────┐
 *             AIN0/REFP0 ─│ 1      16 │─ DVDD
 *             AIN1/REFN0 ─│ 2      15 │─ DGND
 *             AIN2/REFP1 ─│ 3      14 │─ CLK (external clock input)
 *             AIN3/REFN1 ─│ 4      13 │─ DRDY (data ready, active LOW)
 *                   AVDD ─│ 5      12 │─ DOUT/DRDY (SPI MISO)
 *                   AVSS ─│ 6      11 │─ DIN (SPI MOSI)
 *                REFOUT  ─│ 7      10 │─ SCLK (SPI clock)
 *                 REFN1  ─│ 8       9 │─ CS (chip select, active LOW)
 *                         └────────────┘
 *
 ******************************************************************************
 */

#ifndef __ADS1220_H
#define __ADS1220_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Exported defines ----------------------------------------------------------*/

/**
 * @defgroup ADS1220_COUNT Number of ADS1220 chips
 * @{
 */
#define ADS1220_NUM_CHIPS       5U      /**< 5 ADS1220 chips for 20 columns */
#define ADS1220_CHANNELS        4U      /**< 4 single-ended channels per chip */
#define ADS1220_TOTAL_CHANNELS  (ADS1220_NUM_CHIPS * ADS1220_CHANNELS)  /**< 20 */
/** @} */

/**
 * @defgroup ADS1220_COMMANDS SPI Commands
 * @{
 */
#define ADS1220_CMD_RESET       0x06U   /**< Reset the device */
#define ADS1220_CMD_START       0x08U   /**< Start/Sync conversions */
#define ADS1220_CMD_POWERDOWN   0x02U   /**< Enter power-down mode */
#define ADS1220_CMD_RDATA       0x10U   /**< Read data by command */
#define ADS1220_CMD_RREG        0x20U   /**< Read register (OR with addr << 2) */
#define ADS1220_CMD_WREG        0x40U   /**< Write register (OR with addr << 2) */
/** @} */

/**
 * @defgroup ADS1220_REGISTERS Register Addresses
 * @{
 */
#define ADS1220_REG0            0x00U   /**< Config Register 0 */
#define ADS1220_REG1            0x01U   /**< Config Register 1 */
#define ADS1220_REG2            0x02U   /**< Config Register 2 */
#define ADS1220_REG3            0x03U   /**< Config Register 3 */
/** @} */

/**
 * @defgroup ADS1220_REG0_BITS Register 0 Configuration
 * @brief MUX[3:0] | GAIN[2:0] | PGA_BYPASS
 * @{
 */
/* Input Multiplexer (MUX) - Single-ended inputs */
#define ADS1220_MUX_AIN0_AVSS   0x80U   /**< AIN0 vs AVSS */
#define ADS1220_MUX_AIN1_AVSS   0x90U   /**< AIN1 vs AVSS */
#define ADS1220_MUX_AIN2_AVSS   0xA0U   /**< AIN2 vs AVSS */
#define ADS1220_MUX_AIN3_AVSS   0xB0U   /**< AIN3 vs AVSS */

/* Gain settings */
#define ADS1220_GAIN_1          0x00U   /**< Gain = 1 */
#define ADS1220_GAIN_2          0x02U   /**< Gain = 2 */
#define ADS1220_GAIN_4          0x04U   /**< Gain = 4 */

/* PGA Bypass */
#define ADS1220_PGA_BYPASS      0x01U   /**< Bypass PGA (for >2.5V inputs) */
/** @} */

/**
 * @defgroup ADS1220_REG1_BITS Register 1 Configuration
 * @brief DR[2:0] | MODE[1:0] | CM | TS | BCS
 * @{
 */
/* Data Rate (Normal Mode) */
#define ADS1220_DR_20SPS        0x00U   /**< 20 SPS */
#define ADS1220_DR_45SPS        0x20U   /**< 45 SPS */
#define ADS1220_DR_90SPS        0x40U   /**< 90 SPS */
#define ADS1220_DR_175SPS       0x60U   /**< 175 SPS */
#define ADS1220_DR_330SPS       0x80U   /**< 330 SPS */
#define ADS1220_DR_600SPS       0xA0U   /**< 600 SPS */
#define ADS1220_DR_1000SPS      0xC0U   /**< 1000 SPS (Turbo mode) */

/* Operating Mode */
#define ADS1220_MODE_NORMAL     0x00U   /**< Normal mode */
#define ADS1220_MODE_DUTY       0x08U   /**< Duty-cycle mode */
#define ADS1220_MODE_TURBO      0x10U   /**< Turbo mode */

/* Conversion Mode */
#define ADS1220_CM_SINGLE       0x00U   /**< Single-shot mode */
#define ADS1220_CM_CONTINUOUS   0x04U   /**< Continuous conversion */
/** @} */

/**
 * @defgroup ADS1220_REG2_BITS Register 2 Configuration  
 * @brief VREF[1:0] | 50/60[1:0] | PSW | IDAC[2:0]
 * @{
 */
#define ADS1220_VREF_INTERNAL   0x00U   /**< Internal 2.048V reference */
#define ADS1220_VREF_EXTERNAL   0x40U   /**< External reference REF0 */
#define ADS1220_VREF_AVDD       0x80U   /**< Use AVDD as reference */

#define ADS1220_REJECT_OFF      0x00U   /**< No 50/60Hz rejection */
#define ADS1220_REJECT_BOTH     0x10U   /**< Reject 50Hz and 60Hz */
/** @} */

/* Exported types ------------------------------------------------------------*/

/**
 * @brief  ADS1220 chip handle structure
 */
typedef struct {
    GPIO_TypeDef *cs_port;      /**< Chip select GPIO port */
    uint16_t cs_pin;            /**< Chip select GPIO pin */
    uint8_t config_reg[4];      /**< Cached configuration registers */
} ADS1220_Handle_t;

/* Exported variables --------------------------------------------------------*/

extern ADS1220_Handle_t g_ADS1220[ADS1220_NUM_CHIPS];

/* Exported functions --------------------------------------------------------*/

/**
 * @brief  Initialize all ADS1220 chips
 * @param  hspi: Pointer to SPI handle
 * @retval None
 */
void ADS1220_Init(SPI_HandleTypeDef *hspi);

/**
 * @brief  Reset a specific ADS1220 chip
 * @param  chipIndex: Chip index (0-4)
 * @retval None
 */
void ADS1220_Reset(uint8_t chipIndex);

/**
 * @brief  Configure a specific ADS1220 chip
 * @param  chipIndex: Chip index (0-4)
 * @param  reg0: Register 0 value
 * @param  reg1: Register 1 value
 * @param  reg2: Register 2 value
 * @param  reg3: Register 3 value
 * @retval None
 */
void ADS1220_Configure(uint8_t chipIndex, uint8_t reg0, uint8_t reg1,
                       uint8_t reg2, uint8_t reg3);

/**
 * @brief  Set input channel on a specific ADS1220
 * @param  chipIndex: Chip index (0-4)
 * @param  channel: Channel (0-3)
 * @retval None
 */
void ADS1220_SetChannel(uint8_t chipIndex, uint8_t channel);

/**
 * @brief  Start conversion and read result from one ADS1220
 * @param  chipIndex: Chip index (0-4)
 * @retval 24-bit ADC value (right-justified in uint32_t)
 */
uint32_t ADS1220_ReadData(uint8_t chipIndex);

/**
 * @brief  Read a specific channel from a specific chip (convenience)
 * @param  chipIndex: Chip index (0-4)
 * @param  channel: Channel (0-3)
 * @retval 24-bit ADC value
 */
uint32_t ADS1220_ReadChannel(uint8_t chipIndex, uint8_t channel);

/**
 * @brief  Read all 20 columns (all chips, all channels)
 * @param  values: Array of 20 uint32_t to store results
 * @retval None
 */
void ADS1220_ReadAllColumns(uint32_t values[ADS1220_TOTAL_CHANNELS]);

#ifdef __cplusplus
}
#endif

#endif /* __ADS1220_H */
