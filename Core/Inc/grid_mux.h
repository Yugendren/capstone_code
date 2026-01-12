/**
 ******************************************************************************
 * @file           : grid_mux.h
 * @brief          : CD4051 Multiplexer Control Header
 * @author         : Capstone Project
 * @date           : 2026-01-12
 ******************************************************************************
 * @attention
 *
 * This file provides the interface for controlling CD4051/74HC4051 analog
 * multiplexers used in the 40x40 piezoelectric force sensing grid.
 *
 ******************************************************************************
 *
 *                    MULTIPLEXER ARCHITECTURE
 *    ┌─────────────────────────────────────────────────────────┐
 *    │                                                         │
 *    │   ┌─────────┐    ┌─────────┐         ┌─────────┐       │
 *    │   │ ROW MUX │    │ ROW MUX │   ...   │ ROW MUX │       │
 *    │   │    0    │    │    1    │         │    4    │       │
 *    │   │ (0-7)   │    │ (8-15)  │         │ (32-39) │       │
 *    │   └────┬────┘    └────┬────┘         └────┬────┘       │
 *    │        │              │                   │            │
 *    │        └──────────────┴───────────────────┘            │
 *    │                       │                                │
 *    │                    PA1 (Row Drive 3.3V)                │
 *    │                                                         │
 *    │   ┌─────────┐    ┌─────────┐         ┌─────────┐       │
 *    │   │ COL MUX │    │ COL MUX │   ...   │ COL MUX │       │
 *    │   │    0    │    │    1    │         │    4    │       │
 *    │   │ (0-7)   │    │ (8-15)  │         │ (32-39) │       │
 *    │   └────┬────┘    └────┬────┘         └────┬────┘       │
 *    │        │              │                   │            │
 *    │        └──────────────┴───────────────────┘            │
 *    │                       │                                │
 *    │                    PA0 (ADC Input)                     │
 *    │                                                         │
 *    └─────────────────────────────────────────────────────────┘
 *
 *    SELECT BUS: PB0 (S0), PB1 (S1), PB2 (S2) → All 10 muxes
 *    ROW ENABLE: PC0-PC4 → Row Mux 0-4 (Active LOW)
 *    COL ENABLE: PC5-PC9 → Col Mux 0-4 (Active LOW)
 *
 ******************************************************************************
 */

#ifndef __GRID_MUX_H
#define __GRID_MUX_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Exported defines ----------------------------------------------------------*/

/**
 * @defgroup GRID_DIMENSIONS Grid Dimensions
 * @brief    Size of the sensing grid (40x40 = 1600 nodes)
 * @{
 */
#define GRID_NUM_ROWS           40U     /**< Number of rows in the grid */
#define GRID_NUM_COLS           40U     /**< Number of columns in the grid */
#define GRID_TOTAL_NODES        (GRID_NUM_ROWS * GRID_NUM_COLS)  /**< 1600 total sensing points */
/** @} */

/**
 * @defgroup MUX_CONFIG Multiplexer Configuration
 * @brief    CD4051 multiplexer parameters
 * @{
 */
#define MUX_CHANNELS_PER_CHIP   8U      /**< Each CD4051 has 8 channels (Y0-Y7) */
#define MUX_ROW_COUNT           5U      /**< 5 muxes for 40 rows (5 x 8 = 40) */
#define MUX_COL_COUNT           5U      /**< 5 muxes for 40 columns (5 x 8 = 40) */
#define MUX_TOTAL_COUNT         10U     /**< Total multiplexer chips */
/** @} */

/**
 * @defgroup MUX_SELECT_PINS Multiplexer Select Pins (Shared Bus)
 * @brief    S0, S1, S2 select pins - connected to ALL muxes
 *
 *           S2  S1  S0  │ Selected Channel
 *           ────────────┼─────────────────
 *            0   0   0  │  Y0 (Channel 0)
 *            0   0   1  │  Y1 (Channel 1)
 *            0   1   0  │  Y2 (Channel 2)
 *            0   1   1  │  Y3 (Channel 3)
 *            1   0   0  │  Y4 (Channel 4)
 *            1   0   1  │  Y5 (Channel 5)
 *            1   1   0  │  Y6 (Channel 6)
 *            1   1   1  │  Y7 (Channel 7)
 * @{
 */
#define MUX_SEL_S0_PORT         GPIOB
#define MUX_SEL_S0_PIN          GPIO_PIN_0
#define MUX_SEL_S1_PORT         GPIOB
#define MUX_SEL_S1_PIN          GPIO_PIN_1
#define MUX_SEL_S2_PORT         GPIOB
#define MUX_SEL_S2_PIN          GPIO_PIN_2
/** @} */

/**
 * @defgroup ROW_MUX_ENABLE Row Multiplexer Enable Pins
 * @brief    Enable pins for row muxes (Active LOW)
 *           LOW = Enabled, HIGH = Disabled (High-Z output)
 * @{
 */
#define ROW_MUX0_EN_PORT        GPIOC
#define ROW_MUX0_EN_PIN         GPIO_PIN_0     /**< Rows 0-7 */
#define ROW_MUX1_EN_PORT        GPIOC
#define ROW_MUX1_EN_PIN         GPIO_PIN_1     /**< Rows 8-15 */
#define ROW_MUX2_EN_PORT        GPIOC
#define ROW_MUX2_EN_PIN         GPIO_PIN_2     /**< Rows 16-23 */
#define ROW_MUX3_EN_PORT        GPIOC
#define ROW_MUX3_EN_PIN         GPIO_PIN_3     /**< Rows 24-31 */
#define ROW_MUX4_EN_PORT        GPIOC
#define ROW_MUX4_EN_PIN         GPIO_PIN_4     /**< Rows 32-39 */
/** @} */

