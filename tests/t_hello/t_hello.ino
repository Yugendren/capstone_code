void setup() {
    Serial.begin(115200);
    while (!Serial) delay(10);
    delay(500);
    Serial.println("HELLO FROM ESP32-S3");
}

void loop() {
    Serial.println("alive");
    delay(1000);
}
