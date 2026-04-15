# PressureMat — 40×30 Pressure Sensor Matrix

A 40×30 lumbar pressure-mat prototype: flex PCB + velostat sensor sandwich, ESP32-S3 firmware that scans the matrix and streams binary frames over USB, and a desktop GUI (pywebview) that renders a live heatmap, records sessions, and applies per-vertebra force calibration.

For full hardware design notes, pin plan, schematic, and wiring details see [`CLAUDE.md`](CLAUDE.md).

---

## ⭐ EDITING GUIDE — what to change, where, and how to flash it

This is the section to read first if you've inherited this codebase and need to make changes.

### The 3 files you will actually edit

| File | What lives here | When to edit |
|---|---|---|
| **`tests/t13_optimized/t13_optimized.ino`** | **ESP32 firmware (C++)** — scanning loop, ADC reads, 595/MUX driving, binary serial protocol | Any change to how the mat is scanned, the sample rate, the wire protocol, pin assignments, or hardware wiring |
| **`tests/gui/backend.py`** | **Python backend** — serial reader, baseline + force calibration, session recording, exercise regions, vertebra position helper, WebSocket server, settings I/O | Changes to data processing, CSV format, calibration math, session/recording behaviour, exercise→vertebra mapping, or anything the firmware sends to the GUI |
| **`tests/gui/app.html`** | **Frontend (single-file HTML/CSS/JS)** — heatmap rendering, trend graph, all modals, settings UI, force-cal wizard | Any UI change: colours, labels, layout, font sizes, new buttons, modal contents, drawing styles |

Plus two thin helpers you'll occasionally touch:
- **`tests/gui/main.py`** — only the `ApiHandler` bridge (one method per backend call). Add a new method here whenever you add a new backend function the JS needs to call via `pywebview.api.<method>`.
- **`tests/gui/pressuremat.spec`** — PyInstaller bundle config. Edit if you add new asset files (e.g. images) or new Python imports the freezer can't autodiscover.

### "I want to change X — where do I edit?"

| You want to… | Edit this | At this symbol |
|---|---|---|
| Change scan rate / ADC settings / GPIO pins | `t13_optimized.ino` | top-of-file `#define`s, `setup()`, `loop()` |
| Change the binary serial frame format | `t13_optimized.ino` **and** `backend.py` | firmware's `Serial.write()` block + `_serial_reader_binary()` parser. Header `0xAA55`, footer `0xFFFE` — keep both sides in sync |
| Move a vertebra default position | `backend.py` **and** `app.html` | `VERTEBRA_DEFAULTS` dict in both files (must stay in sync). Or just edit them at runtime in the Settings modal — they save to `vertebra_settings.json` |
| Change exercise region size (`±3 cells` margin) | `backend.py` | inside `get_exercise_region()` — the literal `margin = 3` |
| Add a new exercise (e.g. "L6 Mobilization") | `backend.py` **and** `app.html` | add to `exercise_targets` dict in `get_exercise_region()`, add `<option>` to `#exercise-select` in the topbar |
| Change baseline calibration length (10 frames) | `backend.py` | `self.cal_target = 10` in `__init__` |
| Change noise-floor default (200) | `backend.py` | `self.noise_floor = 200` in `__init__` |
| Change red/yellow alert thresholds | `app.html` | `let threshHigh = 2500; let threshLow = 1000;` near the top of the `<script>` block |
| Change colours / fonts / spacing | `app.html` | `<style>` block at top (CSS variables `--accent`, `--bg-surface` etc., plus per-class rules) |
| Change cell text size / when text appears | `app.html` | inside `drawGrid()`: `cellW >= 20 && cellH >= 16` gate and `Math.min(13, …)` cap |
| Change WebSocket port range (8765–8774) | `backend.py` | `_run_ws_server()`'s `range(8765, 8775)` |
| Change where session CSVs save | `backend.py` | `self._recordings_dir` in `__init__` |
| Add a new persistent setting | `backend.py` (`update_settings`) **and** `app.html` (`applyLoadedSettings` + `saveSettingsUI`) | use the existing `update_settings({...})` helper so it's race-free |
| Add a new pywebview API method | `main.py` (new `ApiHandler` method) **and** `backend.py` (new function the method wraps) | call from JS as `await pywebview.api.<name>(args)` |
| Bundle a new asset file into the EXE | `pressuremat.spec` | add to `datas=[…]` |

