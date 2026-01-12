/**
 ******************************************************************************
 * @file           : grid_mux.c
 * @brief          : CD4051 Multiplexer Control Implementation
 * @author         : Capstone Project
 * @date           : 2026-01-12
 ******************************************************************************
 * @attention
 *
 * This file implements the control functions for CD4051/74HC4051 analog
 * multiplexers used in the 40x40 piezoelectric force sensing grid.
 *
 ******************************************************************************
 *
 *                    CD4051 PIN LAYOUT (DIP-16)
 *
 *                         ┌────────────┐
 *           Channel 4 ────│ 1   U   16 │──── VDD (3.3V)
 *           Channel 6 ────│ 2       15 │──── Channel 2
 *         Z (Common) ─────│ 3       14 │──── Channel 1
 *           Channel 7 ────│ 4       13 │──── Channel 0
 *           Channel 5 ────│ 5       12 │──── Channel 3
 *    Enable (Active LOW) ─│ 6       11 │──── S0 (Select Bit 0)
 *           GND (VSS) ────│ 7       10 │──── S1 (Select Bit 1)
 *           GND (VEE) ────│ 8        9 │──── S2 (Select Bit 2)
 *                         └────────────┘
 *
 ******************************************************************************
 */

/* Includes ------------------------------------------------------------------*/
#include "grid_mux.h"

/* Private typedef -----------------------------------------------------------*/
/* Private define ------------------------------------------------------------*/
/* Private macro -------------------------------------------------------------*/
/* Private variables ---------------------------------------------------------*/

/**
 * @brief  Row multiplexer enable pin lookup table
 * @note   Index 0-4 corresponds to Row Mux 0-4
 */
const MuxEnablePin_t RowMuxEnablePins[MUX_ROW_COUNT] = {
    { ROW_MUX0_EN_PORT, ROW_MUX0_EN_PIN },  /* PC0 - Rows 0-7 */
    { ROW_MUX1_EN_PORT, ROW_MUX1_EN_PIN },  /* PC1 - Rows 8-15 */
    { ROW_MUX2_EN_PORT, ROW_MUX2_EN_PIN },  /* PC2 - Rows 16-23 */
    { ROW_MUX3_EN_PORT, ROW_MUX3_EN_PIN },  /* PC3 - Rows 24-31 */
    { ROW_MUX4_EN_PORT, ROW_MUX4_EN_PIN }   /* PC4 - Rows 32-39 */
};

/**
 * @brief  Column multiplexer enable pin lookup table
 * @note   Index 0-4 corresponds to Col Mux 0-4
 */
const MuxEnablePin_t ColMuxEnablePins[MUX_COL_COUNT] = {
    { COL_MUX0_EN_PORT, COL_MUX0_EN_PIN },  /* PC5 - Cols 0-7 */
    { COL_MUX1_EN_PORT, COL_MUX1_EN_PIN },  /* PC6 - Cols 8-15 */
    { COL_MUX2_EN_PORT, COL_MUX2_EN_PIN }   /* PC7 - Cols 16-23 */
};

/* Private function prototypes -----------------------------------------------*/
/* Private functions ---------------------------------------------------------*/

/* Exported functions --------------------------------------------------------*/

/**
 * @brief  Initialize all multiplexer GPIO pins
 */
void MUX_Init(void)
{
    /*
     *  INITIALIZATION SEQUENCE
     *  ┌─────────────────────────────────────────────────────┐
     *  │  1. Disable all row muxes (set enable pins HIGH)    │
     *  │  2. Disable all col muxes (set enable pins HIGH)    │
     *  │  3. Set row drive LOW (no current through grid)     │
     *  │  4. Set select bits to 0 (select channel 0)         │
     *  └─────────────────────────────────────────────────────┘
     */
    
    /* Disable all row multiplexers */
    MUX_DisableAllRowMux();
    
    /* Disable all column multiplexers */
    MUX_DisableAllColMux();
    
    /* Set row drive LOW initially */
    HAL_GPIO_WritePin(ROW_DRIVE_PORT, ROW_DRIVE_PIN, GPIO_PIN_RESET);
    
    /* Set select bits to 0 */
    MUX_SetChannel(0);
}

/**
 * @brief  Set the 3-bit channel select on shared S0/S1/S2 bus
 */
