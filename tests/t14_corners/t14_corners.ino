/*
 * Test 14: Corner & Edge Diagnostic for 40x30 Matrix
 *
 * Interactive test to verify FFC wiring is correct.
 * Guides user through pressing specific locations and
 * confirms the expected row/column responds.
 *
 * Physical layout (looking down from above):
 *   Row 0 = right,  Row 39 = left
 *   Col 0 = bottom, Col 29 = top
 *   Copper faces down on both flex PCBs
 *
 * Commands:
 *   'c' — guided corner test (4 corners, step by step)
 *   'e' — edge sweep test
 *   'l' — live heatmap (continuous scan, shows pressed cells)
 *   'b' — baseline scan (hands off, check for stuck cells)
 *   's' — single full scan dump
 *   'g' — ghost test (press one corner, check for ghosts)
 *   'h' — help
 */

#include <SPI.h>

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
#define THRESHOLD    300   // ADC value to count as "pressed"

uint16_t grid[ROWS][COLS];
uint16_t baseline[ROWS][COLS];
bool hasBaseline = false;
unsigned long scanTime = 0;

SPIClass *hspi = nullptr;
uint8_t rowBuf[NUM_595];

// ---- Hardware drivers ----

void shiftOut595(uint8_t *buf, int len) {
    hspi->beginTransaction(SPISettings(10000000, MSBFIRST, SPI_MODE0));
    hspi->transfer(buf, len);
    hspi->endTransaction();
    digitalWrite(RCLK_PIN, HIGH);
    delayMicroseconds(1);
    digitalWrite(RCLK_PIN, LOW);
}

void setRow(int row) {
    memset(rowBuf, 0, NUM_595);
    int chip = row / 8;
    int bit  = row % 8;
    rowBuf[NUM_595 - 1 - chip] = (1 << bit);
    shiftOut595(rowBuf, NUM_595);
    delayMicroseconds(3);
}

void allRowsOff() {
    memset(rowBuf, 0, NUM_595);
    shiftOut595(rowBuf, NUM_595);
}

void setMuxChannel(int ch) {
    digitalWrite(MUX_S0, ch & 0x01);
    digitalWrite(MUX_S1, (ch >> 1) & 0x01);
    digitalWrite(MUX_S2, (ch >> 2) & 0x01);
    digitalWrite(MUX_S3, (ch >> 3) & 0x01);
    delayMicroseconds(3);
}

// ---- Scanning ----

void scanGrid() {
    unsigned long start = micros();
    for (int row = 0; row < ROWS; row++) {
        setRow(row);
        for (int ch = 0; ch < COLS_PER_MUX; ch++) {
            setMuxChannel(ch);
            grid[row][ch]                = analogRead(MUX1_SIG);
            grid[row][ch + COLS_PER_MUX] = analogRead(MUX2_SIG);
        }
    }
    allRowsOff();
    scanTime = micros() - start;
}

void takeBaseline() {
    Serial.println("Taking baseline (hands off the mat)...");
    delay(500);
    // Average 5 scans
    memset(baseline, 0, sizeof(baseline));
    for (int n = 0; n < 5; n++) {
        scanGrid();
        for (int r = 0; r < ROWS; r++)
            for (int c = 0; c < COLS; c++)
                baseline[r][c] += grid[r][c];
    }
    for (int r = 0; r < ROWS; r++)
        for (int c = 0; c < COLS; c++)
            baseline[r][c] /= 5;
    hasBaseline = true;

    // Report any stuck-high cells
    int stuck = 0;
    for (int r = 0; r < ROWS; r++) {
        for (int c = 0; c < COLS; c++) {
            if (baseline[r][c] > THRESHOLD) {
                Serial.printf("  WARNING: Cell [R%d,C%d] stuck HIGH at baseline = %d\n", r, c, baseline[r][c]);
                stuck++;
            }
        }
    }
    if (stuck == 0) {
        Serial.println("  Baseline OK — no stuck cells.");
    } else {
        Serial.printf("  %d stuck cell(s) found. Check wiring.\n", stuck);
    }
    Serial.printf("  Scan time: %lu us (%.1f Hz)\n\n", scanTime, 1000000.0 / scanTime);
}

// Get value minus baseline
int getVal(int r, int c) {
    int raw = grid[r][c];
    if (hasBaseline) {
        raw -= baseline[r][c];
        if (raw < 0) raw = 0;
    }
    return raw;
}

// ---- Test routines ----

