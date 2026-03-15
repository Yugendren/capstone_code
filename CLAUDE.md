# PRESSURE SENSOR MATRIX — 40×30 BREADBOARD PROTOTYPE

## PROJECT OVERVIEW
40×30 pressure sensor matrix using flex PCBs, velostat, and ESP32-S3 controller on breadboard. The full 40×30 grid is wired, scanning, and displaying via a web GUI. Currently optimizing and refining.

## HARDWARE

**Microcontroller:**
- ESP32-S3-WROOM-1 N16R8 (16MB flash, 8MB PSRAM, USB-C)
- **Use the native USB port** (labeled "USB", not "UART/COM") — shows as VID:PID `303a:1001`
- The other USB-C port (CH343, `1a86:55d3`) has no WSL2 driver — do NOT use it

**Row Drivers:**
- 5× SN74HC595N shift registers (DIP-16) in cascade
- 40× 1N4148TA diodes — **anode (no band) faces 595, cathode (band) faces FFC**

**Column Readers:**
- 2× CD74HC4067 16-channel MUX breakout (pre-soldered)

**Passive:**
- 2× 10K pulldown resistors (on MUX1 SIG and MUX2 SIG lines)

**Interconnects:**
- 1× FFC breakout 40-pin 1.0mm → rows
- 1× FFC breakout 30-pin 1.0mm → columns

**Sensing Layer (assembled):**
- Flex PCB 40-pin (rows) on BOTTOM, copper face UP toward velostat
- Velostat sheet sandwiched in middle
- Flex PCB 30-pin (columns) on TOP, copper face DOWN toward velostat

**Flex PCB Dimensions:**
- Row traces: 3mm wide, 1mm gap = 4mm pitch (40 traces)
- Column traces: 4mm wide, 1mm gap = 5mm pitch (30 traces)

## PHYSICAL ORIENTATION (looking down at mat)

```
                Col 29 (top)
                    ↑
     ┌──────────────────────────────┐
     │  (R39,C29)         (R0,C29) │
     │   top-left         top-right│
     │                             │
Row 39 ←                        → Row 0
(left)│                           │(right)
     │                             │
     │  (R39,C0)           (R0,C0) │
     │  bot-left          bot-right│
     └──────────────────────────────┘
                    ↓
                Col 0 (bottom)

  40-pin FFC exits → right side (row 0 end)
  30-pin FFC exits → bottom (col 0 end)
```

## PIN PLAN — 9 GPIO total

| Pin   | Function              | Notes                                    |
|-------|-----------------------|------------------------------------------|
| IO11  | SPI MOSI / 595 SER   | Hardware SPI 10 MHz                      |
| IO12  | SPI SCK / 595 SRCLK  | Hardware SPI 10 MHz                      |
| IO13  | 595 RCLK (latch)     | GPIO toggle after SPI transfer           |
| IO4   | MUX S0               | Shared across both MUXes                 |
| IO5   | MUX S1               | Shared across both MUXes                 |
| IO6   | MUX S2               | Shared across both MUXes                 |
| IO7   | MUX S3               | Shared across both MUXes                 |
| IO9   | MUX1 SIG (ADC1_CH8)  | Columns 0-14                             |
| IO10  | MUX2 SIG (ADC1_CH9)  | Columns 15-29                            |

**Spare pins (8):** IO3, IO8, IO14, IO15, IO16, IO17, IO18, IO46

## CIRCUIT DESIGN

**Scanning principle:**
1. Drive ONE row HIGH via 74HC595 cascade
2. Diode on each row prevents ghosting (anode→595, cathode→row)
3. Select column via CD74HC4067 MUX (shared S0-S3)
4. Read ADC from MUX SIG line (IO9 or IO10) with 10K pulldown
5. V_adc = 2.6V × (10K / (R_velostat + 10K))

