#define ADC_PIN 1  // GPIO1 / IO1

void setup() {
    Serial.begin(115200);
    delay(2000);

    Serial.println("\n================================");
    Serial.println("ESP32-S3 Test 2: ADC Verification");
    Serial.println("================================\n");

    analogReadResolution(12);  // 12-bit (0-4095)
    analogSetAttenuation(ADC_11db);  // Full range 0-3.3V

    Serial.println("Reading ADC on IO1 (GPIO1)");
    Serial.println("Connect IO1 to GND or 3.3V to test\n");
}

void loop() {
    int raw = analogRead(ADC_PIN);
    float voltage = (raw / 4095.0) * 3.3;

    Serial.printf("ADC Raw: %4d | Voltage: %.2fV | ", raw, voltage);

    if (raw < 100) {
        Serial.println("State: LOW (GND)");
    } else if (raw > 3900) {
        Serial.println("State: HIGH (3.3V)");
    } else {
        Serial.println("State: MID (floating or divider)");
    }

    delay(500);
}
