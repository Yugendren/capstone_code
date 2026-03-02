#define SER_PIN   11
#define SRCLK_PIN 12
#define RCLK_PIN  13
#define MUX_S0  4
#define MUX_S1  5
#define MUX_S2  6
#define MUX_S3  7
#define MUX_SIG 9

#define ROWS 2
#define COLS 2
#define PRESS_THRESHOLD 500

int grid[ROWS][COLS];

void setup() {
    Serial.begin(115200);
    delay(2000);

    pinMode(SER_PIN, OUTPUT);
    pinMode(SRCLK_PIN, OUTPUT);
    pinMode(RCLK_PIN, OUTPUT);
    pinMode(MUX_S0, OUTPUT);
    pinMode(MUX_S1, OUTPUT);
    pinMode(MUX_S2, OUTPUT);
    pinMode(MUX_S3, OUTPUT);

    analogReadResolution(12);

    Serial.println("\n==========================================");
    Serial.println("ESP32-S3 Test 6: 2x2 Grid + Ghosting Test");
    Serial.println("==========================================\n");
}

void setRow(int row) {
    // Shift out MSB first: last bit shifted lands at Q0
    uint8_t pattern = (1 << row);  // bit 0=Q0, bit 1=Q1
    for (int i = 7; i >= 0; i--) {
        digitalWrite(SER_PIN, (pattern >> i) & 1);
        digitalWrite(SRCLK_PIN, HIGH);
        delayMicroseconds(10);
        digitalWrite(SRCLK_PIN, LOW);
    }
    digitalWrite(RCLK_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(RCLK_PIN, LOW);
    delayMicroseconds(50);  // Settling time
}

void allRowsOff() {
    for (int i = 0; i < 8; i++) {
        digitalWrite(SER_PIN, LOW);
        digitalWrite(SRCLK_PIN, HIGH);
        delayMicroseconds(10);
        digitalWrite(SRCLK_PIN, LOW);
    }
    digitalWrite(RCLK_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(RCLK_PIN, LOW);
}

void setMuxChannel(int ch) {
    digitalWrite(MUX_S0, ch & 0x01);
    digitalWrite(MUX_S1, (ch >> 1) & 0x01);
    digitalWrite(MUX_S2, (ch >> 2) & 0x01);
    digitalWrite(MUX_S3, (ch >> 3) & 0x01);
    delayMicroseconds(50);
}

void scanGrid() {
    for (int row = 0; row < ROWS; row++) {
        setRow(row);
        for (int col = 0; col < COLS; col++) {
            setMuxChannel(col);
            delay(2);
            grid[row][col] = analogRead(MUX_SIG);
        }
    }
    allRowsOff();
}

void printGrid() {
    Serial.println("\n        Col0    Col1");
    Serial.println("      +-------+-------+");
    for (int row = 0; row < ROWS; row++) {
        Serial.printf("Row%d  |", row);
        for (int col = 0; col < COLS; col++) {
            int val = grid[row][col];
            char marker = (val > PRESS_THRESHOLD) ? '*' : ' ';
            Serial.printf(" %4d%c |", val, marker);
        }
        Serial.println();
        Serial.println("      +-------+-------+");
    }

    // Count pressed points
    int pressCount = 0;
    for (int r = 0; r < ROWS; r++) {
        for (int c = 0; c < COLS; c++) {
            if (grid[r][c] > PRESS_THRESHOLD) pressCount++;
        }
    }
    Serial.printf("Pressed points: %d (* = pressed, threshold=%d)\n", pressCount, PRESS_THRESHOLD);
}

void loop() {
    scanGrid();
    printGrid();
    delay(500);
}