void printHelp() {
    Serial.println("\n==========================================");
    Serial.println("  TEST 14: Corner & Edge Diagnostic");
    Serial.println("==========================================");
    Serial.println("\nPhysical layout (looking down at mat):");
    Serial.println("  Row 0 = RIGHT,  Row 39 = LEFT");
    Serial.println("  Col 0 = BOTTOM, Col 29 = TOP");
    Serial.println("\nCommands:");
    Serial.println("  b — Baseline scan (hands off mat)");
    Serial.println("  c — Guided corner test");
    Serial.println("  e — Edge sweep test");
    Serial.println("  l — Live heatmap (continuous, press key to stop)");
    Serial.println("  s — Single full scan dump");
    Serial.println("  g — Ghost test");
    Serial.println("  h — This help message");
    Serial.println();
}

// Find the cell with the highest reading
void findPeak(int &peakR, int &peakC, int &peakVal) {
    peakR = 0; peakC = 0; peakVal = 0;
    for (int r = 0; r < ROWS; r++) {
        for (int c = 0; c < COLS; c++) {
            int v = getVal(r, c);
            if (v > peakVal) {
                peakVal = v;
                peakR = r;
                peakC = c;
            }
        }
    }
}

// Count cells above threshold
int countPressed() {
    int count = 0;
    for (int r = 0; r < ROWS; r++)
        for (int c = 0; c < COLS; c++)
            if (getVal(r, c) > THRESHOLD) count++;
    return count;
}

// Describe physical location of a row/col
void describeLocation(int row, int col) {
    // Row: 0=right, 39=left
    // Col: 0=bottom, 29=top
    const char* rowPos = (row < 10) ? "RIGHT" : (row >= 30) ? "LEFT" : "MIDDLE";
    const char* colPos = (col < 8)  ? "BOTTOM" : (col >= 22) ? "TOP" : "MIDDLE";
    Serial.printf("[R%d,C%d] = physical %s-%s", row, col, colPos, rowPos);
}

bool waitForKeyOrTimeout(int timeoutMs) {
    unsigned long start = millis();
    while (!Serial.available()) {
        if (millis() - start > (unsigned long)timeoutMs) return false;
        delay(10);
    }
    return true;
}

void flushSerial() {
    while (Serial.available()) Serial.read();
}

// Test one corner: tell user where to press, scan, verify
bool testCorner(const char* label, int expectRow, int expectCol) {
    Serial.println("--------------------------------------------");
    Serial.printf(">> Press the %s corner of the mat\n", label);
    Serial.printf("   Expected: [R%d, C%d]\n", expectRow, expectCol);
    Serial.println("   Press and HOLD, then hit Enter...");

    flushSerial();
    while (!Serial.available()) delay(10);
    flushSerial();

    // Take 3 scans, use the last one
    scanGrid(); scanGrid(); scanGrid();

    int peakR, peakC, peakVal;
    findPeak(peakR, peakC, peakVal);
    int pressed = countPressed();

    Serial.printf("   Peak: [R%d, C%d] = %d", peakR, peakC, peakVal);

    bool rowOk = (abs(peakR - expectRow) <= 2);
    bool colOk = (abs(peakC - expectCol) <= 2);

    if (peakVal < THRESHOLD) {
        Serial.println("  [NO PRESS DETECTED]");
        return false;
    } else if (rowOk && colOk) {
        Serial.println("  [PASS]");
    } else {
        Serial.println("  [WRONG LOCATION]");
        Serial.printf("   Expected ~[R%d,C%d] but got [R%d,C%d]\n",
                      expectRow, expectCol, peakR, peakC);
        if (!rowOk && colOk) Serial.println("   >> ROW mapping may be wrong");
        if (rowOk && !colOk) Serial.println("   >> COLUMN mapping may be wrong");
        if (!rowOk && !colOk) Serial.println("   >> BOTH row and column mapping wrong");
    }

    Serial.printf("   Pressed cells: %d\n", pressed);
    if (pressed > 10) {
        Serial.println("   WARNING: Many cells active — possible ghosting or velostat bleed");
    }

    // Show the neighborhood around the peak
    Serial.println("   Neighborhood (5x5 around peak):");
    int r0 = max(0, peakR - 2), r1 = min(ROWS - 1, peakR + 2);
    int c0 = max(0, peakC - 2), c1 = min(COLS - 1, peakC + 2);
    Serial.print("        ");
    for (int c = c0; c <= c1; c++) Serial.printf("  C%-3d", c);
    Serial.println();
    for (int r = r0; r <= r1; r++) {
        Serial.printf("   R%-3d", r);
        for (int c = c0; c <= c1; c++) {
            int v = getVal(r, c);
            char mark = (r == peakR && c == peakC) ? '*' : (v > THRESHOLD) ? '+' : ' ';
            Serial.printf(" %4d%c", v, mark);
        }
        Serial.println();
    }
    Serial.println();

    return (rowOk && colOk && peakVal >= THRESHOLD);
}

