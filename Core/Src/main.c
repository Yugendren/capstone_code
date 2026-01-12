/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : 40x40 Piezoelectric Force Sensing Grid - Main Program
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2025 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  *
  *                    SYSTEM OVERVIEW
  *    ┌───────────────────────────────────────────────────────────┐
  *    │                                                           │
  *    │   40×40 Velostat Grid (200×200mm, 5mm copper strips)     │
  *    │          ↓                           ↓                    │
  *    │   5× CD4051 (Rows)            5× CD4051 (Cols)           │
  *    │          ↓                           ↓                    │
  *    │   PA1 (Row Drive)              PA0 (ADC Input)           │
  *    │                    ↓                                      │
  *    │              STM32F303RE                                  │
  *    │                    ↓                                      │
  *    │              UART2 (Binary)                              │
  *    │                    ↓                                      │
  *    │              Python GUI                                   │
  *    │                                                           │
  *    └───────────────────────────────────────────────────────────┘
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include <stdio.h>
#include "grid_mux.h"
#include "grid_scan.h"

/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/**
 *  @brief  40×40 Grid Scanning System
 *  
 *  This replaces the old 2×2 direct ADC/GPIO approach with
 *  multiplexed scanning for 1600 sensing points.
 *  
 *  Pin Configuration:
 *    - PB0, PB1, PB2: Mux select (S0, S1, S2)
 *    - PC0-PC4: Row mux enables
 *    - PC5-PC9: Col mux enables
 *    - PA0: ADC input (through col muxes)
 *    - PA1: Row drive output (through row muxes)
 */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
ADC_HandleTypeDef hadc1;
ADC_HandleTypeDef hadc2;
ADC_HandleTypeDef hadc3;
ADC_HandleTypeDef hadc4;

UART_HandleTypeDef huart2;

/* USER CODE BEGIN PV */

/**
 * @brief  Flag to enable/disable calibration on startup
 *         Set to 1 to calibrate, 0 to skip
 */
static uint8_t g_DoCalibration = 0;

/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_USART2_UART_Init(void);
static void MX_ADC1_Init(void);
static void MX_ADC2_Init(void);
static void MX_ADC3_Init(void);
static void MX_ADC4_Init(void);
/* USER CODE BEGIN PFP */

/**
 * @brief  Retarget printf to UART2
 */
int __io_putchar(int ch);

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/**
 *  ============================================================================
 *  40×40 GRID SCANNING SYSTEM
 *  ============================================================================
 *  
 *  Replaces the old 2×2 direct ADC scanning with multiplexed 40×40 grid.
 *  
 *  MAIN LOOP OPERATION:
 *  ┌─────────────────────────────────────────────────────────────┐
 *  │                                                             │
 *  │   ┌───────────┐      ┌──────────────┐     ┌────────────┐   │
 *  │   │  GRID_    │ ───► │  GRID_       │ ──► │  ~25 Hz    │   │
 *  │   │  ScanMatrix│      │  TransmitData│     │  Loop      │   │
 *  │   │  (1600     │      │  (Binary     │     │  Rate      │   │
 *  │   │   cells)   │      │   3206 bytes)│     │            │   │
 *  │   └───────────┘      └──────────────┘     └────────────┘   │
 *  │                                                             │
 *  └─────────────────────────────────────────────────────────────┘
 *  
 *  BINARY PROTOCOL:
 *    Header:  0xAA 0x55 (2 bytes)
 *    Payload: 1600 × 16-bit values, little-endian (3200 bytes)
 *    Footer:  Checksum (2 bytes) + CR LF (2 bytes)
 *    Total:   3206 bytes per frame
 *  
 */

/**
 * @brief  Retarget printf to UART2 for debug messages
 * @param  ch: Character to transmit
 * @retval Character transmitted
 */
int __io_putchar(int ch)
{
    HAL_UART_Transmit(&huart2, (uint8_t *)&ch, 1, HAL_MAX_DELAY);
    return ch;
}

