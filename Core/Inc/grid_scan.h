/**
 ******************************************************************************
 * @file           : grid_scan.h
 * @brief          : 40x40 Grid Scanning Engine Header
 * @author         : Capstone Project
 * @date           : 2026-01-12
 ******************************************************************************
 * @attention
 *
 * This file provides the interface for scanning the 40x40 piezoelectric
 * force sensing grid and streaming data over UART in binary format.
 *
 ******************************************************************************
 *
 *                    SCANNING ALGORITHM
 *    ┌─────────────────────────────────────────────────────────────────┐
 *    │                                                                 │
 *    │   FOR each row (0 to 39):                                      │
 *    │     1. Enable row mux, select row channel                       │
 *    │     2. Drive PA1 HIGH (activate row)                           │
 *    │     3. Short settling delay                                    │
 *    │     4. FOR each column (0 to 39):                              │
 *    │        a. Enable col mux, select col channel                   │
 *    │        b. Short settling delay                                 │
 *    │        c. Read ADC value from PA0                              │
 *    │        d. Store in matrix[row][col]                            │
 *    │     5. Drive PA1 LOW (deactivate row)                          │
 *    │   END FOR                                                       │
 *    │                                                                 │
 *    │   Stream binary data packet over UART                          │
 *    │                                                                 │
 *    └─────────────────────────────────────────────────────────────────┘
 *
 ******************************************************************************
 *
 *                    BINARY DATA PROTOCOL
 *    ┌─────────────────────────────────────────────────────────────────┐
 *    │                                                                 │
 *    │   PACKET STRUCTURE (total: 3206 bytes per frame)               │
 *    │   ┌──────────┬───────────────────────────┬──────────┐          │
 *    │   │  HEADER  │         PAYLOAD           │  FOOTER  │          │
 *    │   │ (2 bytes)│       (3200 bytes)        │ (4 bytes)│          │
 *    │   └──────────┴───────────────────────────┴──────────┘          │
 *    │                                                                 │
 *    │   HEADER:  0xAA 0x55 (sync bytes)                              │
 *    │   PAYLOAD: 1600 x 16-bit values (little-endian)                │
 *    │            Row 0: [col0_L, col0_H, col1_L, col1_H, ...]       │
 *    │            Row 1: [col0_L, col0_H, col1_L, col1_H, ...]       │
 *    │            ...                                                 │
 *    │   FOOTER:  16-bit checksum (sum of all payload bytes)          │
 *    │            0x0D 0x0A (CR LF)                                   │
 *    │                                                                 │
 *    └─────────────────────────────────────────────────────────────────┘
 *
 ******************************************************************************
 */

#ifndef __GRID_SCAN_H
#define __GRID_SCAN_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "grid_mux.h"

/* Exported defines ----------------------------------------------------------*/

/**
 * @defgroup SCAN_TIMING Scan Timing Parameters
 * @brief    Delays and timing for stable ADC readings
 * @{
 */
#define SCAN_ROW_SETTLE_US      5U      /**< Microseconds to wait after row select */
#define SCAN_COL_SETTLE_US      2U      /**< Microseconds to wait after col select */
#define SCAN_ADC_SAMPLES        4U      /**< Number of ADC samples to average */
/** @} */

/**
 * @defgroup BINARY_PROTOCOL Binary Protocol Constants
 * @brief    Sync bytes and packet structure
 * @{
 */
#define PACKET_SYNC_BYTE_1      0xAAU   /**< First sync byte */
#define PACKET_SYNC_BYTE_2      0x55U   /**< Second sync byte */
#define PACKET_HEADER_SIZE      2U      /**< Header: 2 sync bytes */
#define PACKET_PAYLOAD_SIZE     (GRID_TOTAL_NODES * 2U)  /**< 1600 x 2 bytes = 3200 */
#define PACKET_FOOTER_SIZE      4U      /**< 2-byte checksum + CR + LF */
#define PACKET_TOTAL_SIZE       (PACKET_HEADER_SIZE + PACKET_PAYLOAD_SIZE + PACKET_FOOTER_SIZE)
/** @} */

/**
 * @defgroup ADC_PROCESSING ADC Value Processing
 * @brief    ADC inversion for pressure representation
 *
 *           Raw ADC: 4095 = no pressure, 0 = max pressure
 *           After inversion: 0 = no pressure, 4095 = max pressure
 * @{
 */
#define ADC_MAX_VALUE           4095U   /**< 12-bit ADC maximum */
#define ADC_NOISE_THRESHOLD     50U     /**< Values below this are zeroed */
/** @} */

/* Exported types ------------------------------------------------------------*/

/**
 * @brief  Grid scan state enumeration
 */
typedef enum {
    GRID_STATE_IDLE = 0,        /**< Not scanning */
    GRID_STATE_SCANNING,        /**< Currently scanning matrix */
    GRID_STATE_TRANSMITTING,    /**< Transmitting data */
    GRID_STATE_CALIBRATING      /**< In calibration mode */
} GridState_t;

/**
 * @brief  Grid data structure
 */
typedef struct {
    uint16_t data[GRID_NUM_ROWS][GRID_NUM_COLS];  /**< Pressure values (0-4095) */
    uint16_t baseline[GRID_NUM_ROWS][GRID_NUM_COLS]; /**< Calibration baseline */
    GridState_t state;          /**< Current state */
    uint32_t frameCount;        /**< Number of frames scanned */
    uint32_t lastScanTimeMs;    /**< Timestamp of last scan */
} GridData_t;

/* Exported variables --------------------------------------------------------*/

extern GridData_t g_GridData;

/* Exported functions --------------------------------------------------------*/

/**
 * @brief  Initialize the grid scanning system
 * @param  hadc: Pointer to ADC handle (ADC1)
 * @param  huart: Pointer to UART handle (UART2)
 * @note   Call this after all HAL peripheral init functions
 * @retval None
 */
void GRID_Init(ADC_HandleTypeDef *hadc, UART_HandleTypeDef *huart);

/**
 * @brief  Perform calibration (capture baseline when no pressure applied)
 * @note   User should NOT touch the grid during calibration
 *         Averages multiple scans to establish baseline
 * @retval None
 */
void GRID_Calibrate(void);

/**
 * @brief  Scan the entire 40x40 grid once
 * @note   Results stored in g_GridData.data[][]
 *         Values are inverted (0=no pressure, 4095=max pressure)
 *         Baseline subtraction applied if calibrated
 * @retval None
 */
void GRID_ScanMatrix(void);

/**
 * @brief  Read a single cell value
 * @param  row: Row index (0-39)
 * @param  col: Column index (0-39)
 * @retval Pressure value (0-4095) after processing
 */
uint16_t GRID_ReadCell(uint8_t row, uint8_t col);

/**
 * @brief  Transmit grid data over UART in binary format
 * @note   Uses the binary protocol defined above
 *         Blocking call - waits for transmission complete
 * @retval None
 */
void GRID_TransmitData(void);

/**
 * @brief  Main scan loop - call this repeatedly in main while(1)
 * @note   Performs one complete scan cycle:
 *         1. Scan entire matrix
 *         2. Transmit data
 *         3. Wait for next frame timing
 * @retval None
 */
void GRID_ScanLoop(void);

/**
 * @brief  Microsecond delay using DWT cycle counter
 * @param  us: Microseconds to delay
 * @note   More precise than HAL_Delay for short delays
 * @retval None
 */
void GRID_DelayUs(uint32_t us);

#ifdef __cplusplus
}
#endif

#endif /* __GRID_SCAN_H */
