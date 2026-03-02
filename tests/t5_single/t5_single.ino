#define SER_PIN   11
#define SRCLK_PIN 12
#define RCLK_PIN  13

#define MUX_S0  4
#define MUX_S1  5
#define MUX_S2  6
#define MUX_S3  7
#define MUX_SIG 9

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

    digitalWrite(SER_PIN, LOW);
    digitalWrite(SRCLK_PIN, LOW);
    digitalWrite(RCLK_PIN, LOW);

    digitalWrite(MUX_S0, LOW);
    digitalWrite(MUX_S1, LOW);
    digitalWrite(MUX_S2, LOW);
    digitalWrite(MUX_S3, LOW);

    analogReadResolution(12);

    Serial.println("\n================================");
    Serial.println("ESP32-S3 Test 5: 1x1 Sensing Point");
    Serial.println("================================\n");
}

void setRow(bool on) {
    digitalWrite(SER_PIN, on ? HIGH : LOW);
    digitalWrite(SRCLK_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(SRCLK_PIN, LOW);

    digitalWrite(RCLK_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(RCLK_PIN, LOW);
}

void loop() {
    int adcOff, adcOn;
    float vOff, vOn;

    setRow(false);
    delay(50);
    adcOff = analogRead(MUX_SIG);
    vOff = (adcOff / 4095.0) * 3.3;

    setRow(true);
    delay(50);
    adcOn = analogRead(MUX_SIG);
    vOn = (adcOn / 4095.0) * 3.3;

    String state;
    if (adcOn < 300) {
        state = "NO CONTACT (check wiring)";
    } else if (adcOn < 800) {
        state = "UNPRESSED (light contact)";
    } else if (adcOn < 2000) {
        state = "LIGHT PRESS";
    } else if (adcOn < 3000) {
        state = "MEDIUM PRESS";
    } else {
        state = "HARD PRESS";
    }

    int barLen = map(adcOn, 0, 4095, 0, 30);
    String bar = "";
    for (int i = 0; i < barLen; i++) bar += "#";
    for (int i = barLen; i < 30; i++) bar += ".";

    Serial.printf("Row OFF: %4d (%.2fV) | Row ON: %4d (%.2fV) | [%s] %s\n",
                  adcOff, vOff, adcOn, vOn, bar.c_str(), state.c_str());

    delay(200);
}
