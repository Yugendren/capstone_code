# PRESSURE SENSOR MATRIX - BREADBOARD TESTING

## PROJECT OVERVIEW
Building a 40×30 pressure sensor matrix using flex PCBs, velostat, and custom controller board for capstone project. Currently at breadboard testing phase with 6×6 prototype working, scaling up to 40×30.

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

## PIN PLAN — Optimized 40×30 (9 GPIO total)

**Accessible pins (one side of ESP32-S3):**
2x 3.3V, RST, IO3, IO4, IO5, IO6, IO7, IO8, IO9, IO10, IO11, IO12, IO13, IO14, IO15, IO16, IO17, IO18, IO46, 5V, GND (17 GPIOs + power/reset)

| Pin   | Function              | Notes                                    |
|-------|-----------------------|------------------------------------------|
| IO11  | SPI MOSI / 595 SER   | Hardware SPI (same wire as current SER)  |
| IO12  | SPI SCK / 595 SRCLK  | Hardware SPI (same wire as current SRCLK)|
| IO13  | 595 RCLK (latch)     | GPIO toggle after SPI transfer           |
| IO4   | MUX S0               | Shared across both MUXes                 |
| IO5   | MUX S1               | Shared across both MUXes                 |
| IO6   | MUX S2               | Shared across both MUXes                 |
| IO7   | MUX S3               | Shared across both MUXes                 |
| IO9   | MUX1 SIG (ADC1_CH8)  | Columns 0-14                             |
| IO10  | MUX2 SIG (ADC1_CH9)  | Columns 15-29                            |

**Spare pins (8):** IO3, IO8, IO14, IO15, IO16, IO17, IO18, IO46

**Row driving:** 5x 595 cascade, SPI shifts 5 bytes per row.
```
IO11 (MOSI) → 595_1 SER → 595_2 SER → 595_3 SER → 595_4 SER → 595_5 SER
IO12 (SCK)  → All SRCLK (parallel)
IO13        → All RCLK  (parallel)
595_1 Q0-Q7 → Rows 0-7 (each through 1N4148TA diode)
595_2 Q0-Q7 → Rows 8-15
595_3 Q0-Q7 → Rows 16-23
595_4 Q0-Q7 → Rows 24-31
595_5 Q0-Q7 → Rows 32-39
```

**Column reading:** 2x MUX, 15+15 split, shared S0-S3, separate SIG.
MUX EN pins hardwired to GND (always enabled). Channel 15 on each MUX is unused.

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
- SPI sends MSB first
- SPI transfer buffer: buf[0] = farthest 595, buf[N-1] = closest 595
- Use `uint8_t pattern = (1 << bit)` where `bit = row % 8`
- Chip index: `chip = row / 8`, buffer position: `buf[NUM_595 - 1 - chip]`

**CD74HC4067 Wiring:**
- VCC → 3.3V, GND → GND, EN → GND
- S0-S3 → IO4-IO7
- MUX1 SIG → IO9 + 10K pulldown to GND
- MUX2 SIG → IO10 + 10K pulldown to GND

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
| T8 | 6×6 SPI | PENDING | HW SPI conversion of t7, same wiring |
| T9 | 595 cascade | PENDING | 2x 595, 16 rows, SPI driver |
| T10 | Dual-MUX 30 cols | PENDING | 2x MUX (15+15), 8-16 rows |
| T11 | 40-row cascade | PENDING | 5x 595, 40 rows, 6 cols |
| T12 | Full 40×30 | PENDING | 40 rows + 30 cols integration |
| T13 | Optimized 40×30 | PENDING | Direct register writes, tuned ADC |

**Iterative scale-up dependency graph:**
```
T8 (SPI 6x6)
  ├──→ T9 (cascade 595s)  ──→ T11 (40 rows)
  └──→ T10 (2 MUXes)       ──→        ↓
                                  T12 (40×30)
                                     ↓
                                  T13 (optimized)
```
T9 and T10 can be done in parallel (independent subsystems).

