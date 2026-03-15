/*
 * Test 9: Multi-595 Cascade with SPI
 *
 * Expands from 1 to 2 cascaded 74HC595 shift registers (16 rows).
 * SPI shifts 2 bytes per row activation. Still uses single MUX, 6 columns.
 *
 * Wiring:
 *   IO11 (MOSI) -> 595_1 SER
 *   595_1 Q7S   -> 595_2 SER  (cascade)
 *   IO12 (SCK)  -> Both 595 SRCLK (parallel)
 *   IO13        -> Both 595 RCLK  (parallel)
 *   IO4-IO7     -> MUX S0-S3
 *   IO9         -> MUX SIG (ADC)
 *
 * Bit order: SPI sends MSB first. We send 2 bytes [byte1, byte0].
 *   byte1 shifts through 595_1 into 595_2 (rows 8-15)
 *   byte0 stays in 595_1 (rows 0-7)
 *
 * Test validates:
 *   - Rows 0-5: identical to t8 readings
 *   - Rows 6-7 (on 595_1): activate correctly
 *   - Rows 8-15 (on 595_2): activate correctly
 *   - No ghosting at 595 boundary (row 7→8)
 */

#include <SPI.h>

// --- Pin definitions ---
#define RCLK_PIN  13
#define MUX_S0    4
#define MUX_S1    5
#define MUX_S2    6
#define MUX_S3    7
#define MUX_SIG   9

#define SPI_MOSI  11
#define SPI_SCK   12
#define SPI_MISO  -1

#define NUM_595   2        // Number of cascaded shift registers
#define ROWS      (NUM_595 * 8)  // 16 rows
#define COLS      6
#define PRESS_THRESHOLD 500

int grid[ROWS][COLS];
unsigned long scanTime = 0;
unsigned long shiftTime = 0;
int scanCount = 0;

SPIClass *hspi = nullptr;

void setup() {
    Serial.begin(115200);
    delay(3000);

    hspi = new SPIClass(FSPI);
    hspi->begin(SPI_SCK, SPI_MISO, SPI_MOSI, -1);

    pinMode(RCLK_PIN, OUTPUT);
    digitalWrite(RCLK_PIN, LOW);

    pinMode(MUX_S0, OUTPUT);
    pinMode(MUX_S1, OUTPUT);
    pinMode(MUX_S2, OUTPUT);
    pinMode(MUX_S3, OUTPUT);

    analogReadResolution(12);

    Serial.println("\n==========================================");
    Serial.printf("ESP32-S3 Test 9: %dx%d Cascade (%d x 595)\n", ROWS, COLS, NUM_595);
    Serial.println("==========================================\n");
}

// Shift out NUM_595 bytes via SPI, then latch.
// buf[0] = last 595 in chain (farthest), buf[NUM_595-1] = first 595 (closest to ESP32)
// SPI sends buf[0] first, which gets pushed through to the last 595.
void shiftOut595(uint8_t *buf, int len) {
    hspi->beginTransaction(SPISettings(10000000, MSBFIRST, SPI_MODE0));
    hspi->transfer(buf, len);
    hspi->endTransaction();

    // Pulse latch
    digitalWrite(RCLK_PIN, HIGH);
    delayMicroseconds(1);
    digitalWrite(RCLK_PIN, LOW);
}

void setRow(int row) {
    uint8_t buf[NUM_595];
    memset(buf, 0, NUM_595);

    // row 0-7 -> 595_1 (closest to ESP32), row 8-15 -> 595_2
    // SPI sends buf[0] first, which shifts through to the last 595.
    // So: 595_2 (farthest) gets buf[0], 595_1 (closest) gets buf[1].
    int chip = row / 8;       // which 595 (0 = first/closest, 1 = second/farthest)
    int bit  = row % 8;       // which output on that 595

    // Map chip index to buffer position:
    // chip 0 (closest/595_1) -> buf[NUM_595 - 1] (last sent, stays in first 595)
    // chip 1 (farthest/595_2) -> buf[NUM_595 - 2] (sent first, pushed to second 595)
    buf[NUM_595 - 1 - chip] = (1 << bit);

    unsigned long t0 = micros();
    shiftOut595(buf, NUM_595);
    shiftTime = micros() - t0;

    delayMicroseconds(10);  // settle
}

void allRowsOff() {
    uint8_t buf[NUM_595];
    memset(buf, 0, NUM_595);
    shiftOut595(buf, NUM_595);
}

void setMuxChannel(int ch) {
    digitalWrite(MUX_S0, ch & 0x01);
    digitalWrite(MUX_S1, (ch >> 1) & 0x01);
    digitalWrite(MUX_S2, (ch >> 2) & 0x01);
    digitalWrite(MUX_S3, (ch >> 3) & 0x01);
    delayMicroseconds(5);
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
    Serial.print("\n       ");
    for (int c = 0; c < COLS; c++) {
        Serial.printf(" Col%d ", c);
    }
    Serial.println();

    Serial.print("       ");
    for (int c = 0; c < COLS; c++) {
        Serial.print("+-----");
    }
    Serial.println("+");

    for (int row = 0; row < ROWS; row++) {
        // Mark 595 boundary
        if (row > 0 && row % 8 == 0) {
            Serial.print("  ---  ");
            for (int c = 0; c < COLS; c++) {
                Serial.print("------");
            }
            Serial.println("-  (595 boundary)");
        }

        Serial.printf("Row%2d  ", row);
        for (int col = 0; col < COLS; col++) {
            int val = grid[row][col];
            char marker = (val > PRESS_THRESHOLD) ? '*' : ' ';
            Serial.printf("|%4d%c", val, marker);
        }
        Serial.println("|");
    }

    Serial.print("       ");
    for (int c = 0; c < COLS; c++) {
        Serial.print("+-----");
    }
    Serial.println("+");

    // Stats
    int pressCount = 0;
    for (int r = 0; r < ROWS; r++) {
        for (int c = 0; c < COLS; c++) {
            if (grid[r][c] > PRESS_THRESHOLD) pressCount++;
        }
    }

    float scanHz = 1000000.0 / scanTime;
    Serial.printf("\nPressed: %d | Scan: %lu us (%.1f Hz) | Shift: %lu us | #%d\n",
                  pressCount, scanTime, scanHz, shiftTime, scanCount);
    Serial.printf("595 chain: %d registers, %d rows\n", NUM_595, ROWS);
}

void loop() {
    scanGrid();
    printGrid();
    delay(500);
}