/**
 * @defgroup COL_MUX_ENABLE Column Multiplexer Enable Pins
 * @brief    Enable pins for column muxes (Active LOW)
 *           LOW = Enabled, HIGH = Disabled (High-Z output)
 * @{
 */
#define COL_MUX0_EN_PORT        GPIOC
#define COL_MUX0_EN_PIN         GPIO_PIN_5     /**< Cols 0-7 */
#define COL_MUX1_EN_PORT        GPIOC
#define COL_MUX1_EN_PIN         GPIO_PIN_6     /**< Cols 8-15 */
#define COL_MUX2_EN_PORT        GPIOC
#define COL_MUX2_EN_PIN         GPIO_PIN_7     /**< Cols 16-23 */
#define COL_MUX3_EN_PORT        GPIOC
#define COL_MUX3_EN_PIN         GPIO_PIN_8     /**< Cols 24-31 */
#define COL_MUX4_EN_PORT        GPIOC
#define COL_MUX4_EN_PIN         GPIO_PIN_9     /**< Cols 32-39 */
/** @} */

/**
 * @defgroup ANALOG_PINS Analog I/O Pins
 * @brief    Row drive and ADC input pins
 * @{
 */
#define ROW_DRIVE_PORT          GPIOA
#define ROW_DRIVE_PIN           GPIO_PIN_1     /**< PA1 - drives all row mux Z pins */
#define ADC_COL_CHANNEL         ADC_CHANNEL_1  /**< PA0/ADC1_IN1 - column sensing */
/** @} */

/* Exported types ------------------------------------------------------------*/

/**
 * @brief  Multiplexer type enumeration
 */
typedef enum {
    MUX_TYPE_ROW = 0,   /**< Row multiplexer (for driving rows) */
    MUX_TYPE_COL = 1    /**< Column multiplexer (for reading columns) */
} MuxType_t;

/**
 * @brief  Row enable pin lookup structure
 */
typedef struct {
    GPIO_TypeDef *port;
    uint16_t pin;
} MuxEnablePin_t;

/* Exported constants --------------------------------------------------------*/

extern const MuxEnablePin_t RowMuxEnablePins[MUX_ROW_COUNT];
extern const MuxEnablePin_t ColMuxEnablePins[MUX_COL_COUNT];

/* Exported functions --------------------------------------------------------*/

/**
 * @brief  Initialize all multiplexer GPIO pins
 * @note   Call this after MX_GPIO_Init() in main.c
 *         Sets all enable pins HIGH (disabled) initially
 * @retval None
 */
void MUX_Init(void);

/**
 * @brief  Set the 3-bit select value on the shared S0/S1/S2 bus
 * @param  channel: Channel number (0-7) to select on the enabled mux
 *
 *         Bit mapping:
 *         - Bit 0 → S0 (PB0)
 *         - Bit 1 → S1 (PB1)
 *         - Bit 2 → S2 (PB2)
 *
 * @retval None
 */
void MUX_SetChannel(uint8_t channel);

/**
 * @brief  Enable a specific row multiplexer (Active LOW)
 * @param  muxIndex: Row mux index (0-4)
 *         - 0: Enables rows 0-7
 *         - 1: Enables rows 8-15
 *         - 2: Enables rows 16-23
 *         - 3: Enables rows 24-31
 *         - 4: Enables rows 32-39
 * @note   All other row muxes will be disabled
 * @retval None
 */
void MUX_EnableRowMux(uint8_t muxIndex);

/**
 * @brief  Enable a specific column multiplexer (Active LOW)
 * @param  muxIndex: Column mux index (0-4)
 *         - 0: Enables cols 0-7
 *         - 1: Enables cols 8-15
 *         - 2: Enables cols 16-23
 *         - 3: Enables cols 24-31
 *         - 4: Enables cols 32-39
 * @note   All other column muxes will be disabled
 * @retval None
 */
void MUX_EnableColMux(uint8_t muxIndex);

/**
 * @brief  Disable all row multiplexers (set enable pins HIGH)
 * @retval None
 */
void MUX_DisableAllRowMux(void);

/**
 * @brief  Disable all column multiplexers (set enable pins HIGH)
 * @retval None
 */
void MUX_DisableAllColMux(void);

/**
 * @brief  Select a specific row to drive
 * @param  row: Row index (0-39)
 * @note   This function:
 *         1. Calculates which mux chip (row / 8)
 *         2. Calculates which channel within the mux (row % 8)
 *         3. Enables the correct mux, disables others
 *         4. Sets the channel select bits
 * @retval None
 */
void MUX_SelectRow(uint8_t row);

/**
 * @brief  Select a specific column to read
 * @param  col: Column index (0-39)
 * @note   This function:
 *         1. Calculates which mux chip (col / 8)
 *         2. Calculates which channel within the mux (col % 8)
 *         3. Enables the correct mux, disables others
 *         4. Sets the channel select bits
 * @retval None
 */
void MUX_SelectCol(uint8_t col);

#ifdef __cplusplus
}
#endif

#endif /* __GRID_MUX_H */