### How to flash new firmware to the ESP32

Two paths — pick whichever fits.

#### Path A: From the desktop app (no developer tools needed)

1. Open PressureMat (the installed EXE, or `python tests/gui/main.py`).
2. On the **connection screen**, click **Flash Firmware**.
3. Pick the COM port → click **Flash**.
4. Wait for the progress bar to complete (~30 s). The device auto-resets, then click **Connect**.

What this flashes: the **bundled** firmware in `tests/gui/firmware/` from when the EXE was built — *not* whatever's currently in `tests/t13_optimized/`. To make the EXE flash a newer firmware, see "Refresh the bundled firmware" below.

#### Path B: From the command line (development)

```bash
# WSL / Linux
export PATH="$PATH:$(pwd)/bin"
export FQBN="esp32:esp32:esp32s3:PSRAM=opi,FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,CDCOnBoot=cdc"

# 1. Edit your firmware
nano tests/t13_optimized/t13_optimized.ino

# 2. Compile
arduino-cli compile --fqbn "$FQBN" tests/t13_optimized

# 3. Upload (hold BOOT button if upload fails partway)
arduino-cli upload --fqbn "$FQBN" -p /dev/ttyACM0 tests/t13_optimized
```

`CDCOnBoot=cdc` is **mandatory** — without it the firmware's serial output goes to the wrong USB port and the GUI sees nothing.

#### Refresh the bundled firmware (so users can flash the new version from the EXE)

```bash
arduino-cli compile --fqbn "$FQBN" --output-dir tests/gui/firmware tests/t13_optimized
# Then rebuild the installer (Windows):
cd tests\gui && build.bat
# Then re-compile the Inno Setup script to produce a new PressureMatSetup.exe
```

The four files the flasher reads from `tests/gui/firmware/` are: `t13_optimized.ino.bin`, `t13_optimized.ino.bootloader.bin`, `t13_optimized.ino.partitions.bin`, `boot_app0.bin`. All four must be present.

### Editing the GUI — fast iteration loop

```bash
cd tests/gui
python3 main.py        # launches the desktop window
```