void guidedCornerTest() {
    Serial.println("\n========== GUIDED CORNER TEST ==========");
    Serial.println("You will press each of the 4 corners.");
    Serial.println("Physical layout reminder:");
    Serial.println("  Bottom-Right = [R0, C0]");
    Serial.println("  Top-Right    = [R0, C29]");
    Serial.println("  Bottom-Left  = [R39, C0]");
    Serial.println("  Top-Left     = [R39, C29]");
    Serial.println();

    if (!hasBaseline) takeBaseline();

    int pass = 0;
    if (testCorner("BOTTOM-RIGHT", 0, 0))   pass++;
    if (testCorner("TOP-RIGHT",    0, 29))   pass++;
    if (testCorner("BOTTOM-LEFT",  39, 0))   pass++;
    if (testCorner("TOP-LEFT",     39, 29))  pass++;

    Serial.println("============ RESULTS ============");
    Serial.printf("Corners passed: %d / 4\n", pass);
    if (pass == 4) {
        Serial.println("ALL CORNERS CORRECT — wiring is good!");
    } else {
        Serial.println("Some corners failed. Check:");
        Serial.println("  - FFC cable orientation (pin 1 alignment)");
        Serial.println("  - Diode direction (band toward FFC)");
        Serial.println("  - 595 cascade order");
        Serial.println("  - MUX channel wiring");
    }
    Serial.println("=================================\n");
}

void edgeSweepTest() {
    Serial.println("\n========== EDGE SWEEP TEST ==========");
    Serial.println("Drag your finger along each edge slowly.");
    Serial.println("Watch that row/col numbers change correctly.\n");

    if (!hasBaseline) takeBaseline();

    Serial.println(">> Sweep RIGHT EDGE (bottom to top): Col should go 0 → 29");
    Serial.println("   Press Enter when ready, then sweep. Press Enter to stop.");
    flushSerial();
    while (!Serial.available()) delay(10);
    flushSerial();

    while (!Serial.available()) {
        scanGrid();
        int peakR, peakC, peakVal;
        findPeak(peakR, peakC, peakVal);
        if (peakVal > THRESHOLD) {
            Serial.printf("   Peak: [R%2d, C%2d] = %4d  ", peakR, peakC, peakVal);
            // Print a simple bar
            int bar = min(30, peakVal / 100);
            for (int i = 0; i < bar; i++) Serial.print('#');
            Serial.println();
        }
        delay(50);
    }
    flushSerial();

    Serial.println("\n>> Sweep BOTTOM EDGE (right to left): Row should go 0 → 39");
    Serial.println("   Press Enter when ready, then sweep. Press Enter to stop.");
    flushSerial();
    while (!Serial.available()) delay(10);
    flushSerial();

    while (!Serial.available()) {
        scanGrid();
        int peakR, peakC, peakVal;
        findPeak(peakR, peakC, peakVal);
        if (peakVal > THRESHOLD) {
            Serial.printf("   Peak: [R%2d, C%2d] = %4d  ", peakR, peakC, peakVal);
            int bar = min(30, peakVal / 100);
            for (int i = 0; i < bar; i++) Serial.print('#');
            Serial.println();
        }
        delay(50);
    }
    flushSerial();

    Serial.println("\nEdge sweep done.\n");
}

void liveHeatmap() {
    Serial.println("\n========== LIVE HEATMAP ==========");
    Serial.println("Showing pressed cells. Press any key to stop.\n");

    if (!hasBaseline) takeBaseline();

    while (!Serial.available()) {
        scanGrid();
        int peakR, peakC, peakVal;
        findPeak(peakR, peakC, peakVal);
        int pressed = countPressed();

        if (pressed > 0) {
            Serial.printf("Pressed: %2d cells | Peak: [R%2d,C%2d]=%4d | %.0f Hz | Cells: ",
                          pressed, peakR, peakC, peakVal, 1000000.0 / scanTime);
            // List all pressed cells
            int listed = 0;
            for (int r = 0; r < ROWS && listed < 15; r++) {
                for (int c = 0; c < COLS && listed < 15; c++) {
                    int v = getVal(r, c);
                    if (v > THRESHOLD) {
                        Serial.printf("[%d,%d]=%d ", r, c, v);
                        listed++;
                    }
                }
            }
            if (listed >= 15) Serial.print("...");
            Serial.println();
        } else {
            Serial.printf("No press | %.0f Hz\r", 1000000.0 / scanTime);
        }
        delay(80);
    }
    flushSerial();
    Serial.println("\nStopped.\n");
}

