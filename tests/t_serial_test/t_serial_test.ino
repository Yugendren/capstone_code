void setup() {
    Serial.begin(115200);
    delay(3000);
    Serial.println("HELLO FROM ESP32");
}

void loop() {
    Serial.println("TICK");
    delay(1000);
}
