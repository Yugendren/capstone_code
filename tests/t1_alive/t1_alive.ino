void setup() {
    Serial.begin(115200);
    delay(2000);

    Serial.println("\n================================");
    Serial.println("ESP32-S3 Test 1: Board Alive");
    Serial.println("================================\n");

    Serial.printf("Chip Model: %s\n", ESP.getChipModel());
    Serial.printf("Chip Cores: %d\n", ESP.getChipCores());
    Serial.printf("Flash: %lu MB\n", ESP.getFlashChipSize() / (1024 * 1024));
    Serial.printf("PSRAM: %lu MB\n", ESP.getPsramSize() / (1024 * 1024));

    Serial.println("\n--- Heartbeat starting ---");
}

int count = 0;

void loop() {
    Serial.printf("Heartbeat: %d\n", count++);
    delay(1000);
}