void singleScanDump() {
    Serial.println("\n========== FULL SCAN DUMP ==========\n");
    scanGrid();

    // Column headers
    Serial.print("      ");
    for (int c = 0; c < COLS; c++) {
        if (c == 15) Serial.print("| ");
        Serial.printf("C%-3d ", c);
    }
    Serial.println();
    Serial.print("      ");
    for (int c = 0; c < COLS; c++) {
        if (c == 15) Serial.print("| ");
        Serial.print("---- ");
    }
    Serial.println();

    for (int r = 0; r < ROWS; r++) {
        Serial.printf("R%-3d: ", r);
        for (int c = 0; c < COLS; c++) {
            if (c == 15) Serial.print("| ");
            int v = grid[r][c];
            if (v > THRESHOLD)
                Serial.printf("%4d*", v);
            else
                Serial.printf("%4d ", v);
        }
        Serial.println();
    }

    float hz = (scanTime > 0) ? 1000000.0 / scanTime : 0;
    Serial.printf("\nScan time: %lu us (%.1f Hz)\n\n", scanTime, hz);
}

void ghostTest() {
    Serial.println("\n========== GHOST TEST ==========");
    Serial.println("Tests for ghosting / crosstalk.");
    Serial.println("Press ONE corner firmly, then hit Enter.\n");

    if (!hasBaseline) takeBaseline();

    flushSerial();
    while (!Serial.available()) delay(10);
    flushSerial();

    scanGrid(); scanGrid(); scanGrid();

    int peakR, peakC, peakVal;
    findPeak(peakR, peakC, peakVal);

    if (peakVal < THRESHOLD) {
        Serial.println("No press detected. Try again.\n");
        return;
    }

    Serial.printf("Peak at [R%d, C%d] = %d\n", peakR, peakC, peakVal);

    // Check for ghosts: cells far from peak that are also active
    int ghosts = 0;
    Serial.println("Checking for ghost cells (>5 rows or cols from peak):");
    for (int r = 0; r < ROWS; r++) {
        for (int c = 0; c < COLS; c++) {
            int v = getVal(r, c);
            if (v > THRESHOLD) {
                int rowDist = abs(r - peakR);
                int colDist = abs(c - peakC);
                if (rowDist > 5 || colDist > 5) {
                    Serial.printf("  GHOST: [R%d, C%d] = %d (distance: %d rows, %d cols from peak)\n",
                                  r, c, v, rowDist, colDist);
                    ghosts++;
                }
            }
        }
    }

    if (ghosts == 0) {
        Serial.println("  No ghosts detected — [PASS]");
    } else {
        Serial.printf("  %d ghost cell(s) — check diode orientation and velostat isolation\n", ghosts);
    }

    // Check the entire row and column of the peak for unexpected activity
    Serial.printf("\nRow %d scan (should only be active near C%d):\n  ", peakR, peakC);
    for (int c = 0; c < COLS; c++) {
        int v = getVal(peakR, c);
        if (v > THRESHOLD)
            Serial.printf("C%d=%d ", c, v);
    }

    Serial.printf("\nCol %d scan (should only be active near R%d):\n  ", peakC, peakR);
    for (int r = 0; r < ROWS; r++) {
        int v = getVal(r, peakC);
        if (v > THRESHOLD)
            Serial.printf("R%d=%d ", r, v);
    }
    Serial.println("\n");
}

// ---- Main ----

void setup() {
    Serial.begin(115200);
    // Wait for USB CDC to connect (ESP32-S3 native USB)
    unsigned long waitStart = millis();
    while (!Serial && millis() - waitStart < 5000) delay(10);
    delay(500);

    Serial.println("Booting t14_corners...");
    Serial.flush();

    hspi = new SPIClass(FSPI);
    hspi->begin(SPI_SCK, SPI_MISO, SPI_MOSI, -1);

    pinMode(RCLK_PIN, OUTPUT);
    digitalWrite(RCLK_PIN, LOW);

    pinMode(MUX_S0, OUTPUT);
    pinMode(MUX_S1, OUTPUT);
    pinMode(MUX_S2, OUTPUT);
    pinMode(MUX_S3, OUTPUT);

    analogReadResolution(12);

    printHelp();
    Serial.println("Starting with baseline scan...\n");
    takeBaseline();
}

void loop() {
    if (Serial.available()) {
        char c = Serial.read();
        switch (c) {
            case 'b': takeBaseline(); break;
            case 'c': guidedCornerTest(); break;
            case 'e': edgeSweepTest(); break;
            case 'l': liveHeatmap(); break;
            case 's': singleScanDump(); break;
            case 'g': ghostTest(); break;
            case 'h': printHelp(); break;
            case '\n': case '\r': break;
            default: printHelp(); break;
        }
    }
}
