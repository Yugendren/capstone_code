/**
 ******************************************************************************
 * @file           : grid_scan.c
 * @brief          : 40x40 Grid Scanning Engine Implementation
 * @author         : Capstone Project
 * @date           : 2026-01-12
 ******************************************************************************
 * @attention
 *
 * This file implements the scanning and data streaming functions for the
 * 40x40 piezoelectric force sensing grid.
 *
 ******************************************************************************
 *
 *                    DATA FLOW DIAGRAM
 *
 *    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
 *    │  Velostat    │     │   CD4051     │     │   STM32      │
 *    │  Grid        │────▶│   Muxes      │────▶│   ADC        │
 *    │  40x40       │     │   (10 chips) │     │   12-bit     │
 *    └──────────────┘     └──────────────┘     └──────┬───────┘
 *                                                      │
 *                                                      ▼
 *    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
 *    │  Python GUI  │◀────│   UART2      │◀────│   Process    │
 *    │  Heatmap     │     │   Binary     │     │   & Invert   │
 *    └──────────────┘     └──────────────┘     └──────────────┘
 *
 ******************************************************************************
 */

/* Includes ------------------------------------------------------------------*/
#include "grid_scan.h"
#include <string.h>

/* Private typedef -----------------------------------------------------------*/
/* Private define ------------------------------------------------------------*/

/** 
 * @brief  DWT (Data Watchpoint and Trace) cycle counter for microsecond delays
 */
#define DWT_CTRL    (*(volatile uint32_t *)0xE0001000)
#define DWT_CYCCNT  (*(volatile uint32_t *)0xE0001004)
#define SCB_DEMCR   (*(volatile uint32_t *)0xE000EDFC)

/* Private macro -------------------------------------------------------------*/
/* Private variables ---------------------------------------------------------*/

/** @brief  Global grid data structure */
GridData_t g_GridData;

/** @brief  Pointer to ADC handle (set during init) */
static ADC_HandleTypeDef *s_hAdc = NULL;

/** @brief  Pointer to UART handle (set during init) */
static UART_HandleTypeDef *s_hUart = NULL;

/** @brief  Transmit buffer for binary protocol */
static uint8_t s_TxBuffer[PACKET_TOTAL_SIZE];

/** @brief  Flag indicating if calibration is complete */
static uint8_t s_IsCalibrated = 0;

/* Private function prototypes -----------------------------------------------*/
static uint16_t GRID_ReadADC(void);
static void GRID_EnableDWT(void);

/* Private functions ---------------------------------------------------------*/

/**
 * @brief  Enable DWT cycle counter for microsecond delays
 */
static void GRID_EnableDWT(void)
{
    /*
     *  DWT CYCLE COUNTER SETUP
     *  ┌──────────────────────────────────────────────────┐
     *  │  The DWT (Data Watchpoint and Trace) unit has    │
     *  │  a 32-bit cycle counter that runs at CPU speed.  │
     *  │                                                  │
     *  │  At 72 MHz:                                      │
     *  │    1 cycle = 1/72,000,000 = ~13.9 ns            │
     *  │    1 µs = 72 cycles                             │
     *  │                                                  │
     *  └──────────────────────────────────────────────────┘
     */
    
    /* Enable trace and debug blocks */
    SCB_DEMCR |= (1UL << 24);
    
    /* Reset the cycle counter */
    DWT_CYCCNT = 0;
    
    /* Enable the cycle counter */
    DWT_CTRL |= 1;
}

/**
 * @brief  Read single ADC value with averaging
 */
static uint16_t GRID_ReadADC(void)
{
    /*
     *  ADC READ WITH OVERSAMPLING
     *  ┌──────────────────────────────────────────────────┐
     *  │  Take multiple samples and average for better   │
     *  │  noise immunity. The velostat can be noisy.     │
     *  │                                                  │
     *  │  4 samples averaged = 2 extra bits of resolution│
     *  └──────────────────────────────────────────────────┘
     */
    
    uint32_t sum = 0;
    
    for (uint8_t i = 0; i < SCAN_ADC_SAMPLES; i++) {
        HAL_ADC_Start(s_hAdc);
        HAL_ADC_PollForConversion(s_hAdc, HAL_MAX_DELAY);
        sum += HAL_ADC_GetValue(s_hAdc);
        HAL_ADC_Stop(s_hAdc);
    }
    
    return (uint16_t)(sum / SCAN_ADC_SAMPLES);
}

