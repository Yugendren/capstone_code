/*
 * Test 12: Full 40x30 Integration
 *
 * 5x cascaded 74HC595 (40 rows) + 2x CD74HC4067 MUX (30 columns, 15+15 split).
 * Uses hardware SPI at 10 MHz for shift registers.
 * Binary serial protocol for high-throughput data to GUI.
 *
 * Pin mapping (9 GPIO total):
 *   IO11 (MOSI) -> 595 SER chain
 *   IO12 (SCK)  -> All 595 SRCLK
 *   IO13        -> All 595 RCLK (latch)
 *   IO4         -> MUX S0 (shared)
 *   IO5         -> MUX S1 (shared)
 *   IO6         -> MUX S2 (shared)
 *   IO7         -> MUX S3 (shared)
 *   IO9         -> MUX1 SIG (ADC1_CH8, columns 0-14)
 *   IO10        -> MUX2 SIG (ADC1_CH9, columns 15-29)
 *
 * Serial protocol:
 *   ASCII mode (default): human-readable grid, compatible with existing GUI
 *   Binary mode: 0xAA 0x55 [2400 bytes: 1200 cells x 2 bytes big-endian] 0xFF 0xFE
 *   Toggle with 'b' (binary) or 'a' (ASCII) over serial
 *
 * Target: >= 60 Hz scan rate
 */

#include <SPI.h>

// --- Pin definitions ---
#define RCLK_PIN  13
#define MUX_S0    4
#define MUX_S1    5
#define MUX_S2    6
#define MUX_S3    7
#define MUX1_SIG  9    // Columns 0-14
#define MUX2_SIG  10   // Columns 15-29

#define SPI_MOSI  11
#define SPI_SCK   12
#define SPI_MISO  -1

#define NUM_595      5
#define ROWS         40
#define COLS_PER_MUX 15
#define COLS         30   // 15 + 15
#define PRESS_THRESHOLD 500

// Grid stored as 16-bit values (12-bit ADC range 0-4095)
uint16_t grid[ROWS][COLS];
unsigned long scanTime = 0;
int scanCount = 0;
bool binaryMode = false;

SPIClass *hspi = nullptr;

// Pre-computed row patterns for speed
uint8_t rowBuf[NUM_595];

void setup() {
    // Use higher baud for 40x30 data volume
    // Native USB CDC on ESP32-S3 ignores baud rate setting (always full speed)
    // But set high for CH343 fallback
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

    analogReadResolution(12);

    Serial.println("\n==========================================");
    Serial.printf("ESP32-S3 Test 12: %dx%d Full Integration\n", ROWS, COLS);
    Serial.println("==========================================");
    Serial.printf("595 chain: %d registers\n", NUM_595);
    Serial.println("MUX1 (IO9):  Columns 0-14");
    Serial.println("MUX2 (IO10): Columns 15-29");
    Serial.println("Send 'b' for binary mode, 'a' for ASCII mode\n");
}

inline void shiftOut595(uint8_t *buf, int len) {
    hspi->beginTransaction(SPISettings(10000000, MSBFIRST, SPI_MODE0));
    hspi->transfer(buf, len);
    hspi->endTransaction();

    digitalWrite(RCLK_PIN, HIGH);
    // No delay needed at 10 MHz — latch propagation is < 50 ns
    digitalWrite(RCLK_PIN, LOW);
}

inline void setRow(int row) {
    memset(rowBuf, 0, NUM_595);
    int chip = row / 8;
    int bit  = row % 8;
    rowBuf[NUM_595 - 1 - chip] = (1 << bit);
    shiftOut595(rowBuf, NUM_595);
    delayMicroseconds(3);  // minimal settle — 595 output is fast
}

inline void allRowsOff() {
    memset(rowBuf, 0, NUM_595);
    shiftOut595(rowBuf, NUM_595);
}

inline void setMuxChannel(int ch) {
    // Use direct GPIO writes for speed (still portable)
    digitalWrite(MUX_S0, ch & 0x01);
    digitalWrite(MUX_S1, (ch >> 1) & 0x01);
    digitalWrite(MUX_S2, (ch >> 2) & 0x01);
    digitalWrite(MUX_S3, (ch >> 3) & 0x01);
    delayMicroseconds(3);  // MUX settling
}

void scanGrid() {
    unsigned long start = micros();

    for (int row = 0; row < ROWS; row++) {
        setRow(row);

        for (int ch = 0; ch < COLS_PER_MUX; ch++) {
            setMuxChannel(ch);

            // Read both MUXes simultaneously (same channel select)
            // Two consecutive analogRead calls — ~10 us each on ESP32-S3
            grid[row][ch]                = analogRead(MUX1_SIG);
            grid[row][ch + COLS_PER_MUX] = analogRead(MUX2_SIG);
        }
    }
    allRowsOff();

    scanTime = micros() - start;
    scanCount++;
}

void sendBinaryFrame() {
    // Frame format: [0xAA 0x55] [2400 bytes] [0xFF 0xFE]
    // Each cell: 2 bytes big-endian (high byte first)
    static uint8_t header[2] = {0xAA, 0x55};
    static uint8_t footer[2] = {0xFF, 0xFE};

    Serial.write(header, 2);

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
    // Compact ASCII: one line per row, space-separated values
    // Format compatible with GUI parser updates
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
    Serial.printf("Pressed: %d | Scan time: %lu us (%.1f Hz) | Scan #%d\n",
                  pressCount, scanTime, scanHz, scanCount);
}

void checkSerialCommands() {
    while (Serial.available()) {
        char c = Serial.read();
        if (c == 'b' || c == 'B') {
            binaryMode = true;
            // Send confirmation in ASCII before switching
            Serial.println("MODE: BINARY");
        } else if (c == 'a' || c == 'A') {
            binaryMode = false;
            Serial.println("MODE: ASCII");
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
    }
}
