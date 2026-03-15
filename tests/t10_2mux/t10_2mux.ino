/*
 * Test 10: Dual-MUX Column Expansion (8 rows x 30 columns)
 *
 * Adds second CD74HC4067 MUX for column reading.
 * MUX1 SIG -> IO9  (ADC1_CH8) : Columns 0-14
 * MUX2 SIG -> IO10 (ADC1_CH9) : Columns 15-29
 * Both MUXes share S0-S3 select lines (IO4-IO7).
 * Both MUX EN pins hardwired to GND (always enabled).
 * Channel 15 on each MUX is unused.
 *
 * Uses 2x cascaded 595 from t9 (8 rows for testing).
 *
 * Pin mapping:
 *   IO11 (MOSI) -> 595 SER
 *   IO12 (SCK)  -> 595 SRCLK
 *   IO13        -> 595 RCLK (latch)
 *   IO4-IO7     -> MUX S0-S3 (shared, both MUXes)
 *   IO9         -> MUX1 SIG (columns 0-14)
 *   IO10        -> MUX2 SIG (columns 15-29)
 *
 * Validates:
 *   - Both ADC lines read independently
 *   - All 30 columns respond
 *   - No crosstalk between MUX SIG lines
 */

#include <SPI.h>

// --- Pin definitions ---
#define RCLK_PIN  13
#define MUX_S0    4
#define MUX_S1    5
#define MUX_S2    6
#define MUX_S3    7
#define MUX1_SIG  9    // ADC1_CH8 — columns 0-14
#define MUX2_SIG  10   // ADC1_CH9 — columns 15-29

#define SPI_MOSI  11
#define SPI_SCK   12
#define SPI_MISO  -1

#define NUM_595      2
#define ROWS         (NUM_595 * 8)   // 16 rows available, test with as many as wired
#define COLS_PER_MUX 15              // channels 0-14 used, channel 15 unused
#define COLS         (COLS_PER_MUX * 2)  // 30 total columns
#define PRESS_THRESHOLD 500

int grid[ROWS][COLS];
unsigned long scanTime = 0;
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
    Serial.printf("ESP32-S3 Test 10: %dx%d Dual-MUX\n", ROWS, COLS);
    Serial.println("==========================================");
    Serial.println("MUX1 (IO9):  Columns 0-14");
    Serial.println("MUX2 (IO10): Columns 15-29\n");
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
    buf[NUM_595 - 1 - chip] = (1 << bit);
    shiftOut595(buf, NUM_595);
    delayMicroseconds(10);
}

void allRowsOff() {
    uint8_t buf[NUM_595];
    memset(buf, 0, NUM_595);
    shiftOut595(buf, NUM_595);
}

void setMuxChannel(int ch) {
    // Both MUXes switch simultaneously (shared S0-S3)
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

        // Read both MUXes for each channel select
        for (int ch = 0; ch < COLS_PER_MUX; ch++) {
            setMuxChannel(ch);

            // Read MUX1 (columns 0-14) and MUX2 (columns 15-29)
            grid[row][ch]                = analogRead(MUX1_SIG);
            grid[row][ch + COLS_PER_MUX] = analogRead(MUX2_SIG);
        }
    }
    allRowsOff();

    scanTime = micros() - start;
    scanCount++;
}

void printGrid() {
    // Header with column numbers
    Serial.print("\n       ");
    for (int c = 0; c < COLS; c++) {
        if (c == COLS_PER_MUX) Serial.print("| ");  // MUX boundary
        Serial.printf("%4d ", c);
    }
    Serial.println();

    Serial.print("       ");
    for (int c = 0; c < COLS; c++) {
        if (c == COLS_PER_MUX) Serial.print("+-");
        Serial.print("-----");
    }
    Serial.println();

    for (int row = 0; row < ROWS; row++) {
        if (row > 0 && row % 8 == 0) {
            Serial.println("  --- 595 boundary ---");
        }

        Serial.printf("R%2d    ", row);
        for (int col = 0; col < COLS; col++) {
            if (col == COLS_PER_MUX) Serial.print("| ");  // MUX boundary
            int val = grid[row][col];
            char marker = (val > PRESS_THRESHOLD) ? '*' : ' ';
            Serial.printf("%4d%c", val, marker);
        }
        Serial.println();
    }

    // Stats
    int pressCount = 0;
    for (int r = 0; r < ROWS; r++) {
        for (int c = 0; c < COLS; c++) {
            if (grid[r][c] > PRESS_THRESHOLD) pressCount++;
        }
    }

    float scanHz = 1000000.0 / scanTime;
    Serial.printf("\nPressed: %d/%d | Scan: %lu us (%.1f Hz) | #%d\n",
                  pressCount, ROWS * COLS, scanTime, scanHz, scanCount);
}

void loop() {
    scanGrid();
    printGrid();
    delay(500);
}
