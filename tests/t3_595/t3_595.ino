#define SER_PIN   11  // Data
#define SRCLK_PIN 12  // Shift clock
#define RCLK_PIN  13  // Latch
#define Q0_READ   10  // Read back Q0 via ADC on IO10

void setup() {
    Serial.begin(115200);
    delay(2000);

    pinMode(SER_PIN, OUTPUT);
    pinMode(SRCLK_PIN, OUTPUT);
    pinMode(RCLK_PIN, OUTPUT);

    digitalWrite(SER_PIN, LOW);
    digitalWrite(SRCLK_PIN, LOW);
    digitalWrite(RCLK_PIN, LOW);

    analogReadResolution(12);

    Serial.println("\n================================");
    Serial.println("ESP32-S3 Test 3: 74HC595 Shift Register");
    Serial.println("================================\n");
}

void shiftOutByte(uint8_t data) {
    for (int i = 7; i >= 0; i--) {
        digitalWrite(SER_PIN, (data >> i) & 1);
        digitalWrite(SRCLK_PIN, HIGH);
        delayMicroseconds(10);
        digitalWrite(SRCLK_PIN, LOW);
        delayMicroseconds(10);
    }
    digitalWrite(RCLK_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(RCLK_PIN, LOW);
}

bool verifyQ0(bool expected) {
    delay(10);
    int adc = analogRead(Q0_READ);
    bool actual = (adc > 2000);

    Serial.printf("  Q0 readback: ADC=%d (%.2fV) -> %s | Expected: %s | %s\n",
        adc, (adc/4095.0)*3.3,
        actual ? "HIGH" : "LOW",
        expected ? "HIGH" : "LOW",
        (actual == expected) ? "PASS" : "FAIL");

    return (actual == expected);
}

int testsPassed = 0;
int testsFailed = 0;

void runTest(const char* name, uint8_t pattern, bool expectedQ0) {
    Serial.printf("\nTest: %s (pattern=0x%02X)\n", name, pattern);
    shiftOutByte(pattern);
    if (verifyQ0(expectedQ0)) {
        testsPassed++;
    } else {
        testsFailed++;
    }
}

void loop() {
    Serial.println("\n--- Starting 74HC595 Tests ---\n");
    testsPassed = 0;
    testsFailed = 0;

    runTest("All LOW", 0x00, false);
    delay(500);

    runTest("All HIGH", 0xFF, true);
    delay(500);

    runTest("Q0 only", 0x01, true);
    delay(500);

    runTest("Q0 low, others high", 0xFE, false);
    delay(500);

    runTest("Alternating 0xAA", 0xAA, false);
    delay(500);

    runTest("Alternating 0x55", 0x55, true);
    delay(500);

    Serial.println("\n================================");
    Serial.printf("RESULTS: %d passed, %d failed\n", testsPassed, testsFailed);
    if (testsFailed == 0) {
        Serial.println("*** ALL TESTS PASSED ***");
    } else {
        Serial.println("*** SOME TESTS FAILED ***");
    }
    Serial.println("================================");

    Serial.println("\nWaiting 10 seconds before repeat...\n");
    delay(10000);
}