Edit `app.html` → close the window → relaunch. (Pywebview doesn't hot-reload.)

For pure HTML/CSS tweaks you can also open `app.html` directly in a browser — the WS will fail to connect but you can still inspect layout and styles in DevTools.

### Editing Python backend behaviour — fast iteration loop

```bash
cd tests/gui
python3 main.py
# Edit backend.py, save, close window, relaunch.
```

Don't forget to mirror any new `backend.py` method in `main.py`'s `ApiHandler` if you want the frontend to be able to call it.

---

## Repository layout

```
capstone_code/
├── CLAUDE.md                 # Hardware spec, pin plan, scanning principle, test history
├── README.md                 # ← you are here
├── start.sh                  # Convenience launcher (legacy — see notes below)
├── docs/
│   ├── generate_schematic.py            # KiCad-style schematic generator
│   └── schematic_40x30_pressure_matrix.pdf
├── bin/                      # arduino-cli binary (add to PATH)
└── tests/
    ├── t1_alive…t14_corners  # Bring-up sketches in chronological order
    ├── t13_optimized/        # ← Current production firmware
    │   └── t13_optimized.ino
    └── gui/                  # Desktop application
        ├── main.py           # pywebview entry point + ApiHandler bridge
        ├── backend.py        # Serial reader, scan processing, sessions, calibration, WS server
        ├── app.html          # Single-file HTML/CSS/JS frontend
        ├── server.py         # Legacy browser-based GUI (HTTP + WS)
        ├── index.html        # Legacy browser frontend
        ├── assets/           # Icon, logo, splash
        ├── firmware/         # Pre-compiled .bin + esptool.exe (bundled into installer)
        ├── recordings/       # Session CSVs (created at runtime)
        ├── pressuremat.spec  # PyInstaller spec
        ├── build.bat         # Windows build script
        └── installer.iss     # Inno Setup script → PressureMatSetup.exe
```

---

## Hardware (summary)

- **MCU:** ESP32-S3-WROOM-1 N16R8 (use the **native USB** port, VID:PID `303a:1001`)
- **Row drivers:** 5× SN74HC595 cascaded shift registers + 40× 1N4148 diodes (anti-ghosting)
- **Column readers:** 2× CD74HC4067 16-channel multiplexers, ADC pulldowns 10 kΩ
- **Sensor stack:** 40-pin flex PCB (rows, bottom) → velostat sheet → 30-pin flex PCB (columns, top)
- **Cell pitch:** 4 mm (rows) × 5 mm (columns)
- **9 GPIO total:** see the full pin table in `CLAUDE.md`

Scan principle: drive one row HIGH via the 595 chain, sweep all 30 columns through the two MUXes while reading ADC1_CH8/CH9, repeat for all 40 rows. Achieves ~17.8 Hz at the 40×30 grid.

---

## GUI feature overview

| Feature | Purpose | Backend (`backend.py`) | Frontend (`app.html`) |
|---|---|---|---|
| **Live heatmap** | 40×30 colour render of raw or filtered ADC | `_serial_reader_binary`, `_apply_filter`, WS sender | `drawGrid`, `updateDisplay` |
| **Baseline calibration** | Captures 10 frames, subtracts the average from every later scan. Suppresses output until done. | `start_calibration`, `_process_full_scan` | "Calibrate Baseline" button, `#calibrating-overlay` |
| **Raw / Filtered toggle** | Show raw ADC vs noise-floored, baseline-subtracted values | — | `setMode` |
| **Noise-floor slider** | Per-cell threshold; values below shown as 0 | `noise_floor` field, WS `set_noise_floor` action | `setNoiseFloor`, slider in topbar |
| **Vertebra positions (L1C–L5C)** | Single source of truth for L1–L5 locations. Hardcoded defaults, editable in settings modal, persisted to `vertebra_settings.json`. | `VERTEBRA_DEFAULTS`, `load/save/reset_vertebra_settings`, `_vertebra_center` | `vertebraSettings`, `vertebraCenter`, settings modal section, `drawVertebraRegions` |
| **Exercise regions (L1–L5 Mobilization)** | Dashed yellow box around the configured vertebra ±3 cells, with red/yellow/green threshold colouring inside | `get_exercise_region` | Region drawing inside `drawGrid`, exercise dropdown |
| **Audio alerts** | Beep when any cell in the active exercise region exceeds the high threshold; mute toggle | — | `handleAlert`, `playBeep`, `toggleMute` |
| **Session recording** | Captures raw + filtered grids at scan rate; on stop writes timestamped CSVs to `recordings/` | `start_session`, `stop_session`, `_write_csvs` | `toggleSession`, countdown, badges, timer |
| **Session replay** | Pick a recording, scrub & play back the heatmap | `list_recordings`, `load_recording` | `openReplayPicker`, `startReplay`, `renderReplayFrame` |
| **Trend graph** | Bottom-panel time-series of either peak ADC, exercise-region peak, total force (when force-cal enabled), or a pinned vertebra | — | `updateGraph`, `drawGraph`, tracking-label cycle |
| **Force calibration** | Per-vertebra cubic polynomial `F = a₀+a₁·x+a₂·x²+a₃·x³` from 2–4+ known weights → ADC samples; stored in `force_calibration.json` and applied per-cell using nearest configured vertebra | `_polyfit3`, `compute_force_polynomial`, `_save_poly_force_calibration`, `load_poly_force_calibration` | Force-cal modal (`openForceCalibration`, `captureForcePointNew`, `doneCapturing`, `drawForceCurvePreview`), `adcToForceNum`, `getNearestCalibratedVertebra` |
| **Cell text overlay** | Per-cell ADC or Newton labels (when zoom is large enough) | — | `drawGrid`'s text branch, `cellDisplayMode` |
| **Settings persistence** | All UI prefs in `settings.json` under one atomic lock | `_settings_lock`, `load_settings`, `save_settings`, `update_settings` | `applyLoadedSettings`, `saveSettingsUI` |
| **Firmware flash** | Disconnects, runs bundled `esptool.exe` against the bundled `.bin`s, reports progress | `get_firmware_info`, `start_flash`, `_do_flash`, `get_flash_progress` | Flash modal on connection screen |
| **Debug mode** | Generates fake sinusoidal pressure blobs for development without ESP32 | `connect_debug`, `_debug_data_generator` | "Debug Mode" button on connection screen |
| **WebSocket bind** | Tries ports 8765–8774; raises a hard error if all taken so the UI never starts blank | `_run_ws_server`, `start_ws_server` | Tk error dialog from `main.py` |

Removed in the latest revision: drag-scan spine calibration. `vertebra_settings` is now the only source of truth for L1–L5 — see `_vertebra_center` (Python) and `vertebraCenter` (JS).

### Persisted files

All under `tests/gui/` in dev, or under `%APPDATA%\PressureMat\` when installed.

| File | What it stores |
|---|---|
| `settings.json` | UI prefs: noise floor, last port, thresholds, axis labels, force-cal enabled flag |
| `vertebra_settings.json` | Per-vertebra `{row, col, ext}` for L1C..L5C |
| `force_calibration.json` | Per-vertebra polynomial coefficients + raw cal points |
| `recordings/session_YYYYMMDD_HHMMSS_*.csv` | Raw, filtered, optional force CSVs per session |
| `pressuremat.log` | Application log |
| `spine_calibration.json` | **Obsolete** — left on disk if present from older builds; ignored |

### Important functions to know

- **Add a new vertebra:** edit `VERTEBRA_DEFAULTS` in both `backend.py` (Python) and `app.html` (JS) — keep the keys in sync (`L1C..L5C`).
- **Add a new exercise:** add an entry to the `exercise_targets` dict in `backend.get_exercise_region`, plus the `<option>` in `app.html`'s `#exercise-select`.
- **Change region size:** the ±3 margin is a literal in `get_exercise_region`. Edit there.
- **Tweak the binary frame format:** see the `_serial_reader_binary` parser (header 0xAA55, 4-byte big-endian scan time, 40×30×2 byte grid, footer 0xFFFE) and mirror any change in the firmware.

---

## Quick start

### Run the GUI from source (Linux / WSL)

```bash
# One-time
cd tests/gui
pip3 install -r requirements.txt   # pyserial, websockets, pywebview

# Each session
sudo modprobe cdc_acm                # only after a WSL restart
sudo chmod 666 /dev/ttyACM0          # resets on every reconnect
python3 main.py
```

### Run the GUI from source (Windows)

```bat
cd tests\gui
pip install -r requirements.txt
python main.py
```

### Run the legacy browser GUI

```bash
cd tests/gui
SERIAL_MODE=binary python3 -u server.py
# Open http://localhost:8080
```

---

## Building & flashing the firmware

The current production sketch lives in `tests/t13_optimized/`.

### Compile + upload from WSL

```bash
export PATH="$PATH:$(pwd)/bin"
export FQBN="esp32:esp32:esp32s3:PSRAM=opi,FlashSize=16M,PartitionScheme=app3M_fat9M_16MB,CDCOnBoot=cdc"

arduino-cli compile --fqbn "$FQBN" tests/t13_optimized
arduino-cli upload  --fqbn "$FQBN" -p /dev/ttyACM0 tests/t13_optimized
```

`CDCOnBoot=cdc` is **required** — without it, serial output goes to the wrong USB port.

If upload fails partway, hold the BOOT button on the ESP32 and retry.

### Export pre-compiled binaries (for the installer's flash feature)

The desktop app's "Flash Firmware" button runs `esptool.exe` against four bundled files in `tests/gui/firmware/`:

```
tests/gui/firmware/
├── esptool.exe                              ← from https://github.com/espressif/esptool/releases
├── boot_app0.bin                            ← from Arduino ESP32 core
├── t13_optimized.ino.bootloader.bin
├── t13_optimized.ino.partitions.bin
└── t13_optimized.ino.bin
```

To refresh them after a firmware change:

```bash
arduino-cli compile --fqbn "$FQBN" --output-dir tests/gui/firmware tests/t13_optimized
```

(or in Arduino IDE: **Sketch → Export Compiled Binary**, then copy from `tests/t13_optimized/build/...` into `tests/gui/firmware/`).

---

## Building the Windows installer

```bat
cd tests\gui
pip install pyinstaller pyserial websockets pywebview
build.bat                                    :: → dist\PressureMat\
:: Optional: drop webview2setup.exe next to installer.iss
:: Open installer.iss in Inno Setup → Compile → PressureMatSetup.exe
```

The EXE bundles **whatever firmware `.bin`s are in `tests/gui/firmware/` at build time** — refresh them first if you want users to flash a newer firmware.

End-user install:
1. Run `PressureMatSetup.exe` (installs WebView2 runtime if missing).
2. Plug in ESP32 → COM port appears.
3. First-time only: **Flash Firmware** on the connection screen.
4. **Connect** → live heatmap.

User data lives at `%APPDATA%\PressureMat\` (settings, vertebra config, force cal, recordings, log).

---

## Useful arduino-cli commands

```bash
arduino-cli board list                       # see attached boards
arduino-cli core install esp32:esp32         # install ESP32 core (one-time)
arduino-cli core update-index
arduino-cli monitor -p /dev/ttyACM0 -c baudrate=115200,dtr=on   # raw serial monitor
```

---

## WSL2 USB attach (Windows host)

```powershell
# In Windows PowerShell as admin:
usbipd list                           # find 303a:1001 (native USB port)
usbipd attach --wsl --busid <BUSID>
```

If `/dev/ttyACM0` doesn't appear inside WSL, run `sudo modprobe cdc_acm` once per WSL boot.

---

## Serial protocol (binary, t13)

| Field | Bytes | Notes |
|---|---|---|
| Header | 2 | `0xAA 0x55` |
| Scan time (µs) | 4 | big-endian uint32 |
| Grid | 40×30×2 = 2400 | big-endian uint16, row-major |
| Footer | 2 | `0xFF 0xFE` |
| **Total** | **2408** | per frame |

ASCII mode is also supported (toggle by sending `a` / `b` over serial). The GUI uses binary mode.

---

## Known issues / gotchas

- `/dev/ttyACM0` permissions reset on every reconnect → re-run `sudo chmod 666`.
- Native USB sometimes drops mid-upload → retry, hold BOOT.
- Velostat corners read higher than centre → place a rigid backing under the bottom flex PCB.
- Row 11 has an elevated baseline (~500–1700 ADC) — baseline calibration compensates.
- Edge FFC pins occasionally lose contact → re-seat the FFC, latch fully closed.
- Scan rate caps at ~17.8 Hz due to ESP32-S3 ADC SAR conversion time. ADC continuous/DMA mode could push ~35–50 Hz at the cost of significant complexity.
- `start.sh` predates `t13_optimized` — it still references the `tests/t7_6x6` sketch and the legacy `server.py`. Treat it as historical; use the commands in this README directly.

---

## License / Authors

Capstone Team — see `CLAUDE.md` and Git history for contributors.