**595 Cascade Chain:**
```
IO11 (MOSI) → 595_1 SER → 595_2 SER → 595_3 SER → 595_4 SER → 595_5 SER
IO12 (SCK)  → All SRCLK (parallel)
IO13        → All RCLK  (parallel)
595_1 Q0-Q7 → Rows 0-7   → diode → FFC 40-pin pins 1-8
595_2 Q0-Q7 → Rows 8-15  → diode → FFC 40-pin pins 9-16
595_3 Q0-Q7 → Rows 16-23 → diode → FFC 40-pin pins 17-24
595_4 Q0-Q7 → Rows 24-31 → diode → FFC 40-pin pins 25-32
595_5 Q0-Q7 → Rows 32-39 → diode → FFC 40-pin pins 33-40
```

**MUX Channel → FFC 30-pin Mapping:**
```
MUX1 CH0-CH14 (SIG→IO9)  → FFC 30-pin pins 1-15  → Columns 0-14
MUX2 CH0-CH14 (SIG→IO10) → FFC 30-pin pins 16-30 → Columns 15-29
CH15 on each MUX is unused.
```

**74HC595 Wiring (each):**
- Pin 16 VCC → 3.3V, Pin 8 GND → GND
- Pin 10 SRCLR → 3.3V (disable clear)
- Pin 13 OE → GND (enable outputs)
- Pin 14 SER → IO11 (595_1) or prev Q7S (pin 9)
- Pin 11 SRCLK → IO12, Pin 12 RCLK → IO13
- Note: Q0 is pin 15 (not pin 1), Q1 is pin 1, Q7 is pin 7

**SPI Buffer Ordering:**
- SPI sends MSB first, buf[0] = farthest 595 (595_5), buf[4] = closest (595_1)
- `chip = row / 8`, `bit = row % 8`, `buf[NUM_595 - 1 - chip] = (1 << bit)`

**CD74HC4067 Wiring (each):**
- VCC → 3.3V, GND → GND, EN → GND (always enabled)
- S0-S3 → IO4-IO7 (shared between both MUXes)
- MUX1 SIG → IO9 + 10K pulldown to GND
- MUX2 SIG → IO10 + 10K pulldown to GND

## TEST RESULTS

| Test | Description | Status | Notes |
|------|-------------|--------|-------|
| T1 | ESP32 alive | PASS | 2 cores, 16MB flash, 8MB PSRAM confirmed |
| T2 | ADC verify | PASS | Full 12-bit range (0-4095) on IO1 |
| T3 | Single 595 | PASS | 6/6 bit patterns correct |
| T4 | Single MUX | PASS | All 16 channels, zero crosstalk |
| T5 | 1×1 point | PASS | Velostat: OPEN→4Ω, ADC 0→3225 |
| T6 | 2×2 grid | PASS | Diagonal test: no ghost cells |
| T7 | 6×6 grid | PASS | 322 Hz scan rate, bit-bang |
| T8 | 6×6 SPI | PASS | Hardware SPI at 10 MHz |
| T8-diag | 5×595 + 2×MUX verify | PASS | Interactive diagnostic, all 40 rows + both MUXes verified |
| T12 | Full 40×30 | PASS | ASCII + binary serial, GUI working |
| T13 | Optimized 40×30 | PASS | ESP-IDF ADC oneshot, direct GPIO, 17.8 Hz |
| T14 | Corner/edge diagnostic | PASS | All 4 corners verified, row/col mapping correct |

**Velostat Characterization:**
- No press: OPEN circuit (>1MΩ) → ADC ~0
- Light press: 290-430 Ω → ADC ~3180
- Medium press: 98-130 Ω → ADC ~3213
- Hard press: 4-10 Ω → ADC ~3225

## ACTUAL PERFORMANCE (40×30)

```
Scan time: ~56 ms (17.8 Hz)
Bottleneck: ESP32-S3 ADC SAR conversion (~45 μs per read)
Total ADC reads per scan: 1200 (40 rows × 15 ch × 2 MUXes)
1200 × 47 μs ≈ 56 ms

Possible improvement: ADC continuous/DMA mode could reach 35-50 Hz
but adds significant complexity. Not implemented.
```