/* Exported functions --------------------------------------------------------*/

/**
 * @brief  Microsecond delay using DWT cycle counter
 */
void GRID_DelayUs(uint32_t us)
{
    /*
     *  At 72 MHz system clock:
     *    cycles = us * 72
     */
    uint32_t startTick = DWT_CYCCNT;
    uint32_t delayTicks = us * (SystemCoreClock / 1000000);
    
    while ((DWT_CYCCNT - startTick) < delayTicks) {
        /* Wait */
    }
}

/**
 * @brief  Initialize the grid scanning system
 */
void GRID_Init(ADC_HandleTypeDef *hadc, UART_HandleTypeDef *huart)
{
    /*
     *  INITIALIZATION SEQUENCE
     *  ┌──────────────────────────────────────────────────┐
     *  │  1. Store peripheral handles                     │
     *  │  2. Clear grid data structure                    │
     *  │  3. Initialize multiplexers                      │
     *  │  4. Enable DWT for precise timing               │
     *  │  5. Prepare transmit buffer header/footer       │
     *  └──────────────────────────────────────────────────┘
     */
    
    /* Store handles */
    s_hAdc = hadc;
    s_hUart = huart;
    
    /* Clear grid data */
    memset(&g_GridData, 0, sizeof(GridData_t));
    g_GridData.state = GRID_STATE_IDLE;
    
    /* Initialize multiplexers */
    MUX_Init();
    
    /* Enable DWT cycle counter */
    GRID_EnableDWT();
    
    /* Prepare fixed parts of transmit buffer */
    s_TxBuffer[0] = PACKET_SYNC_BYTE_1;  /* 0xAA */
    s_TxBuffer[1] = PACKET_SYNC_BYTE_2;  /* 0x55 */
    
    /* Footer CR LF will be set during transmit */
}

/**
 * @brief  Perform calibration
 */
void GRID_Calibrate(void)
{
    /*
     *  CALIBRATION PROCESS
     *  ┌──────────────────────────────────────────────────┐
     *  │  1. Scan grid multiple times                     │
     *  │  2. Average readings to get baseline             │
     *  │  3. Store baseline for future subtraction        │
     *  │                                                  │
     *  │  IMPORTANT: Grid must have NO pressure during    │
     *  │  calibration for accurate baseline!              │
     *  └──────────────────────────────────────────────────┘
     */
    
    #define CALIBRATION_SAMPLES 8
    
    g_GridData.state = GRID_STATE_CALIBRATING;
    
    /* Clear baseline */
    memset(g_GridData.baseline, 0, sizeof(g_GridData.baseline));
    
    /* Accumulate multiple scans */
    for (uint8_t scan = 0; scan < CALIBRATION_SAMPLES; scan++) {
        for (uint8_t row = 0; row < GRID_NUM_ROWS; row++) {
            /* Select and drive this row */
            MUX_SelectRow(row);
            HAL_GPIO_WritePin(ROW_DRIVE_PORT, ROW_DRIVE_PIN, GPIO_PIN_SET);
            GRID_DelayUs(SCAN_ROW_SETTLE_US);
            
            for (uint8_t col = 0; col < GRID_NUM_COLS; col++) {
                /* Select this column */
                MUX_SelectCol(col);
                GRID_DelayUs(SCAN_COL_SETTLE_US);
                
                /* Accumulate reading */
                g_GridData.baseline[row][col] += GRID_ReadADC();
            }
            
            /* Deactivate row */
            HAL_GPIO_WritePin(ROW_DRIVE_PORT, ROW_DRIVE_PIN, GPIO_PIN_RESET);
        }
    }
    
    /* Average the baseline */
    for (uint8_t row = 0; row < GRID_NUM_ROWS; row++) {
        for (uint8_t col = 0; col < GRID_NUM_COLS; col++) {
            g_GridData.baseline[row][col] /= CALIBRATION_SAMPLES;
        }
    }
    
    /* Disable all muxes */
    MUX_DisableAllRowMux();
    MUX_DisableAllColMux();
    
    s_IsCalibrated = 1;
    g_GridData.state = GRID_STATE_IDLE;
}

