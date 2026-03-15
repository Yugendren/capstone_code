/*
 * Test 8: 6x6 Grid with Hardware SPI for Shift Register
 *
 * Same 6x6 grid as t7, but uses hardware SPI instead of bit-bang
 * for the 74HC595 shift register. Same wiring, same MUX, same pins.
 *
 * Pin mapping:
 *   IO11 (MOSI) -> 595 SER   (was bit-bang, now SPI)
 *   IO12 (SCK)  -> 595 SRCLK (was bit-bang, now SPI)
 *   IO13        -> 595 RCLK  (latch, still GPIO toggle)
 *   IO4-IO7     -> MUX S0-S3
 *   IO9         -> MUX SIG (ADC)
 *
 * Expected: identical ADC readings to t7, scan rate > 500 Hz
 */

#include <SPI.h>

// --- Pin definitions (unchanged from t7) ---
#define RCLK_PIN  13   // Latch — still GPIO
#define MUX_S0    4
#define MUX_S1    5
#define MUX_S2    6
#define MUX_S3    7
#define MUX_SIG   9

// SPI pins (ESP32-S3 FSPI defaults)
#define SPI_MOSI  11   // -> 595 SER
#define SPI_SCK   12   // -> 595 SRCLK
#define SPI_MISO  -1   // unused — no data coming back

#define ROWS 6
#define COLS 6
#define PRESS_THRESHOLD 500

int grid[ROWS][COLS];
unsigned long scanTime = 0;
int scanCount = 0;

SPIClass *hspi = nullptr;

void setup() {
    Serial.begin(115200);
    delay(3000);

    // Initialize SPI on FSPI bus
    hspi = new SPIClass(FSPI);
    hspi->begin(SPI_SCK, SPI_MISO, SPI_MOSI, -1);  // SCK, MISO, MOSI, SS

    // Latch pin is still plain GPIO
    pinMode(RCLK_PIN, OUTPUT);
    digitalWrite(RCLK_PIN, LOW);

    // MUX select pins
    pinMode(MUX_S0, OUTPUT);
    pinMode(MUX_S1, OUTPUT);
    pinMode(MUX_S2, OUTPUT);
    pinMode(MUX_S3, OUTPUT);

    analogReadResolution(12);

    Serial.println("\n==========================================");
    Serial.println("ESP32-S3 Test 8: 6x6 Grid (HW SPI 595)");
    Serial.println("==========================================\n");
}

// Shift one byte via SPI, then latch
void shiftOut595(uint8_t data) {
    hspi->beginTransaction(SPISettings(10000000, MSBFIRST, SPI_MODE0));
    hspi->transfer(data);
    hspi->endTransaction();

    // Pulse latch
    digitalWrite(RCLK_PIN, HIGH);
    delayMicroseconds(1);
    digitalWrite(RCLK_PIN, LOW);
}

void setRow(int row) {
    // One-hot pattern: only the target row bit is HIGH
    uint8_t pattern = (1 << row);
    shiftOut595(pattern);
    delayMicroseconds(10);  // settle time after latch
}

void allRowsOff() {
    shiftOut595(0x00);
}

void setMuxChannel(int ch) {
    digitalWrite(MUX_S0, ch & 0x01);
    digitalWrite(MUX_S1, (ch >> 1) & 0x01);
    digitalWrite(MUX_S2, (ch >> 2) & 0x01);
    digitalWrite(MUX_S3, (ch >> 3) & 0x01);
    delayMicroseconds(5);  // MUX settling
}

void scanGrid() {
    unsigned long start = micros();

    for (int row = 0; row < ROWS; row++) {
        setRow(row);
        for (int col = 0; col < COLS; col++) {
            setMuxChannel(col);
            grid[row][col] = analogRead(MUX_SIG);
        }
    }
    allRowsOff();

    scanTime = micros() - start;
    scanCount++;
}

void printGrid() {
    // Header
    Serial.print("\n      ");
    for (int c = 0; c < COLS; c++) {
        Serial.printf(" Col%d ", c);
    }
    Serial.println();

    // Divider
    Serial.print("      ");
    for (int c = 0; c < COLS; c++) {
        Serial.print("+-----");
    }
    Serial.println("+");

    // Data rows
    for (int row = 0; row < ROWS; row++) {
        Serial.printf("Row%d  ", row);
        for (int col = 0; col < COLS; col++) {
            int val = grid[row][col];
            char marker = (val > PRESS_THRESHOLD) ? '*' : ' ';
            Serial.printf("|%4d%c", val, marker);
        }
        Serial.println("|");

        Serial.print("      ");
        for (int c = 0; c < COLS; c++) {
            Serial.print("+-----");
        }
        Serial.println("+");
    }

    // Stats
    int pressCount = 0;
    for (int r = 0; r < ROWS; r++) {
        for (int c = 0; c < COLS; c++) {
            if (grid[r][c] > PRESS_THRESHOLD) pressCount++;
        }
    }

    float scanHz = 1000000.0 / scanTime;
    Serial.printf("\nPressed: %d | Scan time: %lu us (%.1f Hz) | Scan #%d\n",
                  pressCount, scanTime, scanHz, scanCount);
}

void printHeatmap() {
    Serial.println("\nHeatmap (. = none, o = light, O = medium, # = hard):");
    for (int row = 0; row < ROWS; row++) {
        Serial.print("  ");
        for (int col = 0; col < COLS; col++) {
            int val = grid[row][col];
            char c;
            if (val < 300) c = '.';
            else if (val < 1500) c = 'o';
            else if (val < 2500) c = 'O';
            else c = '#';
            Serial.printf(" %c", c);
        }
        Serial.println();
    }
}

void loop() {
    scanGrid();
    printGrid();
    printHeatmap();
    delay(500);
}
