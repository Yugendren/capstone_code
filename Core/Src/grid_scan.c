/**
 ******************************************************************************
 * @file           : grid_scan.c
 * @brief          : 16x32 Grid Scanning Engine (ADS1220 Version)
 * @author         : Capstone Project
 * @date           : 2026-01-13
 ******************************************************************************
 */

/* Includes ------------------------------------------------------------------*/
#include "grid_scan.h"
#include <string.h>

/* Private variables ---------------------------------------------------------*/

GridData_t g_GridData;

static UART_HandleTypeDef *s_hUart = NULL;
static uint8_t s_TxBuffer[PACKET_TOTAL_SIZE];
static uint8_t s_IsCalibrated = 0;

/* Private function prototypes -----------------------------------------------*/

/* Exported functions --------------------------------------------------------*/

/**
 * @brief  Initialize the grid scanning system
 */
void GRID_Init(SPI_HandleTypeDef *hspi, UART_HandleTypeDef *huart)
{
    s_hUart = huart;
    
    /* Clear grid data */
    memset(&g_GridData, 0, sizeof(GridData_t));
    g_GridData.state = GRID_STATE_IDLE;
    
    /* Initialize all ADS1220 chips */
    ADS1220_Init(hspi);
    
    /* Disable all rows initially */
    GRID_DisableAllRows();
    
    /* Prepare packet header */
    s_TxBuffer[0] = PACKET_SYNC_BYTE_1;
    s_TxBuffer[1] = PACKET_SYNC_BYTE_2;
}

/**
 * @brief  Enable a specific row
 */
void GRID_EnableRow(uint8_t row)
{
    if (row >= GRID_NUM_ROWS) return;
    
    /* Disable all rows first */
    GRID_DisableAllRows();
    
    /* Enable the specific row (set HIGH) */
    HAL_GPIO_WritePin(ROW_GPIO_PORT, (1U << row), GPIO_PIN_SET);
}

/**
 * @brief  Disable all rows
 */
void GRID_DisableAllRows(void)
{
    /* Set all row GPIOs LOW */
    HAL_GPIO_WritePin(ROW_GPIO_PORT, ROW_GPIO_PINS, GPIO_PIN_RESET);
}

/**
 * @brief  Perform baseline calibration
 */
void GRID_Calibrate(void)
{
    #define CALIBRATION_SAMPLES 4
    
    g_GridData.state = GRID_STATE_CALIBRATING;
    
    /* Clear baseline */
    memset(g_GridData.baseline, 0, sizeof(g_GridData.baseline));
    
    /* Accumulate multiple scans */
    for (uint8_t scan = 0; scan < CALIBRATION_SAMPLES; scan++) {
        for (uint8_t row = 0; row < GRID_NUM_ROWS; row++) {
            /* Enable this row */
            GRID_EnableRow(row);
            HAL_Delay(1);  /* Settling time */
            
            /* Read all 32 columns */
            uint32_t colValues[GRID_NUM_COLS];
            ADS1220_ReadAllColumns(colValues);
            
            /* Accumulate */
            for (uint8_t col = 0; col < GRID_NUM_COLS; col++) {
                g_GridData.baseline[row][col] += colValues[col];
            }
        }
    }
    
    /* Average */
    for (uint8_t row = 0; row < GRID_NUM_ROWS; row++) {
        for (uint8_t col = 0; col < GRID_NUM_COLS; col++) {
            g_GridData.baseline[row][col] /= CALIBRATION_SAMPLES;
        }
    }
    
    GRID_DisableAllRows();
    s_IsCalibrated = 1;
    g_GridData.state = GRID_STATE_IDLE;
}

/**
 * @brief  Scan the entire 16x32 grid
 */
void GRID_ScanMatrix(void)
{
    g_GridData.state = GRID_STATE_SCANNING;
    
    for (uint8_t row = 0; row < GRID_NUM_ROWS; row++) {
        /* Enable this row (drive 3.3V through velostat) */
        GRID_EnableRow(row);
        
        /* Small delay for voltage to stabilize */
        /* Note: Could be reduced with testing */
        for (volatile int i = 0; i < 100; i++);
        
        /* Read all 32 columns via ADS1220s */
        uint32_t colValues[GRID_NUM_COLS];
        ADS1220_ReadAllColumns(colValues);
        
        /* Process and store values */
        for (uint8_t col = 0; col < GRID_NUM_COLS; col++) {
            uint32_t raw = colValues[col];
            uint32_t pressure;
            
            if (s_IsCalibrated) {
                /* Subtract baseline */
                int32_t diff = (int32_t)g_GridData.baseline[row][col] - (int32_t)raw;
                pressure = (diff > 0) ? (uint32_t)diff : 0;
            } else {
                /* Invert: higher pressure = lower ADC reading */
                pressure = (raw < ADC_MAX_VALUE) ? (ADC_MAX_VALUE - raw) : 0;
            }
            
            /* Apply noise threshold */
            if (pressure < ADC_NOISE_THRESHOLD) {
                pressure = 0;
            }
            
            /* Scale 24-bit to 16-bit for transmission */
            g_GridData.data[row][col] = (uint16_t)(pressure >> ADC_SCALE_SHIFT);
        }
    }
    
    GRID_DisableAllRows();
    g_GridData.frameCount++;
    g_GridData.lastScanTimeMs = HAL_GetTick();
    g_GridData.state = GRID_STATE_IDLE;
}

/**
 * @brief  Transmit grid data in binary format
 */
void GRID_TransmitData(void)
{
    g_GridData.state = GRID_STATE_TRANSMITTING;
    
    uint16_t checksum = 0;
    uint16_t idx = PACKET_HEADER_SIZE;
    
    /* Pack 512 x 16-bit values */
    for (uint8_t row = 0; row < GRID_NUM_ROWS; row++) {
        for (uint8_t col = 0; col < GRID_NUM_COLS; col++) {
            uint16_t val = g_GridData.data[row][col];
            
            s_TxBuffer[idx++] = (uint8_t)(val & 0xFF);
            s_TxBuffer[idx++] = (uint8_t)(val >> 8);
            
            checksum += (val & 0xFF);
            checksum += (val >> 8);
        }
    }
    
    /* Footer */
    s_TxBuffer[idx++] = (uint8_t)(checksum & 0xFF);
    s_TxBuffer[idx++] = (uint8_t)(checksum >> 8);
    s_TxBuffer[idx++] = '\r';
    s_TxBuffer[idx++] = '\n';
    
    /* Transmit */
    HAL_UART_Transmit(s_hUart, s_TxBuffer, PACKET_TOTAL_SIZE, HAL_MAX_DELAY);
    
    g_GridData.state = GRID_STATE_IDLE;
}

/**
 * @brief  Main scan loop
 */
void GRID_ScanLoop(void)
{
    GRID_ScanMatrix();
    GRID_TransmitData();
}