**Velostat Characterization (from T5b):**
- No press: OPEN circuit (>1MΩ)
- Light press: 290-430 Ω (ADC ~3180)
- Medium press: 98-130 Ω (ADC ~3213)
- Hard press: 4-10 Ω (ADC ~3225)

**Performance:**
- 6×6 scan time: ~3.1 ms (322 Hz) — bit-bang
- 6×6 SPI estimate: < 1 ms (> 500 Hz)
- 40×30 SPI estimate: ~14 ms (~71 Hz)

## SCAN RATE ANALYSIS (40×30)

```
Per row:
  SPI shift 5 bytes (10 MHz):           5 us
  15 channels x (3us settle + 2x ADC):  15 x 23 us = 345 us
  Row total:                            350 us

Full scan: 40 x 350 us = 14.0 ms → ~71 Hz  (above 60 Hz target)
```

## SERIAL PROTOCOL

**ASCII mode (default for t7-t11):**
- Human-readable grid with `Row%d  |%4d%c|...` format
- Stats line: `Pressed: %d | Scan time: %lu us (%.1f Hz)`
- Baud: 115200 (t7) or 921600 (t12+)

**Binary mode (t12/t13):**
- Header: 0xAA 0x55
- Scan time: 4 bytes big-endian (microseconds)
- Grid: ROWS × COLS × 2 bytes, big-endian, row-major
- Footer: 0xFF 0xFE
- Toggle: send 'b' (binary) or 'a' (ASCII) over serial

## REAL-TIME GUI

Web-based visualization using Python WebSocket server + HTML5 Canvas frontend.

**Features:**
- Dynamic grid sizing (auto-detects 6×6, 40×30, or any size)
- Canvas-based rendering (scales to 1200+ cells)
- White→black pressure gradient with red ADC values
- Raw/Filtered mode toggle
- Baseline calibration (averages first 10 scans on startup)
- Adjustable noise floor (default 200, slider 0-1000)
- Hover tooltip showing R/C coordinates and values
- Auto-reconnecting WebSocket
- Supports both ASCII and binary serial protocols

**Files:**
- `tests/gui/server.py` — Python server (serial reader + WebSocket + HTTP)
- `tests/gui/index.html` — Browser frontend (Canvas-based)

**Environment variables for server.py:**
- `SERIAL_PORT` (default: /dev/ttyACM0)
- `BAUD_RATE` (default: 921600)
- `ROWS` (default: 40)
- `COLS` (default: 30)

**For 6×6 testing:** `ROWS=6 COLS=6 BAUD_RATE=115200 python3 tests/gui/server.py`

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

# 3. Compile and upload (example for t8):
export PATH="$PATH:$(pwd)/bin"
arduino-cli compile --fqbn esp32:esp32:esp32s3:PSRAM=opi,FlashSize=16M,PartitionScheme=app3M_fat9M_16MB tests/t8_spi_6x6
arduino-cli upload --fqbn esp32:esp32:esp32s3:PSRAM=opi,FlashSize=16M,PartitionScheme=app3M_fat9M_16MB -p /dev/ttyACM0 tests/t8_spi_6x6

# 4. Launch GUI (6x6 mode):
ROWS=6 COLS=6 BAUD_RATE=115200 python3 tests/gui/server.py

# 5. Launch GUI (40x30 mode):
python3 tests/gui/server.py
# Open http://localhost:8080 in browser
```

## WORKING ENVIRONMENT

- OS: Windows WSL2 (Ubuntu)
- Arduino CLI v1.4.1 (installed to `bin/arduino-cli`)
- ESP32 board FQBN: `esp32:esp32:esp32s3:PSRAM=opi,FlashSize=16M,PartitionScheme=app3M_fat9M_16MB`
- ESP32 core: v3.3.7
- Serial port: `/dev/ttyACM0` (USB-C via CH343 driver)
- Serial baud: 115200 (t7), 921600 (t12+)
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
9. For 40×30 tests, use baud rate 921600: `arduino-cli monitor -p <port> -c baudrate=921600`