/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{
  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_USART2_UART_Init();
  MX_ADC1_Init();
  MX_ADC2_Init();
  MX_ADC3_Init();
  MX_ADC4_Init();
  /* USER CODE BEGIN 2 */
  
  /*
   *  ════════════════════════════════════════════════════════════════════
   *  INITIALIZATION SEQUENCE FOR 40×40 GRID
   *  ════════════════════════════════════════════════════════════════════
   *  
   *   Step 1: Print startup banner
   *   Step 2: Initialize grid scanning system
   *   Step 3: Optional calibration (if g_DoCalibration = 1)
   *   Step 4: Enter main scanning loop
   *  
   */
  
  /* Print startup banner */
  printf("\r\n");
  printf("============================================\r\n");
  printf("  40x40 Piezoelectric Force Sensing Grid   \r\n");
  printf("  Physiotherapy Training System            \r\n");
  printf("============================================\r\n");
  printf("  Grid Size:   40 rows x 40 columns        \r\n");
  printf("  Resolution:  1600 sensing nodes          \r\n");
  printf("  Coverage:    200mm x 200mm               \r\n");
  printf("  Protocol:    Binary (3206 bytes/frame)   \r\n");
  printf("============================================\r\n");
  printf("\r\n");
  
  /* Initialize the grid scanning system */
  printf("[INIT] Initializing grid scanning system...\r\n");
  GRID_Init(&hadc1, &huart2);
  printf("[INIT] Grid system initialized.\r\n");
  
  /* Optional: Perform calibration */
  if (g_DoCalibration) {
      printf("[CALIB] Starting calibration - DO NOT TOUCH THE GRID!\r\n");
      HAL_Delay(2000);  /* Give user time to release */
      GRID_Calibrate();
      printf("[CALIB] Calibration complete.\r\n");
  } else {
      printf("[INFO] Skipping calibration (g_DoCalibration = 0)\r\n");
  }
  
  printf("\r\n[RUN] Starting main scan loop...\r\n");
  HAL_Delay(500);
  
  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  /* USER CODE BEGIN WHILE */
//  while (1) {
////	  calibrate_row(0);  // <-- choose which row you want to test
//
////      scan_matrix();
////      HAL_Delay(200);
//      term_clear();
//      printf("=== 4 x 8 Matrix ===\r\n");
//
//      for (int row = 0; row < 8; row++) {
//          // --- select row ---
//          // if your rows are tied directly to ADC2/3/4 channels,
//          // you might instead *drive* row via GPIO and *read* columns here.
//          // For now: assume rows = 8 ADC channels total.
//
//          uint32_t c0 = read_adc(&hadc1, ADC_CHANNEL_1); // PA0
//          uint32_t c1 = read_adc(&hadc1, ADC_CHANNEL_2); // PA1
//          uint32_t c2 = read_adc(&hadc1, ADC_CHANNEL_6); // PC0
//          uint32_t c3 = read_adc(&hadc1, ADC_CHANNEL_7); // PC1
//
//          // You’ll need to adjust which ADC/channel corresponds to row X.
//          // Example placeholders:
//          uint32_t row_val;
//          if (row < 2) row_val = read_adc(&hadc2, row==0 ? ADC_CHANNEL_1 : ADC_CHANNEL_2);
//          else if (row < 4) row_val = read_adc(&hadc3, (row==2)? ADC_CHANNEL_1 : ADC_CHANNEL_2);
//          else row_val = read_adc(&hadc4, (row==4)? ADC_CHANNEL_1 :
//                                             (row==5)? ADC_CHANNEL_2 :
//                                             (row==6)? ADC_CHANNEL_3 : ADC_CHANNEL_4);
//
//          // --- print row ---
//          printf("R%d | %4lu %4lu %4lu %4lu  (rowADC=%lu)\r\n",
//                 row, c0, c1, c2, c3, row_val);
//      }
//
//      HAL_Delay(200);
//  }
  /* USER CODE BEGIN WHILE */
//  while (1)
//  {
//    // --- NEW 2x2 DATA STREAMING CODE ---
//    uint32_t raw_matrix[2][2];
//    uint32_t pressure_matrix[2][2];
//
//    // === Step 1: Scan Row 0 (PC1) ===
//    HAL_GPIO_WritePin(ROW_DRIVE_1_GPIO_Port, ROW_DRIVE_1_Pin, GPIO_PIN_SET); // Deactivate Row 1 (PC0)
//    HAL_GPIO_WritePin(ROW_DRIVE_0_GPIO_Port, ROW_DRIVE_0_Pin, GPIO_PIN_RESET); // Activate Row 0 (PC1)
//    HAL_Delay(1);
//
//    raw_matrix[0][0] = read_adc(&hadc1, ADC_CHANNEL_1); // Read (Row 0, Col 0) -> PA0
//    raw_matrix[0][1] = read_adc(&hadc1, ADC_CHANNEL_2); // Read (Row 0, Col 1) -> PA1
//
//    // === Step 2: Scan Row 1 (PC0) ===
//    HAL_GPIO_WritePin(ROW_DRIVE_0_GPIO_Port, ROW_DRIVE_0_Pin, GPIO_PIN_SET); // Deactivate Row 0 (PC1)
//    HAL_GPIO_WritePin(ROW_DRIVE_1_GPIO_Port, ROW_DRIVE_1_Pin, GPIO_PIN_RESET); // Activate Row 1 (PC0)
//    HAL_Delay(1);
//
//    raw_matrix[1][0] = read_adc(&hadc1, ADC_CHANNEL_1); // Read (Row 1, Col 0) -> PA0
//    raw_matrix[1][1] = read_adc(&hadc1, ADC_CHANNEL_2); // Read (Row 1, Col 1) -> PA1
//
//    // === Step 3: Deactivate all rows ===
//    HAL_GPIO_WritePin(ROW_DRIVE_0_GPIO_Port, ROW_DRIVE_0_Pin, GPIO_PIN_SET);
//    HAL_GPIO_WritePin(ROW_DRIVE_1_GPIO_Port, ROW_DRIVE_1_Pin, GPIO_PIN_SET);
//
//    // === Step 4: Process and Print Clean Data ===
//
//    // "Flip" the values to get pressure
//    pressure_matrix[0][0] = (raw_matrix[0][0] > 4050) ? 0 : (4095 - raw_matrix[0][0]);
//    pressure_matrix[0][1] = (raw_matrix[0][1] > 4050) ? 0 : (4095 - raw_matrix[0][1]);
//    pressure_matrix[1][0] = (raw_matrix[1][0] > 4050) ? 0 : (4095 - raw_matrix[1][0]);
//    pressure_matrix[1][1] = (raw_matrix[1][1] > 4050) ? 0 : (4095 - raw_matrix[1][1]);
//
//    // Print all 4 values on one line, separated by commas.
//    // This is the *only* thing you should print.
//    printf("%lu,%lu,%lu,%lu\n",
//           pressure_matrix[0][0],
//           pressure_matrix[0][1],
//           pressure_matrix[1][0],
//           pressure_matrix[1][1]
//    );
//
//    HAL_Delay(50); // Send data ~20 times per second
//
//    // --- END NEW CODE ---
//    /* USER CODE END WHILE */
//
//    /* USER CODE BEGIN 3 */
//  }
  /* USER CODE BEGIN WHILE */
  //OLD PYTHON
//    while (1)
//    {
//      // --- NEW 2x2 DATA STREAMING CODE ---
//      uint32_t raw_matrix[2][2];
//      uint32_t pressure_matrix[2][2];
//
//      // === Step 1: Scan Row 0 (PC1) ===
//      HAL_GPIO_WritePin(ROW_DRIVE_1_GPIO_Port, ROW_DRIVE_1_Pin, GPIO_PIN_SET); // Deactivate Row 1 (PC0)
//      HAL_GPIO_WritePin(ROW_DRIVE_0_GPIO_Port, ROW_DRIVE_0_Pin, GPIO_PIN_RESET); // Activate Row 0 (PC1)
//      HAL_Delay(1);
//
//      raw_matrix[0][0] = read_adc(&hadc1, ADC_CHANNEL_1); // Read (Row 0, Col 0) -> PA0
//      raw_matrix[0][1] = read_adc(&hadc1, ADC_CHANNEL_2); // Read (Row 0, Col 1) -> PA1
//
//      // === Step 2: Scan Row 1 (PC0) ===
//      HAL_GPIO_WritePin(ROW_DRIVE_0_GPIO_Port, ROW_DRIVE_0_Pin, GPIO_PIN_SET); // Deactivate Row 0 (PC1)
//      HAL_GPIO_WritePin(ROW_DRIVE_1_GPIO_Port, ROW_DRIVE_1_Pin, GPIO_PIN_RESET); // Activate Row 1 (PC0)
//      HAL_Delay(1);
//
//      raw_matrix[1][0] = read_adc(&hadc1, ADC_CHANNEL_1); // Read (Row 1, Col 0) -> PA0
//      raw_matrix[1][1] = read_adc(&hadc1, ADC_CHANNEL_2); // Read (Row 1, Col 1) -> PA1
//
//      // === Step 3: Deactivate all rows ===
//      HAL_GPIO_WritePin(ROW_DRIVE_0_GPIO_Port, ROW_DRIVE_0_Pin, GPIO_PIN_SET);
//      HAL_GPIO_WritePin(ROW_DRIVE_1_GPIO_Port, ROW_DRIVE_1_Pin, GPIO_PIN_SET);
//
//      // === Step 4: Process and Print Clean Data ===
//
//      // "Flip" the values to get pressure
//      pressure_matrix[0][0] = (raw_matrix[0][0] > 4050) ? 0 : (4095 - raw_matrix[0][0]);
//      pressure_matrix[0][1] = (raw_matrix[0][1] > 4050) ? 0 : (4095 - raw_matrix[0][1]);
//      pressure_matrix[1][0] = (raw_matrix[1][0] > 4050) ? 0 : (4095 - raw_matrix[1][0]);
//      pressure_matrix[1][1] = (raw_matrix[1][1] > 4050) ? 0 : (4095 - raw_matrix[1][1]);
//
//      // Print all 4 values on one line, separated by commas.
//      // This is the *only* thing you should print.
//      printf("%lu,%lu,%lu,%lu\n",
//             pressure_matrix[0][0],
//             pressure_matrix[0][1],
//             pressure_matrix[1][0],
//             pressure_matrix[1][1]
//      );
//
//      HAL_Delay(50); // Send data ~20 times per second
//
//      // --- END NEW CODE ---
//      /* USER CODE END WHILE */
//
//      /* USER CODE BEGIN 3 */
//    }
    /* USER CODE END 3 */
    /* USER CODE BEGIN WHILE */
  /* USER CODE BEGIN WHILE */
    while (1)
    {
      /*
       *  ═══════════════════════════════════════════════════════════
       *  MAIN SCAN LOOP - 40×40 GRID
       *  ═══════════════════════════════════════════════════════════
       *  
       *  This loop:
       *    1. Scans all 1600 cells (40 rows × 40 columns)
       *    2. Transmits binary data packet (3206 bytes)
       *    3. Repeats at ~25 Hz
       *  
       *  The scanning and transmission are handled by GRID_ScanLoop()
       *  which calls GRID_ScanMatrix() and GRID_TransmitData().
       *  
       */
      
      /* Execute one complete scan + transmit cycle */
      GRID_ScanLoop();
      
      /* 
       * Toggle LED to show activity (optional)
       * HAL_GPIO_TogglePin(LD2_GPIO_Port, LD2_Pin);
       */
      
      /* USER CODE END WHILE */

      /* USER CODE BEGIN 3 */
    }
    /* USER CODE END 3 */
// HUMAN READABLE
//    while (1)
//    {
//      // --- NEW 2x2 MATRIX SCAN CODE ---
//      uint32_t raw_matrix[2][2];
//      uint32_t pressure_matrix[2][2];
//
//      // === Step 1: Scan Row 0 (PC1) ===
//      HAL_GPIO_WritePin(ROW_DRIVE_1_GPIO_Port, ROW_DRIVE_1_Pin, GPIO_PIN_SET); // Deactivate Row 1 (PC0)
//      HAL_GPIO_WritePin(ROW_DRIVE_0_GPIO_Port, ROW_DRIVE_0_Pin, GPIO_PIN_RESET); // Activate Row 0 (PC1)
//      HAL_Delay(1); // Short delay for voltages to settle
//
//      raw_matrix[0][0] = read_adc(&hadc1, ADC_CHANNEL_1); // Read (Row 0, Col 0) -> PA0
//      raw_matrix[0][1] = read_adc(&hadc1, ADC_CHANNEL_2); // Read (Row 0, Col 1) -> PA1
//
//      // === Step 2: Scan Row 1 (PC0) ===
//      HAL_GPIO_WritePin(ROW_DRIVE_0_GPIO_Port, ROW_DRIVE_0_Pin, GPIO_PIN_SET); // Deactivate Row 0 (PC1)
//      HAL_GPIO_WritePin(ROW_DRIVE_1_GPIO_Port, ROW_DRIVE_1_Pin, GPIO_PIN_RESET); // Activate Row 1 (PC0)
//      HAL_Delay(1); // Short delay
//
//      raw_matrix[1][0] = read_adc(&hadc1, ADC_CHANNEL_1); // Read (Row 1, Col 0) -> PA0
//      raw_matrix[1][1] = read_adc(&hadc1, ADC_CHANNEL_2); // Read (Row 1, Col 1) -> PA1
//
//      // === Step 3: Deactivate all rows ===
//      HAL_GPIO_WritePin(ROW_DRIVE_0_GPIO_Port, ROW_DRIVE_0_Pin, GPIO_PIN_SET); // Deactivate Row 0
//      HAL_GPIO_WritePin(ROW_DRIVE_1_GPIO_Port, ROW_DRIVE_1_Pin, GPIO_PIN_SET); // Deactivate Row 1
//
//
//      // === Step 4: Process and Print the Values ===
//      term_clear();
//      printf("2x2 Matrix Read Test:\r\n");
//      printf("---------------------\r\n");
//
//      for (int r = 0; r < 2; r++) {
//        for (int c = 0; c < 2; c++) {
//          // "Flip" the value. 4095 (no press) becomes 0.
//          pressure_matrix[r][c] = (raw_matrix[r][c] > 4050) ? 0 : (4095 - raw_matrix[r][c]);
//
//          // Print the processed pressure value
//          printf("%5lu ", pressure_matrix[r][c]);
//        }
//        printf("\r\n"); // New line after each row
//      }
//
//      printf("\r\nRaw ADC Values:\r\n");
//      printf("%5lu %5lu\r\n", raw_matrix[0][0], raw_matrix[0][1]);
//      printf("%5lu %5lu\r\n", raw_matrix[1][0], raw_matrix[1][1]);
//
//
//      HAL_Delay(100); // 100ms delay for readability
//
//      // --- END NEW CODE ---
//      /* USER CODE END WHILE */
//
//      /* USER CODE BEGIN 3 */
//    }
    /* USER CODE END 3 */
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};
  RCC_PeriphCLKInitTypeDef PeriphClkInit = {0};

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSI;
  RCC_OscInitStruct.PLL.PLLMUL = RCC_PLL_MUL9;
  RCC_OscInitStruct.PLL.PREDIV = RCC_PREDIV_DIV1;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK)
  {
    Error_Handler();
  }
  PeriphClkInit.PeriphClockSelection = RCC_PERIPHCLK_USART2|RCC_PERIPHCLK_ADC12
                              |RCC_PERIPHCLK_ADC34;
  PeriphClkInit.Usart2ClockSelection = RCC_USART2CLKSOURCE_PCLK1;
  PeriphClkInit.Adc12ClockSelection = RCC_ADC12PLLCLK_DIV1;
  PeriphClkInit.Adc34ClockSelection = RCC_ADC34PLLCLK_DIV1;
  if (HAL_RCCEx_PeriphCLKConfig(&PeriphClkInit) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief ADC1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_ADC1_Init(void)
{

  /* USER CODE BEGIN ADC1_Init 0 */

  /* USER CODE END ADC1_Init 0 */

  ADC_MultiModeTypeDef multimode = {0};
  ADC_ChannelConfTypeDef sConfig = {0};

  /* USER CODE BEGIN ADC1_Init 1 */

  /* USER CODE END ADC1_Init 1 */

  /** Common config
  */
  hadc1.Instance = ADC1;
  hadc1.Init.ClockPrescaler = ADC_CLOCK_ASYNC_DIV1;
  hadc1.Init.Resolution = ADC_RESOLUTION_12B;
  hadc1.Init.ScanConvMode = ADC_SCAN_DISABLE;
  hadc1.Init.ContinuousConvMode = ENABLE;
  hadc1.Init.DiscontinuousConvMode = DISABLE;
  hadc1.Init.ExternalTrigConvEdge = ADC_EXTERNALTRIGCONVEDGE_NONE;
  hadc1.Init.ExternalTrigConv = ADC_SOFTWARE_START;
  hadc1.Init.DataAlign = ADC_DATAALIGN_RIGHT;
  hadc1.Init.NbrOfConversion = 1;
  hadc1.Init.DMAContinuousRequests = DISABLE;
  hadc1.Init.EOCSelection = ADC_EOC_SINGLE_CONV;
  hadc1.Init.LowPowerAutoWait = DISABLE;
  hadc1.Init.Overrun = ADC_OVR_DATA_OVERWRITTEN;
  if (HAL_ADC_Init(&hadc1) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure the ADC multi-mode
  */
  multimode.Mode = ADC_MODE_INDEPENDENT;
  if (HAL_ADCEx_MultiModeConfigChannel(&hadc1, &multimode) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure Regular Channel
  */
  sConfig.Channel = ADC_CHANNEL_1;
  sConfig.Rank = ADC_REGULAR_RANK_1;
  sConfig.SingleDiff = ADC_SINGLE_ENDED;
  sConfig.SamplingTime = ADC_SAMPLETIME_1CYCLE_5;
  sConfig.OffsetNumber = ADC_OFFSET_NONE;
  sConfig.Offset = 0;
  if (HAL_ADC_ConfigChannel(&hadc1, &sConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN ADC1_Init 2 */

  /* USER CODE END ADC1_Init 2 */

}

/**
  * @brief ADC2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_ADC2_Init(void)
{

  /* USER CODE BEGIN ADC2_Init 0 */

  /* USER CODE END ADC2_Init 0 */

  ADC_ChannelConfTypeDef sConfig = {0};

  /* USER CODE BEGIN ADC2_Init 1 */

  /* USER CODE END ADC2_Init 1 */

  /** Common config
  */
  hadc2.Instance = ADC2;
  hadc2.Init.ClockPrescaler = ADC_CLOCK_ASYNC_DIV1;
  hadc2.Init.Resolution = ADC_RESOLUTION_12B;
  hadc2.Init.ScanConvMode = ADC_SCAN_DISABLE;
  hadc2.Init.ContinuousConvMode = DISABLE;
  hadc2.Init.DiscontinuousConvMode = DISABLE;
  hadc2.Init.ExternalTrigConvEdge = ADC_EXTERNALTRIGCONVEDGE_NONE;
  hadc2.Init.ExternalTrigConv = ADC_SOFTWARE_START;
  hadc2.Init.DataAlign = ADC_DATAALIGN_RIGHT;
  hadc2.Init.NbrOfConversion = 1;
  hadc2.Init.DMAContinuousRequests = DISABLE;
  hadc2.Init.EOCSelection = ADC_EOC_SINGLE_CONV;
  hadc2.Init.LowPowerAutoWait = DISABLE;
  hadc2.Init.Overrun = ADC_OVR_DATA_OVERWRITTEN;
  if (HAL_ADC_Init(&hadc2) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure Regular Channel
  */
  sConfig.Channel = ADC_CHANNEL_1;
  sConfig.Rank = ADC_REGULAR_RANK_1;
  sConfig.SingleDiff = ADC_SINGLE_ENDED;
  sConfig.SamplingTime = ADC_SAMPLETIME_1CYCLE_5;
  sConfig.OffsetNumber = ADC_OFFSET_NONE;
  sConfig.Offset = 0;
  if (HAL_ADC_ConfigChannel(&hadc2, &sConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN ADC2_Init 2 */

  /* USER CODE END ADC2_Init 2 */

}

/**
  * @brief ADC3 Initialization Function
  * @param None
  * @retval None
  */
static void MX_ADC3_Init(void)
{

  /* USER CODE BEGIN ADC3_Init 0 */

  /* USER CODE END ADC3_Init 0 */

  ADC_MultiModeTypeDef multimode = {0};
  ADC_ChannelConfTypeDef sConfig = {0};

  /* USER CODE BEGIN ADC3_Init 1 */

  /* USER CODE END ADC3_Init 1 */

  /** Common config
  */
  hadc3.Instance = ADC3;
  hadc3.Init.ClockPrescaler = ADC_CLOCK_ASYNC_DIV1;
  hadc3.Init.Resolution = ADC_RESOLUTION_12B;
  hadc3.Init.ScanConvMode = ADC_SCAN_DISABLE;
  hadc3.Init.ContinuousConvMode = DISABLE;
  hadc3.Init.DiscontinuousConvMode = DISABLE;
  hadc3.Init.ExternalTrigConvEdge = ADC_EXTERNALTRIGCONVEDGE_NONE;
  hadc3.Init.ExternalTrigConv = ADC_SOFTWARE_START;
  hadc3.Init.DataAlign = ADC_DATAALIGN_RIGHT;
  hadc3.Init.NbrOfConversion = 1;
  hadc3.Init.DMAContinuousRequests = DISABLE;
  hadc3.Init.EOCSelection = ADC_EOC_SINGLE_CONV;
  hadc3.Init.LowPowerAutoWait = DISABLE;
  hadc3.Init.Overrun = ADC_OVR_DATA_OVERWRITTEN;
  if (HAL_ADC_Init(&hadc3) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure the ADC multi-mode
  */
  multimode.Mode = ADC_MODE_INDEPENDENT;
  if (HAL_ADCEx_MultiModeConfigChannel(&hadc3, &multimode) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure Regular Channel
  */
  sConfig.Channel = ADC_CHANNEL_1;
  sConfig.Rank = ADC_REGULAR_RANK_1;
  sConfig.SingleDiff = ADC_SINGLE_ENDED;
  sConfig.SamplingTime = ADC_SAMPLETIME_1CYCLE_5;
  sConfig.OffsetNumber = ADC_OFFSET_NONE;
  sConfig.Offset = 0;
  if (HAL_ADC_ConfigChannel(&hadc3, &sConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN ADC3_Init 2 */

  /* USER CODE END ADC3_Init 2 */

}

/**
  * @brief ADC4 Initialization Function
  * @param None
  * @retval None
  */
static void MX_ADC4_Init(void)
{

  /* USER CODE BEGIN ADC4_Init 0 */

  /* USER CODE END ADC4_Init 0 */

  ADC_ChannelConfTypeDef sConfig = {0};

  /* USER CODE BEGIN ADC4_Init 1 */

  /* USER CODE END ADC4_Init 1 */

  /** Common config
  */
  hadc4.Instance = ADC4;
  hadc4.Init.ClockPrescaler = ADC_CLOCK_ASYNC_DIV1;
  hadc4.Init.Resolution = ADC_RESOLUTION_12B;
  hadc4.Init.ScanConvMode = ADC_SCAN_DISABLE;
  hadc4.Init.ContinuousConvMode = DISABLE;
  hadc4.Init.DiscontinuousConvMode = DISABLE;
  hadc4.Init.ExternalTrigConvEdge = ADC_EXTERNALTRIGCONVEDGE_NONE;
  hadc4.Init.ExternalTrigConv = ADC_SOFTWARE_START;
  hadc4.Init.DataAlign = ADC_DATAALIGN_RIGHT;
  hadc4.Init.NbrOfConversion = 1;
  hadc4.Init.DMAContinuousRequests = DISABLE;
  hadc4.Init.EOCSelection = ADC_EOC_SINGLE_CONV;
  hadc4.Init.LowPowerAutoWait = DISABLE;
  hadc4.Init.Overrun = ADC_OVR_DATA_OVERWRITTEN;
  if (HAL_ADC_Init(&hadc4) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure Regular Channel
  */
  sConfig.Channel = ADC_CHANNEL_3;
  sConfig.Rank = ADC_REGULAR_RANK_1;
  sConfig.SingleDiff = ADC_SINGLE_ENDED;
  sConfig.SamplingTime = ADC_SAMPLETIME_1CYCLE_5;
  sConfig.OffsetNumber = ADC_OFFSET_NONE;
  sConfig.Offset = 0;
  if (HAL_ADC_ConfigChannel(&hadc4, &sConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN ADC4_Init 2 */

  /* USER CODE END ADC4_Init 2 */

}

/**
  * @brief USART2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_USART2_UART_Init(void)
{

  /* USER CODE BEGIN USART2_Init 0 */

  /* USER CODE END USART2_Init 0 */

  /* USER CODE BEGIN USART2_Init 1 */

  /* USER CODE END USART2_Init 1 */
  huart2.Instance = USART2;
  huart2.Init.BaudRate = 115200;
  huart2.Init.WordLength = UART_WORDLENGTH_8B;
  huart2.Init.StopBits = UART_STOPBITS_1;
  huart2.Init.Parity = UART_PARITY_NONE;
  huart2.Init.Mode = UART_MODE_TX_RX;
  huart2.Init.HwFlowCtl = UART_HWCONTROL_NONE;
  huart2.Init.OverSampling = UART_OVERSAMPLING_16;
  huart2.Init.OneBitSampling = UART_ONE_BIT_SAMPLE_DISABLE;
  huart2.AdvancedInit.AdvFeatureInit = UART_ADVFEATURE_NO_INIT;
  if (HAL_UART_Init(&huart2) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN USART2_Init 2 */

  /* USER CODE END USART2_Init 2 */

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
/* USER CODE BEGIN MX_GPIO_Init_1 */
/* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOC_CLK_ENABLE();
  __HAL_RCC_GPIOF_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(GPIOC, ROW_DRIVE_1_Pin|ROW_DRIVE_0_Pin, GPIO_PIN_RESET);

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(LD2_GPIO_Port, LD2_Pin, GPIO_PIN_RESET);

  /*Configure GPIO pin : B1_Pin */
  GPIO_InitStruct.Pin = B1_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_IT_FALLING;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(B1_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pins : ROW_DRIVE_1_Pin ROW_DRIVE_0_Pin */
  GPIO_InitStruct.Pin = ROW_DRIVE_1_Pin|ROW_DRIVE_0_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);

  /*Configure GPIO pin : LD2_Pin */
  GPIO_InitStruct.Pin = LD2_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(LD2_GPIO_Port, &GPIO_InitStruct);

/* USER CODE BEGIN MX_GPIO_Init_2 */
/* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}

#ifdef  USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
