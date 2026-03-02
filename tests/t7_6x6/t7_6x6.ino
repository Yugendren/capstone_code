#define SER_PIN   11
#define SRCLK_PIN 12
#define RCLK_PIN  13
#define MUX_S0  4
#define MUX_S1  5
#define MUX_S2  6
#define MUX_S3  7
#define MUX_SIG 9

#define ROWS 6
#define COLS 6
#define PRESS_THRESHOLD 500

int grid[ROWS][COLS];
unsigned long scanTime = 0;
int scanCount = 0;

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
    Serial.println("ESP32-S3 Test 7: 6x6 Grid Matrix Scan");
    Serial.println("==========================================\n");
}

void setRow(int row) {
    // Shift out 8 bits MSB first, only 'row' bit is HIGH
    for (int i = 7; i >= 0; i--) {
        digitalWrite(SER_PIN, (i == row) ? HIGH : LOW);
        digitalWrite(SRCLK_PIN, HIGH);
        delayMicroseconds(5);
        digitalWrite(SRCLK_PIN, LOW);
    }
    digitalWrite(RCLK_PIN, HIGH);
    delayMicroseconds(5);
    digitalWrite(RCLK_PIN, LOW);
    delayMicroseconds(20);
}

void allRowsOff() {
    for (int i = 0; i < 8; i++) {
        digitalWrite(SER_PIN, LOW);
        digitalWrite(SRCLK_PIN, HIGH);
        delayMicroseconds(5);
        digitalWrite(SRCLK_PIN, LOW);
    }
    digitalWrite(RCLK_PIN, HIGH);
    delayMicroseconds(5);
    digitalWrite(RCLK_PIN, LOW);
}

void setMuxChannel(int ch) {
    digitalWrite(MUX_S0, ch & 0x01);
    digitalWrite(MUX_S1, (ch >> 1) & 0x01);
    digitalWrite(MUX_S2, (ch >> 2) & 0x01);
    digitalWrite(MUX_S3, (ch >> 3) & 0x01);
    delayMicroseconds(20);
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
