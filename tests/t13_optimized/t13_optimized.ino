/*
 * Test 13: Optimized 40x30 Scan
 *
 * Same hardware as t12 (5x 595, 2x MUX, 40x30).
 * Performance optimizations:
 *   1. Direct GPIO register writes for MUX select
 *   2. ESP-IDF ADC oneshot driver (3-4x faster than analogRead)
 *   3. Reduced settle times
 *   4. Continuous scanning (no delay between frames)
 *   5. Binary output for maximum throughput
 *   6. Bulk serial write (single write per frame)
 *
 * Target: stable >= 60 Hz
 */

#include <SPI.h>
#include "soc/gpio_struct.h"
#include "driver/gpio.h"
#include "esp_adc/adc_oneshot.h"
#include "hal/adc_types.h"

// --- Pin definitions ---
#define RCLK_PIN  13
#define MUX_S0    4
#define MUX_S1    5
#define MUX_S2    6
#define MUX_S3    7
#define MUX1_SIG  9    // ADC1_CH8
#define MUX2_SIG  10   // ADC1_CH9

#define SPI_MOSI  11
#define SPI_SCK   12
#define SPI_MISO  -1

#define NUM_595      5
#define ROWS         40
#define COLS_PER_MUX 15
#define COLS         30
#define PRESS_THRESHOLD 500

// ADC channels for IO9 and IO10 on ESP32-S3
#define MUX1_ADC_CH  ADC_CHANNEL_8   // IO9
#define MUX2_ADC_CH  ADC_CHANNEL_9   // IO10

uint16_t grid[ROWS][COLS];
unsigned long scanTime = 0;
unsigned long frameCount = 0;
unsigned long fpsTimer = 0;
float measuredFps = 0;
bool binaryMode = true;

SPIClass *hspi = nullptr;
uint8_t rowBuf[NUM_595];

// ADC oneshot handle
adc_oneshot_unit_handle_t adc1_handle;

// Pre-computed MUX select patterns
static const uint32_t MUX_PIN_MASK = (1 << MUX_S0) | (1 << MUX_S1) | (1 << MUX_S2) | (1 << MUX_S3);
uint32_t muxPatterns[COLS_PER_MUX];

// Pre-built binary frame buffer (header + time + grid + footer)
#define FRAME_SIZE (2 + 4 + ROWS * COLS * 2 + 2)
uint8_t frameBuf[FRAME_SIZE];

void precomputeMuxPatterns() {
    for (int ch = 0; ch < COLS_PER_MUX; ch++) {
        uint32_t pattern = 0;
        if (ch & 0x01) pattern |= (1 << MUX_S0);
        if (ch & 0x02) pattern |= (1 << MUX_S1);
        if (ch & 0x04) pattern |= (1 << MUX_S2);
        if (ch & 0x08) pattern |= (1 << MUX_S3);
        muxPatterns[ch] = pattern;
    }
}

void initADC() {
    // Configure ADC1 oneshot driver
    adc_oneshot_unit_init_cfg_t init_cfg = {
        .unit_id = ADC_UNIT_1,
    };
    adc_oneshot_new_unit(&init_cfg, &adc1_handle);

    // Configure both channels — 12-bit, 11dB attenuation (0-3.3V range)
    adc_oneshot_chan_cfg_t chan_cfg = {
        .atten = ADC_ATTEN_DB_11,
        .bitwidth = ADC_BITWIDTH_12,
    };
    adc_oneshot_config_channel(adc1_handle, MUX1_ADC_CH, &chan_cfg);
    adc_oneshot_config_channel(adc1_handle, MUX2_ADC_CH, &chan_cfg);
}

void setup() {
    Serial.begin(921600);
    delay(3000);

    hspi = new SPIClass(FSPI);
    hspi->begin(SPI_SCK, SPI_MISO, SPI_MOSI, -1);

    pinMode(RCLK_PIN, OUTPUT);
    digitalWrite(RCLK_PIN, LOW);

    pinMode(MUX_S0, OUTPUT);
    pinMode(MUX_S1, OUTPUT);
    pinMode(MUX_S2, OUTPUT);
    pinMode(MUX_S3, OUTPUT);

    initADC();
    precomputeMuxPatterns();

    // Pre-fill static parts of frame buffer
    frameBuf[0] = 0xAA;
    frameBuf[1] = 0x55;
    frameBuf[FRAME_SIZE - 2] = 0xFF;
    frameBuf[FRAME_SIZE - 1] = 0xFE;

    fpsTimer = millis();

    Serial.println("\n==========================================");
    Serial.printf("ESP32-S3 Test 13: %dx%d Optimized\n", ROWS, COLS);
    Serial.println("==========================================");
    Serial.println("ADC: ESP-IDF oneshot driver (fast)");
    Serial.println("Direct register MUX select");
    Serial.println("Send 'b' for binary, 'a' for ASCII, 's' for stats\n");
}