## SERIAL PROTOCOL

**ASCII mode (t7-t12 default, t13 via 'a' command):**
- Format: `Row%d  |%4d%c|...` per row, `*` marks cells > threshold
- Stats line: `Pressed: %d | Scan time: %lu us (%.1f Hz)`
- Baud: 115200 (native USB ignores baud, always full speed)

**Binary mode (t13 default, t12 via 'b' command):**
- Header: 0xAA 0x55
- Scan time: 4 bytes big-endian (microseconds)
- Grid: 40 × 30 × 2 bytes = 2400 bytes, big-endian, row-major
- Footer: 0xFF 0xFE
- Total frame: 2408 bytes
- Toggle: send 'b' (binary) or 'a' (ASCII) over serial

## DESKTOP GUI (pywebview)

Native desktop application using pywebview (Edge WebView2) + internal WebSocket.

**Features:**
- Transposed display matching physical mat orientation
- Physical PCB pitch aspect ratio (4mm row × 5mm col)
- Canvas-based rendering (1200 cells)
- White→black pressure gradient
- Raw/Filtered mode toggle
- Baseline calibration (averages first 10 scans)
- Adjustable noise floor (default 200, slider 0-1000)
- Hover tooltip with R/C coordinates and values
- Session recording with countdown (raw + filtered + force CSVs)
- Spine calibration: drag-scan with clustering-based auto-detection (L1–L5)
- Force calibration: 5-point IDW gain map (ADC → Newtons per cell)
- Firmware flashing from GUI (esptool.exe, progress bar)
- Settings persistence (JSON)
- Exercise-specific region alerts with audio

**Files:**
- `tests/gui/main.py` — pywebview entry point + ApiHandler bridge
- `tests/gui/backend.py` — Serial, grid processing, sessions, calibration, WebSocket, firmware flash
- `tests/gui/app.html` — Single-file SPA frontend (HTML/CSS/JS)
- `tests/gui/assets/` — Icon, logo, splash screen
- `tests/gui/firmware/` — Pre-compiled .bin files + esptool.exe (for flashing)

**Build pipeline (Windows):**
- `tests/gui/build.bat` — PyInstaller `--onedir` build
- `tests/gui/pressuremat.spec` — PyInstaller spec file
- `tests/gui/installer.iss` — Inno Setup script → `PressureMatSetup.exe`
- User data saves to `%APPDATA%\PressureMat\` when frozen

**Legacy GUI (browser-based):**
- `tests/gui/server.py` — Standalone Python server (serial + WebSocket + HTTP)
- `tests/gui/index.html` — Browser frontend
- Launch: `SERIAL_MODE=binary python3 -u tests/gui/server.py` → http://localhost:8080

## QUICK START — Desktop App (Windows)

```
1. Run PressureMatSetup.exe (or run from source: python tests/gui/main.py)
2. Plug ESP32 into USB — COM port appears automatically
3. If first time: click "Flash Firmware" on connection screen → select port → Flash
4. Select COM port → Connect
5. Heatmap displays live pressure data
```

## QUICK START — Development (WSL)

```bash
# 1. Attach ESP32 to WSL (from Windows PowerShell as admin):
usbipd list                              # find 303a:1001 (native USB port)
usbipd attach --wsl --busid <BUSID>

# 2. In WSL — load driver and fix permissions:
sudo modprobe cdc_acm                    # needed once per WSL boot
sudo chmod 666 /dev/ttyACM0

# 3. Compile and upload (MUST include CDCOnBoot=cdc):
export PATH="$PATH:$(pwd)/bin"
export FQBN="esp32:esp32:esp32s3:PSRAM=opi,FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,CDCOnBoot=cdc"
arduino-cli compile --fqbn "$FQBN" tests/t13_optimized
arduino-cli upload  --fqbn "$FQBN" -p /dev/ttyACM0 tests/t13_optimized

# 4. Launch desktop GUI:
cd tests/gui && python3 main.py