/**
 * @brief  Read a single cell value
 */
uint16_t GRID_ReadCell(uint8_t row, uint8_t col)
{
    if (row >= GRID_NUM_ROWS || col >= GRID_NUM_COLS) {
        return 0;
    }
    
    /* Select row and drive it */
    MUX_SelectRow(row);
    HAL_GPIO_WritePin(ROW_DRIVE_PORT, ROW_DRIVE_PIN, GPIO_PIN_SET);
    GRID_DelayUs(SCAN_ROW_SETTLE_US);
    
    /* Select column */
    MUX_SelectCol(col);
    GRID_DelayUs(SCAN_COL_SETTLE_US);
    
    /* Read ADC */
    uint16_t raw = GRID_ReadADC();
    
    /* Deactivate */
    HAL_GPIO_WritePin(ROW_DRIVE_PORT, ROW_DRIVE_PIN, GPIO_PIN_RESET);
    MUX_DisableAllRowMux();
    MUX_DisableAllColMux();
    
    /*
     *  VALUE INVERSION
     *  ┌──────────────────────────────────────────────────┐
     *  │  Raw:  High resistance = high voltage = ~4095   │
     *  │        Low resistance  = low voltage  = ~0      │
     *  │                                                  │
     *  │  We want:                                        │
     *  │        No pressure  = 0                          │
     *  │        Max pressure = 4095                       │
     *  │                                                  │
     *  │  So we invert: pressure = 4095 - raw            │
     *  └──────────────────────────────────────────────────┘
     */
    
    uint16_t pressure;
    
    if (s_IsCalibrated) {
        /* Subtract baseline */
        int32_t diff = (int32_t)g_GridData.baseline[row][col] - (int32_t)raw;
        pressure = (diff > 0) ? (uint16_t)diff : 0;
    } else {
        /* Just invert */
        pressure = (raw < ADC_MAX_VALUE) ? (ADC_MAX_VALUE - raw) : 0;
    }
    
    /* Apply noise threshold */
    if (pressure < ADC_NOISE_THRESHOLD) {
        pressure = 0;
    }
    
    return pressure;
}

/**
 * @brief  Scan the entire 40x40 grid
 */
void GRID_ScanMatrix(void)
{
    /*
     *  FULL MATRIX SCAN
     *  ┌──────────────────────────────────────────────────────────┐
     *  │                                                          │
     *  │  Row 0:  ●───●───●───●───●─── ... ───●───●  (40 cols)   │
     *  │  Row 1:  ●───●───●───●───●─── ... ───●───●              │
     *  │  Row 2:  ●───●───●───●───●─── ... ───●───●              │
     *  │    ⋮          ⋮                           ⋮              │
     *  │  Row 39: ●───●───●───●───●─── ... ───●───●              │
     *  │                                                          │
     *  │  Total: 40 × 40 = 1600 readings                         │
     *  │  Target: ~25 Hz (40ms per frame)                        │
     *  │                                                          │
     *  └──────────────────────────────────────────────────────────┘
     */
    
    g_GridData.state = GRID_STATE_SCANNING;
    
    for (uint8_t row = 0; row < GRID_NUM_ROWS; row++) {
        /* Select and drive this row */
        MUX_SelectRow(row);
        HAL_GPIO_WritePin(ROW_DRIVE_PORT, ROW_DRIVE_PIN, GPIO_PIN_SET);
        GRID_DelayUs(SCAN_ROW_SETTLE_US);
        
        for (uint8_t col = 0; col < GRID_NUM_COLS; col++) {
            /* Select this column */
            MUX_SelectCol(col);
            GRID_DelayUs(SCAN_COL_SETTLE_US);
            
            /* Read and process */
            uint16_t raw = GRID_ReadADC();
            uint16_t pressure;
            
            if (s_IsCalibrated) {
                int32_t diff = (int32_t)g_GridData.baseline[row][col] - (int32_t)raw;
                pressure = (diff > 0) ? (uint16_t)diff : 0;
            } else {
                pressure = (raw < ADC_MAX_VALUE) ? (ADC_MAX_VALUE - raw) : 0;
            }
            
            /* Apply noise threshold */
            if (pressure < ADC_NOISE_THRESHOLD) {
                pressure = 0;
            }
            
            g_GridData.data[row][col] = pressure;
        }
        
        /* Deactivate row after scanning all columns */
        HAL_GPIO_WritePin(ROW_DRIVE_PORT, ROW_DRIVE_PIN, GPIO_PIN_RESET);
    }
    
    /* Disable all muxes */
    MUX_DisableAllRowMux();
    MUX_DisableAllColMux();
    
    g_GridData.frameCount++;
    g_GridData.lastScanTimeMs = HAL_GetTick();
    g_GridData.state = GRID_STATE_IDLE;
}

