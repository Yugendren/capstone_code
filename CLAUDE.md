# PRESSURE SENSOR MATRIX - BREADBOARD TESTING

## PROJECT OVERVIEW
Building a 40×30 pressure sensor matrix using flex PCBs, velostat, and custom controller board for capstone project. Currently at breadboard testing phase with 6×6 prototype working.

## HARDWARE AVAILABLE

**Microcontroller:**
- ESP32-S3-WROOM-1 N16R8 (16MB flash, 8MB PSRAM, pre-soldered headers, USB-C)

**Row Drivers:**
- 10× SN74HC595N shift registers (DIP-16)
- 50× 1N4148TA diodes (through-hole)

**Column Readers:**
- 3× CD74HC4067 16-channel MUX breakout (pre-soldered)

**Passive:**
- 100× 10K resistors (through-hole)

**Interconnects:**
- 2× FFC breakout 1.0mm 30-pin
- 2× FFC breakout 1.0mm 40-pin
- 4× FFC cable 40-pin, 3× FFC cable 30-pin

**Sensing:**
- 3× Velostat sheets (11"×11")
- Copper foil

**Test Equipment:**
- 2× Breadboard (60×10 each)
- Jumper wires, Multimeter

## CIRCUIT DESIGN

**Scanning principle:**
1. Drive ONE row HIGH via 74HC595 cascade
2. Diode on each row prevents ghosting
3. Select column via CD74HC4067 MUX
4. Read ADC with 10K pulldown
5. V_adc = 2.6V × (10K / (R_velostat + 10K))

**ESP32-S3 Pin Assignments:**
| Function | GPIO |
|----------|------|
| 595 SER (data) | IO11 |
| 595 SRCLK (clock) | IO12 |
| 595 RCLK (latch) | IO13 |
| MUX S0 | IO4 |
| MUX S1 | IO5 |
| MUX S2 | IO6 |
| MUX S3 | IO7 |
| ADC1 (MUX SIG) | IO9 |
| ADC2 (595 Q0 readback) | IO10 |

**74HC595 Wiring (each):**
- Pin 16 VCC → 3.3V
- Pin 8 GND → GND
- Pin 10 SRCLR → 3.3V
- Pin 13 OE → GND
- Pin 14 SER → IO11 or prev Q7S
- Pin 11 SRCLK → IO12
- Pin 12 RCLK → IO13
- Outputs Q0-Q7 → diode anode → row

**74HC595 Bit Ordering (important):**
- Shift MSB first: `for (i = 7; i >= 0; i--)` — last bit shifted lands at Q0
- Use `uint8_t pattern = (1 << row)` to set the correct output

**CD74HC4067 Wiring:**
- VCC → 3.3V, GND → GND, EN → GND
- S0-S3 → IO4-IO7
- SIG → ADC (IO9) + 10K pulldown to GND

## TEST RESULTS

| Test | Description | Status | Notes |
|------|-------------|--------|-------|
| T1 | ESP32 alive | PASS | 2 cores, 16MB flash, 8MB PSRAM confirmed |
| T2 | ADC verify | PASS | Full 12-bit range (0-4095) on IO1 |
| T3 | Single 595 | PASS | 6/6 bit patterns correct, Q0 readback via IO10 |
| T4 | Single MUX | PASS | All 16 channels, zero crosstalk |
| T5 | 1×1 point | PASS | Velostat: OPEN→4Ω, ADC 0→3225 |
| T6 | 2×2 grid (ghosting) | PASS | Diagonal test: no ghost cells |
| T7 | 6×6 grid | PASS | 322 Hz scan rate, clear localized pressure |
| T8 | Full 40×30 | PENDING | Waiting for parts |

**Velostat Characterization (from T5b):**
- No press: OPEN circuit (>1MΩ)
- Light press: 290-430 Ω (ADC ~3180)
- Medium press: 98-130 Ω (ADC ~3213)
- Hard press: 4-10 Ω (ADC ~3225)

**Performance (6×6 grid):**
- Scan time: ~3.1 ms per full scan
- Scan rate: ~322 Hz
- Extrapolated 40×30 rate: ~89 Hz (well above 60 Hz target)

## REAL-TIME GUI

Web-based visualization using Python WebSocket server + HTML/JS frontend.

**Features:**
- 6×6 grid with white→black pressure gradient and red ADC values
- Raw/Filtered mode toggle
- Baseline calibration (averages first 10 scans on startup)
- Adjustable noise floor (default 200, slider 0-1000)
- Auto-reconnecting WebSocket
- Connection status indicator and scan rate display

**Files:**
- `tests/gui/server.py` — Python server (serial reader + WebSocket + HTTP)
- `tests/gui/index.html` — Browser frontend

**Noise Filtering:**
1. Baseline calibration: averages N scans (default 10) at startup with no pressure
2. Baseline subtraction: `filtered = raw - baseline`
3. Noise floor: values below threshold (default 200) are zeroed
4. Recalibrate anytime via GUI button

## QUICK START

```bash
# One command to start everything:
./start.sh
```

Or manually:
```bash
# 1. Attach ESP32 to WSL (from Windows PowerShell):
usbipd list
usbipd attach --wsl --busid <BUSID>

# 2. Fix serial permissions (in WSL):
sudo chmod 666 /dev/ttyACM0

# 3. (Optional) Compile and upload:
export PATH="$PATH:$(pwd)/bin"
arduino-cli compile --fqbn esp32:esp32:esp32s3:PSRAM=opi,FlashSize=16M,PartitionScheme=app3M_fat9M_16MB tests/t7_6x6
arduino-cli upload --fqbn esp32:esp32:esp32s3:PSRAM=opi,FlashSize=16M,PartitionScheme=app3M_fat9M_16MB -p /dev/ttyACM0 tests/t7_6x6

# 4. Launch GUI:
cd tests/gui
python3 server.py
# Open http://localhost:8080 in browser
```

## WORKING ENVIRONMENT

- OS: Windows WSL2 (Ubuntu)
- Arduino CLI v1.4.1 (installed to `bin/arduino-cli`)
- ESP32 board FQBN: `esp32:esp32:esp32s3:PSRAM=opi,FlashSize=16M,PartitionScheme=app3M_fat9M_16MB`
- ESP32 core: v3.3.7
- Serial port: `/dev/ttyACM0` (USB-C via CH343 driver)
- Serial baud: 115200
- Python dependencies: `pyserial`, `websockets`

## KNOWN ISSUES

- **WSL2 USB**: Serial port disappears on disconnect. Re-attach with `usbipd attach --wsl` from PowerShell.
- **Permissions reset**: `/dev/ttyACM0` permissions reset on every USB reconnect. `start.sh` handles this.
- **Col0 wiring**: Physical Col0 reads 0 in 6×6 breadboard setup — loose wire on breadboard.
- **Velostat crosstalk**: Continuous velostat sheet causes neighbor cell activation. Cut individual pieces or use noise floor filtering.

## INSTRUCTIONS FOR CLAUDE

1. Use Arduino CLI for all ESP32 operations
2. Always check board connection with `arduino-cli board list`
3. If upload fails, remind user to hold BOOT button
4. After upload, monitor serial with `arduino-cli monitor -p <port> -c baudrate=115200`
5. Run tests interactively - confirm each step before proceeding
6. Update test status in this file after each test passes
7. arduino-cli is at `bin/arduino-cli` — add to PATH: `export PATH="$PATH:$(pwd)/bin"`
8. Serial port permissions: `sudo chmod 666 /dev/ttyACM0`
