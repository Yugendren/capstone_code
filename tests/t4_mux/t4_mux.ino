#define MUX_S0  4
#define MUX_S1  5
#define MUX_S2  6
#define MUX_S3  7
#define MUX_SIG 9

void setup() {
    Serial.begin(115200);
    delay(2000);

    pinMode(MUX_S0, OUTPUT);
    pinMode(MUX_S1, OUTPUT);
    pinMode(MUX_S2, OUTPUT);
    pinMode(MUX_S3, OUTPUT);

    analogReadResolution(12);

    Serial.println("\n================================");
    Serial.println("ESP32-S3 Test 4: CD74HC4067 MUX");
    Serial.println("================================\n");
}

void setMuxChannel(int ch) {
    digitalWrite(MUX_S0, ch & 0x01);
    digitalWrite(MUX_S1, (ch >> 1) & 0x01);
    digitalWrite(MUX_S2, (ch >> 2) & 0x01);
    digitalWrite(MUX_S3, (ch >> 3) & 0x01);
    delayMicroseconds(10);  // Settling time
}

int readMuxChannel(int ch) {
    setMuxChannel(ch);
    delay(5);
    return analogRead(MUX_SIG);
}

void loop() {
    Serial.println("\n--- Scanning all 16 MUX channels ---\n");
    Serial.println("All channels floating (should read ~0V due to pulldown)\n");

    for (int ch = 0; ch < 16; ch++) {
        int adc = readMuxChannel(ch);
        float voltage = (adc / 4095.0) * 3.3;

        Serial.printf("CH%2d: ADC=%4d (%.2fV)", ch, adc, voltage);

        if (adc < 200) {
            Serial.println(" [LOW - pulldown working]");
        } else if (adc > 3800) {
            Serial.println(" [HIGH - connected to 3.3V]");
        } else {
            Serial.println(" [MID - floating or connected]");
        }
    }

    Serial.println("\n================================");
    Serial.println("INTERACTIVE TEST:");
    Serial.println("Connect any channel (C0-C15) to 3.3V");
    Serial.println("That channel should show HIGH");
    Serial.println("================================\n");

    delay(5000);
}