/**
 * @brief  Transmit grid data in binary format
 */
void GRID_TransmitData(void)
{
    /*
     *  BINARY PACKET LAYOUT
     *  ┌────────┬────────────────────────────────────┬────────┐
     *  │ 0xAA   │               PAYLOAD              │ CHKSUM │
     *  │ 0x55   │  Row0[Col0_L,Col0_H,Col1_L,...]   │  +CRLF │
     *  │(2 bytes│         (3200 bytes)               │(4 bytes)│
     *  └────────┴────────────────────────────────────┴────────┘
     */
    
    g_GridData.state = GRID_STATE_TRANSMITTING;
    
    /* Header already set in init */
    
    /* Pack payload: 1600 x 16-bit values, little-endian */
    uint16_t checksum = 0;
    uint16_t payloadIdx = PACKET_HEADER_SIZE;
    
    for (uint8_t row = 0; row < GRID_NUM_ROWS; row++) {
        for (uint8_t col = 0; col < GRID_NUM_COLS; col++) {
            uint16_t val = g_GridData.data[row][col];
            
            /* Little-endian: low byte first */
            s_TxBuffer[payloadIdx++] = (uint8_t)(val & 0xFF);
            s_TxBuffer[payloadIdx++] = (uint8_t)(val >> 8);
            
            /* Accumulate checksum */
            checksum += (val & 0xFF);
            checksum += (val >> 8);
        }
    }
    
    /* Footer: checksum + CR + LF */
    s_TxBuffer[payloadIdx++] = (uint8_t)(checksum & 0xFF);
    s_TxBuffer[payloadIdx++] = (uint8_t)(checksum >> 8);
    s_TxBuffer[payloadIdx++] = '\r';
    s_TxBuffer[payloadIdx++] = '\n';
    
    /* Transmit entire packet */
    HAL_UART_Transmit(s_hUart, s_TxBuffer, PACKET_TOTAL_SIZE, HAL_MAX_DELAY);
    
    g_GridData.state = GRID_STATE_IDLE;
}

/**
 * @brief  Main scan loop
 */
void GRID_ScanLoop(void)
{
    /*
     *  MAIN LOOP FLOW
     *  ┌──────────────────────────────────────────────────┐
     *  │                                                  │
     *  │   ┌─────────────┐                               │
     *  │   │  Scan Grid  │                               │
     *  │   │   (40x40)   │──────┐                        │
     *  │   └─────────────┘      │                        │
     *  │                        ▼                        │
     *  │              ┌─────────────────┐                │
     *  │              │ Transmit Binary │                │
     *  │              │   (3206 bytes)  │                │
     *  │              └────────┬────────┘                │
     *  │                       │                         │
     *  │                       ▼                         │
     *  │              ┌─────────────────┐                │
     *  │              │  Frame Timing   │                │
     *  │              │   (~40ms/frame) │                │
     *  │              └────────┬────────┘                │
     *  │                       │                         │
     *  │                       └─────────────────────────│
     *  │                                                  │
     *  └──────────────────────────────────────────────────┘
     */
    
    /* Scan the matrix */
    GRID_ScanMatrix();
    
    /* Transmit the data */
    GRID_TransmitData();
    
    /* No additional delay - scanning + transmission takes ~40ms */
}