# 5. Or launch legacy browser GUI:
SERIAL_MODE=binary python3 -u tests/gui/server.py
# Open http://localhost:8080 in browser
```

## BUILDING THE INSTALLER (Windows)

```
1. Install Python 3.10+ on Windows
2. cd tests\gui
3. pip install pyserial websockets pywebview
4. Download esptool.exe from GitHub releases → place in firmware\
5. build.bat                          → produces dist\PressureMat\
6. (Optional) Download webview2setup.exe → place next to installer.iss
7. Open installer.iss with Inno Setup → compile → PressureMatSetup.exe
```

## WORKING ENVIRONMENT

- OS: Windows WSL2 (Ubuntu)
- Arduino CLI v1.4.1 (installed to `bin/arduino-cli`)
- ESP32 FQBN: `esp32:esp32:esp32s3:PSRAM=opi,FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,CDCOnBoot=cdc`
- ESP32 core: v3.3.7
- **CDCOnBoot=cdc is REQUIRED** — without it, Serial output goes to UART port (CH343) instead of native USB
- Serial port: `/dev/ttyACM0` (native USB, requires `sudo modprobe cdc_acm` once per WSL boot)
- Python dependencies: `pyserial`, `websockets`, `pywebview`
- Desktop app GUI backend: Edge WebView2 (Windows), GTK/Qt (Linux)
- Firmware flash tool: esptool.exe (standalone, bundled in `tests/gui/firmware/`)
- Build tools: PyInstaller (EXE), Inno Setup (installer)

## KNOWN ISSUES

- **WSL2 USB**: Serial port disappears on disconnect. Re-attach with `usbipd attach --wsl` from PowerShell.
- **cdc_acm module**: Must run `sudo modprobe cdc_acm` once after each WSL restart before the ESP32 shows up as `/dev/ttyACM0`.
- **Permissions reset**: `/dev/ttyACM0` permissions reset on every USB reconnect. Run `sudo chmod 666 /dev/ttyACM0`.
- **Server "Calibrating" stuck**: If server starts before ESP32 finishes booting, binary parser gets confused by boot text. Fix: reset ESP32 before starting server, or just restart server (parser now handles boot text gracefully).
- **Upload fails mid-way**: Native USB sometimes drops during upload. Retry, or hold BOOT button during upload.
- **Velostat pressure unevenness**: Corners respond with higher ADC values than center because flex PCBs bow in the middle. Fix: place a rigid flat surface (acrylic/plywood) under the bottom flex PCB.
- **Row 11 noisy**: Row 11 shows elevated baseline values (~500-1700). Likely a pinched velostat spot or partial short. Baseline calibration compensates.
- **Edge rows/cols occasionally dead**: FFC connector edge pins (pins 1-3 and last 2-3) can lose contact. Re-seat FFC cable firmly with latch fully closed. Also check velostat alignment.
- **Scan rate 17.8 Hz**: Bottleneck is ESP32-S3 ADC conversion time (~45μs/read). ADC continuous/DMA could improve to 35-50 Hz but adds significant complexity.

## INSTRUCTIONS FOR CLAUDE

1. **FQBN must include `CDCOnBoot=cdc`** — this is critical for serial output on native USB
2. Use Arduino CLI at `bin/arduino-cli` — add to PATH: `export PATH="$PATH:$(pwd)/bin"`
3. Serial port is `/dev/ttyACM0` — may need `sudo modprobe cdc_acm` first
4. Serial permissions: `sudo chmod 666 /dev/ttyACM0`
5. For t13 (current firmware): use `SERIAL_MODE=binary` when starting server
6. ESP32-S3 native USB CDC ignores baud rate (always full speed) — baud setting doesn't matter
7. If upload fails, remind user to hold BOOT button
8. Run `python3 -u` (unbuffered) for server to see output immediately
9. After upload, may need to reset ESP32 via DTR toggle before server can read frames
10. GPIO struct in ESP32 core 3.3.7: use `GPIO.out_w1ts = val` (no `.val` member)
