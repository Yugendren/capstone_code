/*
 * Test 13: Optimized 40x30 Scan
 *
 * Same hardware as t12 (5x 595, 2x MUX, 40x30).
 * Performance optimizations:
 *   1. Direct GPIO register writes for MUX select (instead of digitalWrite)
 *   2. Reduced ADC settling time (tuned)
 *   3. Optional 10-bit ADC mode for faster conversion
 *   4. Continuous scanning (no delay between frames)
 *   5. Binary-only output for maximum throughput
 *
 * Target: stable >= 60 Hz, ideally 70+ Hz
 */

#include <SPI.h>
#include "soc/gpio_struct.h"
#include "driver/gpio.h"

// --- Pin definitions ---
#define RCLK_PIN  13
#define MUX_S0    4
#define MUX_S1    5
#define MUX_S2    6
#define MUX_S3    7
#define MUX1_SIG  9
#define MUX2_SIG  10

#define SPI_MOSI  11
#define SPI_SCK   12
#define SPI_MISO  -1

#define NUM_595      5
#define ROWS         40
#define COLS_PER_MUX 15
#define COLS         30
#define PRESS_THRESHOLD 500

// Use 10-bit ADC for faster conversion (still 0-4095 range, just less precision)
// Set to 12 if you need full precision
#define ADC_BITS     12

uint16_t grid[ROWS][COLS];
unsigned long scanTime = 0;
unsigned long frameCount = 0;
unsigned long fpsTimer = 0;
float measuredFps = 0;
bool binaryMode = true;  // Default to binary for speed

SPIClass *hspi = nullptr;
uint8_t rowBuf[NUM_595];

// Pre-computed MUX select patterns for direct register write
// GPIO 4,5,6,7 -> bits 4,5,6,7 in GPIO.out register
// We create a mask and value for each channel 0-14
static const uint32_t MUX_PIN_MASK = (1 << MUX_S0) | (1 << MUX_S1) | (1 << MUX_S2) | (1 << MUX_S3);
uint32_t muxPatterns[COLS_PER_MUX];

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

    analogReadResolution(ADC_BITS);

    precomputeMuxPatterns();

    fpsTimer = millis();

    Serial.println("\n==========================================");
    Serial.printf("ESP32-S3 Test 13: %dx%d Optimized\n", ROWS, COLS);
    Serial.println("==========================================");
    Serial.printf("ADC resolution: %d bits\n", ADC_BITS);
    Serial.println("Direct register MUX select");
    Serial.println("Send 'b' for binary, 'a' for ASCII, 's' for stats\n");
}

inline void shiftOut595Fast(uint8_t *buf, int len) {
    hspi->beginTransaction(SPISettings(10000000, MSBFIRST, SPI_MODE0));
    hspi->transfer(buf, len);
    hspi->endTransaction();

    // Direct register latch pulse — faster than digitalWrite
    GPIO.out_w1ts = (1 << RCLK_PIN);  // set HIGH
    GPIO.out_w1tc = (1 << RCLK_PIN);  // set LOW
}

inline void setRowFast(int row) {
    memset(rowBuf, 0, NUM_595);
    int chip = row / 8;
    int bit  = row % 8;
    rowBuf[NUM_595 - 1 - chip] = (1 << bit);
    shiftOut595Fast(rowBuf, NUM_595);
    // Minimal settle — 595 tPHL is ~26 ns, diode adds ~4 ns
    delayMicroseconds(2);
}

inline void allRowsOff() {
    memset(rowBuf, 0, NUM_595);
    shiftOut595Fast(rowBuf, NUM_595);
}

inline void setMuxChannelFast(int ch) {
    // Direct register write: clear all MUX pins, then set the pattern
    GPIO.out_w1tc = MUX_PIN_MASK;        // clear S0-S3
    GPIO.out_w1ts = muxPatterns[ch];      // set new channel
    delayMicroseconds(2);  // MUX tPHL is ~40 ns, but ADC input needs settling
}

void scanGrid() {
    unsigned long start = micros();

    for (int row = 0; row < ROWS; row++) {
        setRowFast(row);

        for (int ch = 0; ch < COLS_PER_MUX; ch++) {
            setMuxChannelFast(ch);

            // Read both MUXes — back to back
            grid[row][ch]                = analogRead(MUX1_SIG);
            grid[row][ch + COLS_PER_MUX] = analogRead(MUX2_SIG);
        }
    }
    allRowsOff();

    scanTime = micros() - start;
    frameCount++;

    // Update FPS every second
    unsigned long now = millis();
    if (now - fpsTimer >= 1000) {
        measuredFps = frameCount * 1000.0 / (now - fpsTimer);
        frameCount = 0;
        fpsTimer = now;
    }
}

void sendBinaryFrame() {
    // Frame: [0xAA 0x55] [scanTime 4 bytes] [2400 bytes grid] [0xFF 0xFE]
    uint8_t header[2] = {0xAA, 0x55};
    uint8_t footer[2] = {0xFF, 0xFE};

    Serial.write(header, 2);

    // Send scan time as 4 bytes (big-endian) so GUI can compute Hz
    uint8_t timeBytes[4] = {
        (uint8_t)((scanTime >> 24) & 0xFF),
        (uint8_t)((scanTime >> 16) & 0xFF),
        (uint8_t)((scanTime >> 8) & 0xFF),
        (uint8_t)(scanTime & 0xFF)
    };
    Serial.write(timeBytes, 4);

    // Send grid data: row-major, 2 bytes per cell (big-endian)
    for (int r = 0; r < ROWS; r++) {
        for (int c = 0; c < COLS; c++) {
            uint16_t val = grid[r][c];
            uint8_t buf[2] = {(uint8_t)(val >> 8), (uint8_t)(val & 0xFF)};
            Serial.write(buf, 2);
        }
    }

    Serial.write(footer, 2);
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
    Serial.printf("ADC bits: %d\n", ADC_BITS);
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
