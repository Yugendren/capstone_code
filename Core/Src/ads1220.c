/**
 ******************************************************************************
 * @file           : ads1220.c
 * @brief          : ADS1220 24-bit ADC Driver Implementation
 * @author         : Capstone Project
 * @date           : 2026-01-13
 ******************************************************************************
 */

/* Includes ------------------------------------------------------------------*/
#include "ads1220.h"
#include <string.h>

/* Private variables ---------------------------------------------------------*/

/** @brief  Pointer to SPI handle */
static SPI_HandleTypeDef *s_hSpi = NULL;

/** @brief  ADS1220 chip handles with CS pin assignments */
ADS1220_Handle_t g_ADS1220[ADS1220_NUM_CHIPS];

/** @brief  MUX register values for each channel (single-ended vs AVSS) */
static const uint8_t s_ChannelMux[4] = {
    ADS1220_MUX_AIN0_AVSS,  /* Channel 0 */
    ADS1220_MUX_AIN1_AVSS,  /* Channel 1 */
    ADS1220_MUX_AIN2_AVSS,  /* Channel 2 */
    ADS1220_MUX_AIN3_AVSS   /* Channel 3 */
};

/* Private function prototypes -----------------------------------------------*/
static void ADS1220_CS_Low(uint8_t chipIndex);
static void ADS1220_CS_High(uint8_t chipIndex);
static void ADS1220_SendCommand(uint8_t chipIndex, uint8_t cmd);
static void ADS1220_WriteRegister(uint8_t chipIndex, uint8_t reg, uint8_t value);
static uint8_t ADS1220_ReadRegister(uint8_t chipIndex, uint8_t reg);
static void ADS1220_WaitDRDY(uint8_t chipIndex);

/* Private functions ---------------------------------------------------------*/

/**
 * @brief  Assert chip select (active LOW)
 */
static void ADS1220_CS_Low(uint8_t chipIndex)
{
    if (chipIndex < ADS1220_NUM_CHIPS) {
        HAL_GPIO_WritePin(g_ADS1220[chipIndex].cs_port, 
                          g_ADS1220[chipIndex].cs_pin, 
                          GPIO_PIN_RESET);
    }
}

/**
 * @brief  Deassert chip select
 */
static void ADS1220_CS_High(uint8_t chipIndex)
{
    if (chipIndex < ADS1220_NUM_CHIPS) {
        HAL_GPIO_WritePin(g_ADS1220[chipIndex].cs_port, 
                          g_ADS1220[chipIndex].cs_pin, 
                          GPIO_PIN_SET);
    }
}

/**
 * @brief  Send a single command byte
 */
static void ADS1220_SendCommand(uint8_t chipIndex, uint8_t cmd)
{
    ADS1220_CS_Low(chipIndex);
    HAL_SPI_Transmit(s_hSpi, &cmd, 1, HAL_MAX_DELAY);
    ADS1220_CS_High(chipIndex);
}

/**
 * @brief  Write to a configuration register
 */
static void ADS1220_WriteRegister(uint8_t chipIndex, uint8_t reg, uint8_t value)
{
    uint8_t txData[2];
    txData[0] = ADS1220_CMD_WREG | (reg << 2);  /* WREG command + address */
    txData[1] = value;
    
    ADS1220_CS_Low(chipIndex);
    HAL_SPI_Transmit(s_hSpi, txData, 2, HAL_MAX_DELAY);
    ADS1220_CS_High(chipIndex);
    
    /* Cache the value */
    if (reg < 4) {
        g_ADS1220[chipIndex].config_reg[reg] = value;
    }
}

/**
 * @brief  Read from a configuration register
 */
static uint8_t ADS1220_ReadRegister(uint8_t chipIndex, uint8_t reg)
{
    uint8_t txData = ADS1220_CMD_RREG | (reg << 2);
    uint8_t rxData = 0;
    
    ADS1220_CS_Low(chipIndex);
    HAL_SPI_Transmit(s_hSpi, &txData, 1, HAL_MAX_DELAY);
    HAL_SPI_Receive(s_hSpi, &rxData, 1, HAL_MAX_DELAY);
    ADS1220_CS_High(chipIndex);
    
    return rxData;
}

/**
 * @brief  Wait for data ready (DRDY low on DOUT pin during CS low)
 * @note   For simplicity, we use a fixed delay based on data rate
 */
static void ADS1220_WaitDRDY(uint8_t chipIndex)
{
    /* At 1000 SPS turbo mode, conversion takes ~1ms
     * Add margin for safety */
    HAL_Delay(2);
}

/* Exported functions --------------------------------------------------------*/

/**
 * @brief  Initialize all ADS1220 chips
 */
