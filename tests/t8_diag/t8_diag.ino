/*
 * Test 8 Diagnostic: Verify 5x 595 cascade + 2x MUX wiring
 *
 * No FFC needed. Tests:
 *   1. SPI communication — shifts 5 bytes through cascade
 *   2. Each 595 output goes HIGH one at a time (check with multimeter)
 *   3. MUX channel select — cycles S0-S3 (check with multimeter)
 *   4. Both ADC lines — reads IO9 and IO10 (should be ~0 with pulldowns)
 *
 * Interactive: send commands over serial:
 *   'r'     — run full 40-row sweep (1 second per row, check with multimeter)
 *   'f'     — fast sweep all 40 rows (50ms each)
 *   'm'     — test MUX channels 0-15 on both MUXes
 *   'a'     — read both ADC lines continuously
 *   '0'-'4' — activate specific 595 chip (all 8 outputs HIGH)
 *   's'     — summary test (quick check of everything)
 *   number  — type a row number 0-39 to hold that row HIGH
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

#define NUM_595   5

SPIClass *hspi = nullptr;
uint8_t rowBuf[NUM_595];

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

    allOff();

    Serial.println("\n==========================================");
    Serial.println("  DIAGNOSTIC: 5x 595 + 2x MUX Checker");
    Serial.println("==========================================");
    printMenu();
}

void shiftOut595(uint8_t *buf, int len) {
    hspi->beginTransaction(SPISettings(10000000, MSBFIRST, SPI_MODE0));
    hspi->transfer(buf, len);
    hspi->endTransaction();
    digitalWrite(RCLK_PIN, HIGH);
    delayMicroseconds(1);
    digitalWrite(RCLK_PIN, LOW);
}

void allOff() {
    memset(rowBuf, 0, NUM_595);
    shiftOut595(rowBuf, NUM_595);
}

void setRow(int row) {
    memset(rowBuf, 0, NUM_595);
    int chip = row / 8;
    int bit  = row % 8;
    rowBuf[NUM_595 - 1 - chip] = (1 << bit);
    shiftOut595(rowBuf, NUM_595);
}

void setChipAll(int chip) {
    memset(rowBuf, 0, NUM_595);
    rowBuf[NUM_595 - 1 - chip] = 0xFF;
    shiftOut595(rowBuf, NUM_595);
}

void setMuxChannel(int ch) {
    digitalWrite(MUX_S0, ch & 0x01);
    digitalWrite(MUX_S1, (ch >> 1) & 0x01);
    digitalWrite(MUX_S2, (ch >> 2) & 0x01);
    digitalWrite(MUX_S3, (ch >> 3) & 0x01);
}

void printMenu() {
    Serial.println("\nCommands:");
    Serial.println("  s  — Quick summary test");
    Serial.println("  r  — Slow sweep rows 0-39 (1s each, use multimeter)");
    Serial.println("  f  — Fast sweep rows 0-39 (50ms each)");
    Serial.println("  m  — Test MUX channels 0-15");
    Serial.println("  a  — Read ADC lines continuously (press any key to stop)");
    Serial.println("  0-4 — Light up all outputs on 595 #N");
    Serial.println("  h  — Hold specific row (enter row number 0-39)");
    Serial.println("  x  — All off");
    Serial.println();
}

void testSummary() {
    Serial.println("\n=== SUMMARY TEST ===\n");

    // Test 1: SPI shift timing
    Serial.print("1. SPI shift (5 bytes): ");
    unsigned long t0 = micros();
    for (int i = 0; i < 100; i++) {
        memset(rowBuf, 0xAA, NUM_595);
        shiftOut595(rowBuf, NUM_595);
    }
    unsigned long elapsed = micros() - t0;
    Serial.printf("%.1f us avg", elapsed / 100.0);
    Serial.println(elapsed / 100.0 < 20 ? "  [PASS]" : "  [SLOW]");
    allOff();

    // Test 2: Each 595 chip
    Serial.println("2. 595 chips (each lit for 200ms):");
    for (int chip = 0; chip < NUM_595; chip++) {
        setChipAll(chip);
        Serial.printf("   595 #%d (rows %2d-%2d) — ALL HIGH", chip + 1, chip * 8, chip * 8 + 7);
        delay(200);

        // Quick check: set one row and verify others are off
        // We can't electrically verify without FFC, but we confirm SPI works
        setRow(chip * 8);  // just Q0 of this chip
        delay(50);
        Serial.println("  [SHIFTED]");
    }
    allOff();

    // Test 3: MUX select lines
    Serial.println("3. MUX select lines:");
    for (int ch = 0; ch < 16; ch++) {
        setMuxChannel(ch);
        Serial.printf("   CH%2d — S3=%d S2=%d S1=%d S0=%d\n",
            ch,
            (ch >> 3) & 1, (ch >> 2) & 1, (ch >> 1) & 1, ch & 1);
        delay(50);
    }

    // Test 4: ADC lines
    Serial.println("4. ADC readings (no FFC, expect ~0 with pulldowns):");
    int adc1 = analogRead(MUX1_SIG);
    int adc2 = analogRead(MUX2_SIG);
    Serial.printf("   MUX1 (IO9):  %d %s\n", adc1, adc1 < 100 ? "[PASS - pulldown working]" : adc1 < 500 ? "[OK - some noise]" : "[HIGH - check wiring]");
    Serial.printf("   MUX2 (IO10): %d %s\n", adc2, adc2 < 100 ? "[PASS - pulldown working]" : adc2 < 500 ? "[OK - some noise]" : "[HIGH - check wiring]");

    Serial.println("\n=== DONE ===");
    allOff();
    printMenu();
}

void sweepRows(int delayMs) {
    Serial.printf("\n=== ROW SWEEP (%dms per row) ===\n", delayMs);
    Serial.println("Check each row output with multimeter — should read ~3.3V\n");
    for (int row = 0; row < 40; row++) {
        setRow(row);
        int chip = row / 8;
        int bit  = row % 8;
        Serial.printf("Row %2d  (595 #%d, Q%d) — HIGH", row, chip + 1, bit);
        if (bit == 0 && row > 0) Serial.print("  << 595 boundary");
        Serial.println();
        delay(delayMs);
    }
    allOff();
    Serial.println("\nAll off.");
    printMenu();
}

void testMux() {
    Serial.println("\n=== MUX CHANNEL TEST ===");
    Serial.println("Check S0-S3 pins and SIG with multimeter\n");
    for (int ch = 0; ch < 16; ch++) {
        setMuxChannel(ch);
        int adc1 = analogRead(MUX1_SIG);
        int adc2 = analogRead(MUX2_SIG);
        Serial.printf("CH%2d  S[%d%d%d%d]  MUX1=%4d  MUX2=%4d\n",
            ch,
            (ch >> 3) & 1, (ch >> 2) & 1, (ch >> 1) & 1, ch & 1,
            adc1, adc2);
        delay(200);
    }
    Serial.println("\nDone.");
    printMenu();
}

void readAdc() {
    Serial.println("\n=== ADC CONTINUOUS (press any key to stop) ===\n");
    while (!Serial.available()) {
        int adc1 = analogRead(MUX1_SIG);
        int adc2 = analogRead(MUX2_SIG);
        Serial.printf("MUX1(IO9)=%4d  MUX2(IO10)=%4d\r", adc1, adc2);
        delay(100);
    }
    Serial.read();  // consume the key
    Serial.println("\nStopped.");
    printMenu();
}

void holdRow() {
    Serial.println("Enter row number (0-39):");
    while (!Serial.available()) delay(10);
    String input = "";
    delay(100);  // wait for full input
    while (Serial.available()) {
        input += (char)Serial.read();
    }
    int row = input.toInt();
    if (row >= 0 && row < 40) {
        setRow(row);
        int chip = row / 8;
        int bit  = row % 8;
        Serial.printf("Holding Row %d (595 #%d, Q%d) HIGH — send any key to release\n", row, chip + 1, bit);
        while (!Serial.available()) delay(10);
        Serial.read();
        allOff();
        Serial.println("Released.");
    } else {
        Serial.println("Invalid row number.");
    }
    printMenu();
}

void loop() {
    if (Serial.available()) {
        char c = Serial.read();
        switch (c) {
            case 's': testSummary(); break;
            case 'r': sweepRows(1000); break;
            case 'f': sweepRows(50); break;
            case 'm': testMux(); break;
            case 'a': readAdc(); break;
            case '0': setChipAll(0); Serial.println("595 #1 (rows 0-7) ALL HIGH"); break;
            case '1': setChipAll(1); Serial.println("595 #2 (rows 8-15) ALL HIGH"); break;
            case '2': setChipAll(2); Serial.println("595 #3 (rows 16-23) ALL HIGH"); break;
            case '3': setChipAll(3); Serial.println("595 #4 (rows 24-31) ALL HIGH"); break;
            case '4': setChipAll(4); Serial.println("595 #5 (rows 32-39) ALL HIGH"); break;
            case 'h': holdRow(); break;
            case 'x': allOff(); Serial.println("All off."); break;
            case '\n': case '\r': break;
            default: printMenu(); break;
        }
    }
}