inline void shiftOut595Fast(uint8_t *buf, int len) {
    hspi->beginTransaction(SPISettings(10000000, MSBFIRST, SPI_MODE0));
    hspi->transfer(buf, len);
    hspi->endTransaction();

    GPIO.out_w1ts = (1 << RCLK_PIN);
    GPIO.out_w1tc = (1 << RCLK_PIN);
}

inline void setRowFast(int row) {
    memset(rowBuf, 0, NUM_595);
    int chip = row / 8;
    int bit  = row % 8;
    rowBuf[NUM_595 - 1 - chip] = (1 << bit);
    shiftOut595Fast(rowBuf, NUM_595);
    delayMicroseconds(1);
}

inline void allRowsOff() {
    memset(rowBuf, 0, NUM_595);
    shiftOut595Fast(rowBuf, NUM_595);
}

inline void setMuxChannelFast(int ch) {
    GPIO.out_w1tc = MUX_PIN_MASK;
    GPIO.out_w1ts = muxPatterns[ch];
    delayMicroseconds(1);
}

void scanGrid() {
    unsigned long start = micros();
    int val1, val2;

    for (int row = 0; row < ROWS; row++) {
        setRowFast(row);

        for (int ch = 0; ch < COLS_PER_MUX; ch++) {
            setMuxChannelFast(ch);

            // ESP-IDF oneshot read — much faster than analogRead()
            adc_oneshot_read(adc1_handle, MUX1_ADC_CH, &val1);
            adc_oneshot_read(adc1_handle, MUX2_ADC_CH, &val2);
            grid[row][ch]                = val1;
            grid[row][ch + COLS_PER_MUX] = val2;
        }
    }
    allRowsOff();

    scanTime = micros() - start;
    frameCount++;

    unsigned long now = millis();
    if (now - fpsTimer >= 1000) {
        measuredFps = frameCount * 1000.0 / (now - fpsTimer);
        frameCount = 0;
        fpsTimer = now;
    }
}

void sendBinaryFrame() {
    // Pack scan time into frame buffer
    frameBuf[2] = (uint8_t)((scanTime >> 24) & 0xFF);
    frameBuf[3] = (uint8_t)((scanTime >> 16) & 0xFF);
    frameBuf[4] = (uint8_t)((scanTime >> 8) & 0xFF);
    frameBuf[5] = (uint8_t)(scanTime & 0xFF);

    // Pack grid data into frame buffer
    int offset = 6;
    for (int r = 0; r < ROWS; r++) {
        for (int c = 0; c < COLS; c++) {
            uint16_t val = grid[r][c];
            frameBuf[offset++] = (uint8_t)(val >> 8);
            frameBuf[offset++] = (uint8_t)(val & 0xFF);
        }
    }

    // Single write — much faster than many small writes
    Serial.write(frameBuf, FRAME_SIZE);
}

void sendAsciiFrame() {
    for (int row = 0; row < ROWS; row++) {
        Serial.printf("Row%d  |", row);
        for (int col = 0; col < COLS; col++) {
            int val = grid[row][col];
            char marker = (val > PRESS_THRESHOLD) ? '*' : ' ';
            Serial.printf("%4d%c|", val, marker);
        }
        Serial.println();
    }

    int pressCount = 0;
    for (int r = 0; r < ROWS; r++) {
        for (int c = 0; c < COLS; c++) {
            if (grid[r][c] > PRESS_THRESHOLD) pressCount++;
        }
    }

    float scanHz = (scanTime > 0) ? 1000000.0 / scanTime : 0;
    Serial.printf("Pressed: %d | Scan time: %lu us (%.1f Hz) | FPS: %.1f\n",
                  pressCount, scanTime, scanHz, measuredFps);
}

void printStats() {
    float scanHz = (scanTime > 0) ? 1000000.0 / scanTime : 0;
    Serial.println("\n--- Performance Stats ---");
    Serial.printf("Grid: %dx%d = %d cells\n", ROWS, COLS, ROWS * COLS);
    Serial.printf("Scan time: %lu us\n", scanTime);
    Serial.printf("Scan rate: %.1f Hz\n", scanHz);
    Serial.printf("Measured FPS: %.1f\n", measuredFps);
    Serial.printf("ADC: ESP-IDF oneshot, 12-bit\n");
    Serial.printf("SPI clock: 10 MHz\n");
    Serial.printf("Mode: %s\n", binaryMode ? "BINARY" : "ASCII");
    Serial.println("-------------------------\n");
}

void checkSerialCommands() {
    while (Serial.available()) {
        char c = Serial.read();
        if (c == 'b' || c == 'B') {
            binaryMode = true;
            Serial.println("MODE: BINARY");
        } else if (c == 'a' || c == 'A') {
            binaryMode = false;
            Serial.println("MODE: ASCII");
        } else if (c == 's' || c == 'S') {
            printStats();
        }
    }
}

void loop() {
    checkSerialCommands();
    scanGrid();

    if (binaryMode) {
        sendBinaryFrame();
    } else {
        sendAsciiFrame();
        delay(100);
    }
}