void ADS1220_Init(SPI_HandleTypeDef *hspi)
{
    s_hSpi = hspi;
    
    /* Initialize CS pin assignments for each chip */
    /* CS0-CS7 on PA0, PA1, PA4, PA5, PA6, PA7, PA8, PA9 */
    g_ADS1220[0].cs_port = GPIOA; g_ADS1220[0].cs_pin = GPIO_PIN_0;
    g_ADS1220[1].cs_port = GPIOA; g_ADS1220[1].cs_pin = GPIO_PIN_1;
    g_ADS1220[2].cs_port = GPIOA; g_ADS1220[2].cs_pin = GPIO_PIN_4;
    g_ADS1220[3].cs_port = GPIOA; g_ADS1220[3].cs_pin = GPIO_PIN_5;
    g_ADS1220[4].cs_port = GPIOA; g_ADS1220[4].cs_pin = GPIO_PIN_6;
    g_ADS1220[5].cs_port = GPIOA; g_ADS1220[5].cs_pin = GPIO_PIN_7;
    g_ADS1220[6].cs_port = GPIOA; g_ADS1220[6].cs_pin = GPIO_PIN_8;
    g_ADS1220[7].cs_port = GPIOA; g_ADS1220[7].cs_pin = GPIO_PIN_9;
    
    /* Deselect all chips initially */
    for (uint8_t i = 0; i < ADS1220_NUM_CHIPS; i++) {
        ADS1220_CS_High(i);
    }
    
    HAL_Delay(10);  /* Power-on delay */
    
    /* Reset and configure each chip */
    for (uint8_t i = 0; i < ADS1220_NUM_CHIPS; i++) {
        ADS1220_Reset(i);
        HAL_Delay(1);
        
        /* Configure for fast single-shot readings:
         * REG0: AIN0 vs AVSS, Gain=1, PGA bypassed
         * REG1: 1000 SPS turbo, single-shot mode
         * REG2: AVDD as reference (3.3V), no 50/60Hz rejection
         * REG3: Default (no DRDY on DOUT)
         */
        ADS1220_Configure(i,
            ADS1220_MUX_AIN0_AVSS | ADS1220_GAIN_1 | ADS1220_PGA_BYPASS,
            ADS1220_DR_1000SPS | ADS1220_MODE_TURBO | ADS1220_CM_SINGLE,
            ADS1220_VREF_AVDD,
            0x00
        );
    }
}

/**
 * @brief  Reset a specific ADS1220 chip
 */
void ADS1220_Reset(uint8_t chipIndex)
{
    ADS1220_SendCommand(chipIndex, ADS1220_CMD_RESET);
}

/**
 * @brief  Configure a specific ADS1220
 */
void ADS1220_Configure(uint8_t chipIndex, uint8_t reg0, uint8_t reg1, 
                       uint8_t reg2, uint8_t reg3)
{
    ADS1220_WriteRegister(chipIndex, ADS1220_REG0, reg0);
    ADS1220_WriteRegister(chipIndex, ADS1220_REG1, reg1);
    ADS1220_WriteRegister(chipIndex, ADS1220_REG2, reg2);
    ADS1220_WriteRegister(chipIndex, ADS1220_REG3, reg3);
}

/**
 * @brief  Set input channel on a specific ADS1220
 */
void ADS1220_SetChannel(uint8_t chipIndex, uint8_t channel)
{
    if (channel >= 4) return;
    
    /* Update REG0 with new MUX setting, keep gain and PGA settings */
    uint8_t reg0 = s_ChannelMux[channel] | ADS1220_GAIN_1 | ADS1220_PGA_BYPASS;
    ADS1220_WriteRegister(chipIndex, ADS1220_REG0, reg0);
}

/**
 * @brief  Start conversion and read result
 */
uint32_t ADS1220_ReadData(uint8_t chipIndex)
{
    uint8_t rxData[3] = {0, 0, 0};
    
    /* Start conversion */
    ADS1220_SendCommand(chipIndex, ADS1220_CMD_START);
    
    /* Wait for conversion complete */
    ADS1220_WaitDRDY(chipIndex);
    
    /* Read 24-bit result */
    uint8_t cmd = ADS1220_CMD_RDATA;
    ADS1220_CS_Low(chipIndex);
    HAL_SPI_Transmit(s_hSpi, &cmd, 1, HAL_MAX_DELAY);
    HAL_SPI_Receive(s_hSpi, rxData, 3, HAL_MAX_DELAY);
    ADS1220_CS_High(chipIndex);
    
    /* Combine bytes (MSB first) */
    uint32_t value = ((uint32_t)rxData[0] << 16) | 
                     ((uint32_t)rxData[1] << 8) | 
                     ((uint32_t)rxData[2]);
    
    return value;
}

/**
 * @brief  Read a specific channel
 */
uint32_t ADS1220_ReadChannel(uint8_t chipIndex, uint8_t channel)
{
    ADS1220_SetChannel(chipIndex, channel);
    return ADS1220_ReadData(chipIndex);
}

/**
 * @brief  Read all 32 columns
 */
void ADS1220_ReadAllColumns(uint32_t values[ADS1220_TOTAL_CHANNELS])
{
    for (uint8_t chip = 0; chip < ADS1220_NUM_CHIPS; chip++) {
        for (uint8_t ch = 0; ch < ADS1220_CHANNELS; ch++) {
            uint8_t colIndex = chip * ADS1220_CHANNELS + ch;
            values[colIndex] = ADS1220_ReadChannel(chip, ch);
        }
    }
}
