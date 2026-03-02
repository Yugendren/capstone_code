#define SER_PIN   11
#define SRCLK_PIN 12
#define RCLK_PIN  13
#define MUX_S0  4
#define MUX_S1  5
#define MUX_S2  6
#define MUX_S3  7
#define MUX_SIG 9

const float V_SOURCE = 2.6;    // 3.3V - 0.7V diode drop
const float R_PULLDOWN = 10000.0;  // 10K ohm

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

    Serial.println("\n==========================================");
    Serial.println("ESP32-S3 Test 5b: Voltage & Resistance Calc");
    Serial.println("==========================================\n");
    Serial.println("Circuit: 3.3V -> 595 -> Diode -> Velostat -> MUX -> 10K -> GND");
    Serial.println("V_source after diode = 2.6V\n");
    Serial.println("ADC     | Voltage | R_velostat | Conductance | Bar");
    Serial.println("--------|---------|------------|-------------|----");
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
    setRow(true);
    delay(20);

    // Average 5 samples
    long sum = 0;
    for (int i = 0; i < 5; i++) {
        sum += analogRead(MUX_SIG);
        delay(5);
    }
    int adc = sum / 5;

    // Calculate voltage at ADC pin
    float v_adc = (adc / 4095.0) * 3.3;

    // Calculate velostat resistance
    // Voltage divider: V_adc = V_SOURCE * (R_PULLDOWN / (R_velo + R_PULLDOWN))
    // Rearranged: R_velo = R_PULLDOWN * (V_SOURCE / V_adc - 1)
    float r_velo;
    float conductance;

    if (v_adc < 0.01) {
        r_velo = 999999.0;  // Open circuit
        conductance = 0;
    } else {
        r_velo = R_PULLDOWN * (V_SOURCE / v_adc - 1.0);
        if (r_velo < 0) r_velo = 0;
        conductance = 1000.0 / r_velo;  // mS (milliSiemens)
    }

    // Visual bar based on ADC
    int barLen = map(adc, 0, 4095, 0, 20);
    String bar = "";
    for (int i = 0; i < barLen; i++) bar += "#";
    for (int i = barLen; i < 20; i++) bar += ".";

    // Print formatted output
    if (r_velo > 100000) {
        Serial.printf("%4d    | %5.2fV  | OPEN       | 0.00 mS     | [%s]\n",
                      adc, v_adc, bar.c_str());
    } else {
        Serial.printf("%4d    | %5.2fV  | %6.0f ohm | %5.2f mS    | [%s]\n",
                      adc, v_adc, r_velo, conductance, bar.c_str());
    }

    delay(200);
}
