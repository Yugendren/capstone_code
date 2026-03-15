/*
 * Test 11: Full 40-Row 595 Cascade (40 rows x 6 columns)
 *
 * 5x cascaded 74HC595 shift registers driving 40 rows.
 * SPI shifts 5 bytes per row. Single MUX, 6 columns.
 *
 * Wiring:
 *   IO11 (MOSI) -> 595_1 SER
 *   595_1 Q7S   -> 595_2 SER -> ... -> 595_5 SER
 *   IO12 (SCK)  -> All 595 SRCLK (parallel)
 *   IO13        -> All 595 RCLK  (parallel)
 *   IO4-IO7     -> MUX S0-S3
 *   IO9         -> MUX SIG (ADC)
 *
 *   595_1 Q0-Q7 -> Rows 0-7   (each through 1N4148TA diode)
 *   595_2 Q0-Q7 -> Rows 8-15
 *   595_3 Q0-Q7 -> Rows 16-23
 *   595_4 Q0-Q7 -> Rows 24-31
 *   595_5 Q0-Q7 -> Rows 32-39
 *
 * Validates:
 *   - All 40 rows one-hot
 *   - Boundary rows (7↔8, 15↔16, 23↔24, 31↔32) no ghosting
 *   - Shift time < 10 us for 5 bytes
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

#define NUM_595   5
#define ROWS      40   // 5 x 8
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
    Serial.printf("ESP32-S3 Test 11: %d rows x %d cols (%d x 595)\n", ROWS, COLS, NUM_595);
    Serial.println("==========================================\n");
}

void shiftOut595(uint8_t *buf, int len) {
    hspi->beginTransaction(SPISettings(10000000, MSBFIRST, SPI_MODE0));
    hspi->transfer(buf, len);
    hspi->endTransaction();

    digitalWrite(RCLK_PIN, HIGH);
    delayMicroseconds(1);
    digitalWrite(RCLK_PIN, LOW);
}

void setRow(int row) {
    uint8_t buf[NUM_595];
    memset(buf, 0, NUM_595);

    int chip = row / 8;
    int bit  = row % 8;
    // chip 0 (closest) -> buf[NUM_595-1], chip 4 (farthest) -> buf[0]
    buf[NUM_595 - 1 - chip] = (1 << bit);

    unsigned long t0 = micros();
    shiftOut595(buf, NUM_595);
    shiftTime = micros() - t0;

    delayMicroseconds(10);
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
        if (row > 0 && row % 8 == 0) {
            Serial.printf("  --- 595 #%d/%d boundary ---\n", row / 8, NUM_595);
        }

        Serial.printf("R%2d    ", row);
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

    int pressCount = 0;
    for (int r = 0; r < ROWS; r++) {
        for (int c = 0; c < COLS; c++) {
            if (grid[r][c] > PRESS_THRESHOLD) pressCount++;
        }
    }

    float scanHz = 1000000.0 / scanTime;
    Serial.printf("\nPressed: %d/%d | Scan: %lu us (%.1f Hz) | Shift: %lu us | #%d\n",
                  pressCount, ROWS * COLS, scanTime, scanHz, shiftTime, scanCount);
}

void loop() {
    scanGrid();
    printGrid();
    delay(500);
}
