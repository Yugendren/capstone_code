/**
 ******************************************************************************
 * @file           : grid_scan.h
 * @brief          : 12x20 Grid Scanning Engine Header (ADS1220 Version)
 * @author         : Capstone Project
 * @date           : 2026-01-13
 ******************************************************************************
 *
 *                    SYSTEM ARCHITECTURE
 *    ┌─────────────────────────────────────────────────────────────────┐
 *    │                                                                 │
 *    │   12 ROWS (GPIO PC0-PC11)          20 COLUMNS (5x ADS1220)     │
 *    │   ═══════════════════════          ══════════════════════       │
 *    │                                                                 │
 *    │   PC0  ──────┬───┬───┬─── ... ───┬───┬──── AIN0-3 (Chip 0)     │
 *    │   PC1  ──────┼───┼───┼─── ... ───┼───┼──── AIN0-3 (Chip 1)     │
 *    │   PC2  ──────┼───┼───┼─── ... ───┼───┼──── AIN0-3 (Chip 2)     │
 *    │    ⋮         ⋮   ⋮   ⋮           ⋮   ⋮     AIN0-3 (Chip 3)     │
 *    │   PC11 ──────┴───┴───┴─── ... ───┴───┴──── AIN0-3 (Chip 4)     │
 *    │                                                                 │
 *    │   Grid: 12 rows × 20 columns = 240 sensing points              │
 *    │   Physical size: 60mm × 100mm (at 5mm spacing)                 │
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
#include "ads1220.h"

/* Exported defines ----------------------------------------------------------*/

/**
 * @defgroup GRID_DIMENSIONS Grid Dimensions
 * @{
 */
#define GRID_NUM_ROWS           12U     /**< 12 rows driven by GPIO PC0-PC11 */
#define GRID_NUM_COLS           20U     /**< 20 columns from 5x ADS1220 (4 channels each) */
#define GRID_TOTAL_NODES        (GRID_NUM_ROWS * GRID_NUM_COLS)  /**< 240 */
/** @} */

/**
 * @defgroup BINARY_PROTOCOL Binary Protocol Constants
 * @{
 */
#define PACKET_SYNC_BYTE_1      0xAAU
#define PACKET_SYNC_BYTE_2      0x55U
#define PACKET_HEADER_SIZE      2U
#define PACKET_PAYLOAD_SIZE     (GRID_TOTAL_NODES * 2U)  /**< 240 x 2 = 480 bytes */
#define PACKET_FOOTER_SIZE      4U
#define PACKET_TOTAL_SIZE       (PACKET_HEADER_SIZE + PACKET_PAYLOAD_SIZE + PACKET_FOOTER_SIZE)  /**< 486 bytes */
/** @} */

/**
 * @defgroup ROW_GPIO Row GPIO Configuration
 * @brief Using GPIOC for 12 row drivers
 * @{
 */
#define ROW_GPIO_PORT           GPIOC
#define ROW_GPIO_PINS           0x0FFFU  /**< PC0-PC11 (12 bits) */
/** @} */

/**
 * @defgroup ADC_PROCESSING ADC Processing
 * @{
 */
#define ADC_MAX_VALUE           0xFFFFFFU  /**< 24-bit max */
#define ADC_NOISE_THRESHOLD     5000U      /**< Noise floor threshold */
#define ADC_SCALE_SHIFT         8U         /**< Shift 24-bit to 16-bit (>> 8) */
/** @} */

/* Exported types ------------------------------------------------------------*/

typedef enum {
    GRID_STATE_IDLE = 0,
    GRID_STATE_SCANNING,
    GRID_STATE_TRANSMITTING,
    GRID_STATE_CALIBRATING
} GridState_t;

typedef struct {
    uint16_t data[GRID_NUM_ROWS][GRID_NUM_COLS];  /**< 16-bit scaled values */
    uint32_t baseline[GRID_NUM_ROWS][GRID_NUM_COLS]; /**< 24-bit baseline */
    GridState_t state;
    uint32_t frameCount;
    uint32_t lastScanTimeMs;
} GridData_t;

/* Exported variables --------------------------------------------------------*/

extern GridData_t g_GridData;

/* Exported functions --------------------------------------------------------*/

/**
 * @brief  Initialize the grid scanning system
 * @param  hspi: Pointer to SPI handle for ADS1220 communication (not used if using internal ADCs)
 * @param  huart: Pointer to UART handle for data streaming
 */
void GRID_Init(SPI_HandleTypeDef *hspi, UART_HandleTypeDef *huart);

/**
 * @brief  Perform baseline calibration
 */
void GRID_Calibrate(void);

/**
 * @brief  Scan the entire 12x20 grid once
 */
void GRID_ScanMatrix(void);

/**
 * @brief  Transmit grid data over UART
 */
void GRID_TransmitData(void);

/**
 * @brief  Main scan loop (scan + transmit)
 */
void GRID_ScanLoop(void);

/**
 * @brief  Enable a specific row (set GPIO high)
 * @param  row: Row index (0-11)
 */
void GRID_EnableRow(uint8_t row);

/**
 * @brief  Disable all rows (set all GPIO low)
 */
void GRID_DisableAllRows(void);

#ifdef __cplusplus
}
#endif

#endif /* __GRID_SCAN_H */