void MUX_SetChannel(uint8_t channel)
{
    /*
     *  CHANNEL SELECT ENCODING
     *  ┌────────┬────────┬────────┬─────────────────┐
     *  │   S2   │   S1   │   S0   │  Selected Out   │
     *  │ (PB2)  │ (PB1)  │ (PB0)  │                 │
     *  ├────────┼────────┼────────┼─────────────────┤
     *  │   0    │   0    │   0    │      Y0         │
     *  │   0    │   0    │   1    │      Y1         │
     *  │   0    │   1    │   0    │      Y2         │
     *  │   0    │   1    │   1    │      Y3         │
     *  │   1    │   0    │   0    │      Y4         │
     *  │   1    │   0    │   1    │      Y5         │
     *  │   1    │   1    │   0    │      Y6         │
     *  │   1    │   1    │   1    │      Y7         │
     *  └────────┴────────┴────────┴─────────────────┘
     */
    
    /* Mask to 3 bits (0-7) */
    channel &= 0x07U;
    
    /* Set S0 (bit 0) */
    HAL_GPIO_WritePin(MUX_SEL_S0_PORT, MUX_SEL_S0_PIN, 
                      (channel & 0x01U) ? GPIO_PIN_SET : GPIO_PIN_RESET);
    
    /* Set S1 (bit 1) */
    HAL_GPIO_WritePin(MUX_SEL_S1_PORT, MUX_SEL_S1_PIN, 
                      (channel & 0x02U) ? GPIO_PIN_SET : GPIO_PIN_RESET);
    
    /* Set S2 (bit 2) */
    HAL_GPIO_WritePin(MUX_SEL_S2_PORT, MUX_SEL_S2_PIN, 
                      (channel & 0x04U) ? GPIO_PIN_SET : GPIO_PIN_RESET);
}

/**
 * @brief  Enable a specific row multiplexer
 */
void MUX_EnableRowMux(uint8_t muxIndex)
{
    if (muxIndex >= MUX_ROW_COUNT) {
        return;  /* Invalid index */
    }
    
    /* First disable all row muxes */
    MUX_DisableAllRowMux();
    
    /* Enable the selected one (Active LOW) */
    HAL_GPIO_WritePin(RowMuxEnablePins[muxIndex].port,
                      RowMuxEnablePins[muxIndex].pin,
                      GPIO_PIN_RESET);  /* LOW = Enabled */
}

/**
 * @brief  Enable a specific column multiplexer
 */
void MUX_EnableColMux(uint8_t muxIndex)
{
    if (muxIndex >= MUX_COL_COUNT) {
        return;  /* Invalid index */
    }
    
    /* First disable all col muxes */
    MUX_DisableAllColMux();
    
    /* Enable the selected one (Active LOW) */
    HAL_GPIO_WritePin(ColMuxEnablePins[muxIndex].port,
                      ColMuxEnablePins[muxIndex].pin,
                      GPIO_PIN_RESET);  /* LOW = Enabled */
}

/**
 * @brief  Disable all row multiplexers
 */
void MUX_DisableAllRowMux(void)
{
    for (uint8_t i = 0; i < MUX_ROW_COUNT; i++) {
        HAL_GPIO_WritePin(RowMuxEnablePins[i].port,
                          RowMuxEnablePins[i].pin,
                          GPIO_PIN_SET);  /* HIGH = Disabled */
    }
}

/**
 * @brief  Disable all column multiplexers
 */
void MUX_DisableAllColMux(void)
{
    for (uint8_t i = 0; i < MUX_COL_COUNT; i++) {
        HAL_GPIO_WritePin(ColMuxEnablePins[i].port,
                          ColMuxEnablePins[i].pin,
                          GPIO_PIN_SET);  /* HIGH = Disabled */
    }
}

/**
 * @brief  Select a specific row to drive
 */
void MUX_SelectRow(uint8_t row)
{
    /*
     *  ROW SELECTION ALGORITHM
     *  ┌──────────────────────────────────────────────┐
     *  │  row = 0-39                                   │
     *  │                                               │
     *  │  muxIndex = row / 8   (which mux chip)       │
     *  │  channel  = row % 8   (which channel Y0-Y7)  │
     *  │                                               │
     *  │  Example: row 25                              │
     *  │    muxIndex = 25 / 8 = 3  (Row Mux 3)        │
     *  │    channel  = 25 % 8 = 1  (Y1)               │
     *  │                                               │
     *  └──────────────────────────────────────────────┘
     */
    
    if (row >= GRID_NUM_ROWS) {
        return;  /* Invalid row */
    }
    
    uint8_t muxIndex = row / MUX_CHANNELS_PER_CHIP;
    uint8_t channel = row % MUX_CHANNELS_PER_CHIP;
    
    /* Set channel select bits first */
    MUX_SetChannel(channel);
    
    /* Then enable the correct mux */
    MUX_EnableRowMux(muxIndex);
}

/**
 * @brief  Select a specific column to read
 */
void MUX_SelectCol(uint8_t col)
{
    /*
     *  COLUMN SELECTION ALGORITHM
     *  ┌──────────────────────────────────────────────┐
     *  │  col = 0-39                                   │
     *  │                                               │
     *  │  muxIndex = col / 8   (which mux chip)       │
     *  │  channel  = col % 8   (which channel Y0-Y7)  │
     *  │                                               │
     *  │  Example: col 18                              │
     *  │    muxIndex = 18 / 8 = 2  (Col Mux 2)        │
     *  │    channel  = 18 % 8 = 2  (Y2)               │
     *  │                                               │
     *  └──────────────────────────────────────────────┘
     */
    
    if (col >= GRID_NUM_COLS) {
        return;  /* Invalid column */
    }
    
    uint8_t muxIndex = col / MUX_CHANNELS_PER_CHIP;
    uint8_t channel = col % MUX_CHANNELS_PER_CHIP;
    
    /* Set channel select bits first */
    MUX_SetChannel(channel);
    
    /* Then enable the correct mux */
    MUX_EnableColMux(muxIndex);
}
