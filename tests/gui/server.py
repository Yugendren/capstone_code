#!/usr/bin/env python3
"""Pressure Matrix GUI - WebSocket server that reads ESP32 serial data.

Supports both 6x6 (ASCII) and 40x30 (ASCII or binary) modes.
Auto-detects grid size from serial data.
Binary protocol: 0xAA 0x55 [4 bytes scanTime] [ROWS*COLS*2 bytes] 0xFF 0xFE
"""

import asyncio
import json
import math
import os
import random
import re
import struct
import sys
import threading
import time as _time
import websockets

# Debug mode: run without ESP32 using fake data
DEBUG_MODE = "--debug" in sys.argv or os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")

try:
    import serial
except ImportError:
    if not DEBUG_MODE:
        raise
    serial = None  # Not needed in debug mode

SERIAL_PORT = os.environ.get("SERIAL_PORT", "/dev/ttyACM0")
BAUD_RATE = int(os.environ.get("BAUD_RATE", "115200"))

# ── Vertebra Settings ────────────────────────────────────────────
VERTEBRA_DEFAULTS = {
    "L1C": {"row": 4, "col": 5, "ext": 1},
    "L2C": {"row": 7, "col": 5, "ext": 1},
    "L3C": {"row": 9, "col": 5, "ext": 2},
    "L4C": {"row": 13, "col": 5, "ext": 2},
    "L5C": {"row": 17, "col": 5, "ext": 2},
}
vertebra_settings_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "vertebra_settings.json"
)
vertebra_settings = {}


def load_vertebra_settings():
    """Load vertebra settings from JSON file, or use defaults."""
    global vertebra_settings
    if os.path.exists(vertebra_settings_path):
        try:
            with open(vertebra_settings_path) as f:
                vertebra_settings = json.load(f)
            print(f"Vertebra settings loaded from {vertebra_settings_path}")
            return
        except Exception as e:
            print(f"Failed to load vertebra settings: {e}")
    vertebra_settings = {k: dict(v) for k, v in VERTEBRA_DEFAULTS.items()}
    print("Using default vertebra settings")


def save_vertebra_settings_to_disk(data):
    """Write vertebra settings to JSON file."""
    global vertebra_settings
    vertebra_settings = data
    with open(vertebra_settings_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Vertebra settings saved to {vertebra_settings_path}")

# Grid dimensions — auto-detected or set via env
ROWS = int(os.environ.get("ROWS", "40"))
COLS = int(os.environ.get("COLS", "30"))

# Raw grid from ESP32
grid_raw = [[0]*COLS for _ in range(ROWS)]
# Filtered grid (baseline subtracted, noise removed)
grid_filtered = [[0]*COLS for _ in range(ROWS)]
# Baseline captured at startup or on calibrate
baseline = [[0]*COLS for _ in range(ROWS)]
# Accumulator for calibration averaging
cal_accum = [[0]*COLS for _ in range(ROWS)]
cal_count = 0
cal_target = 10
calibrating = True

scan_hz = 0.0
pressed = 0
noise_floor = 200
lock = threading.Lock()
grid_size_detected = False


def resize_grids(rows, cols):
    """Resize all grid arrays to new dimensions."""
    global ROWS, COLS, grid_raw, grid_filtered, baseline, cal_accum
    global cal_count, calibrating, grid_size_detected
    ROWS = rows
    COLS = cols
    grid_raw = [[0]*COLS for _ in range(ROWS)]
    grid_filtered = [[0]*COLS for _ in range(ROWS)]
    baseline = [[0]*COLS for _ in range(ROWS)]
    cal_accum = [[0]*COLS for _ in range(ROWS)]
    cal_count = 0
    calibrating = True
    grid_size_detected = True
    print(f"Grid resized to {ROWS}x{COLS}")


def apply_filter():
    """Subtract baseline and apply noise floor."""
    global grid_filtered, pressed
    p = 0
    for r in range(ROWS):
        for c in range(COLS):
            val = grid_raw[r][c] - baseline[r][c]
            if val < noise_floor:
                val = 0
            grid_filtered[r][c] = val
            if val > 0:
                p += 1
    pressed = p


def process_full_scan():
    """Called when a full scan is received. Handles calibration and filtering."""
    global cal_count, calibrating, baseline
    if calibrating:
        for r in range(ROWS):
            for c in range(COLS):
                cal_accum[r][c] += grid_raw[r][c]
        cal_count += 1
        if cal_count >= cal_target:
            for r in range(ROWS):
                for c in range(COLS):
                    baseline[r][c] = cal_accum[r][c] // cal_count
            calibrating = False
            print(f"Baseline captured ({cal_count} scans averaged)")
    apply_filter()


def start_calibration():
    """Reset calibration to capture new baseline."""
    global cal_accum, cal_count, calibrating
    cal_accum = [[0]*COLS for _ in range(ROWS)]
    cal_count = 0
    calibrating = True


def serial_reader_ascii():
    """Read serial data line-by-line (ASCII mode for t7-t11)."""
    global grid_raw, scan_hz
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    row_pattern = re.compile(r"Row(\d+)\s+\|(.+)\|")
    stat_pattern = re.compile(r"Pressed:\s+(\d+)\s+\|.*?([\d.]+)\s+Hz")
    rows_received = set()

    while True:
        try:
            line = ser.readline().decode("utf-8", errors="replace").strip()
            m = row_pattern.match(line)
            if m:
                row_idx = int(m.group(1))
                cells = m.group(2).split("|")
                if row_idx < ROWS and len(cells) >= COLS:
                    with lock:
                        for c in range(COLS):
                            val_str = cells[c].strip().rstrip("*")
                            try:
                                grid_raw[row_idx][c] = int(val_str)
                            except ValueError:
                                pass
                    rows_received.add(row_idx)

                    if len(rows_received) == ROWS:
                        rows_received.clear()
                        with lock:
                            process_full_scan()

            m2 = stat_pattern.search(line)
            if m2:
                with lock:
                    scan_hz = float(m2.group(2))
        except serial.SerialException:
            print("Serial disconnected, retrying...")
            try:
                ser.close()
            except Exception:
                pass
            import time
            time.sleep(2)
            try:
                ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
                print("Serial reconnected")
            except Exception:
                pass
        except Exception:
            pass


def serial_reader_binary():
    """Read binary frames from serial (for t12/t13)."""
    global grid_raw, scan_hz
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    HEADER = bytes([0xAA, 0x55])
    FOOTER = bytes([0xFF, 0xFE])
    frame_size = 2 + 4 + ROWS * COLS * 2 + 2
    buf = bytearray()
    frame_count = 0

    print(f"Binary reader: expecting {frame_size} byte frames, listening...", flush=True)

    while True:
        try:
            waiting = ser.in_waiting or 1
            data = ser.read(waiting)
            if not data:
                continue
            buf.extend(data)

            # Prevent buffer from growing unbounded
            if len(buf) > frame_size * 4:
                buf = buf[-(frame_size * 2):]

            while True:
                header_pos = buf.find(HEADER)
                if header_pos == -1:
                    # Keep last byte in case it's 0xAA
                    if len(buf) > 1:
                        buf = buf[-1:]
                    break
                if header_pos > 0:
                    buf = buf[header_pos:]

                if len(buf) < frame_size:
                    break

                # Verify footer before accepting frame
                footer = buf[frame_size - 2:frame_size]
                if footer != FOOTER:
                    # False header — skip past it and try next
                    buf = buf[2:]
                    continue

                scan_time_us = struct.unpack(">I", buf[2:6])[0]
                if scan_time_us > 0:
                    with lock:
                        scan_hz = 1000000.0 / scan_time_us

                offset = 6
                with lock:
                    for r in range(ROWS):
                        for c in range(COLS):
                            grid_raw[r][c] = struct.unpack(">H", buf[offset:offset+2])[0]
                            offset += 2
                    process_full_scan()

                frame_count += 1
                if frame_count <= 3 or frame_count % 100 == 0:
                    print(f"Frame {frame_count}: {scan_hz:.1f} Hz", flush=True)

                buf = buf[frame_size:]

        except serial.SerialException:
            print("Serial disconnected, retrying...")
            try:
                ser.close()
            except Exception:
                pass
            import time
            time.sleep(2)
            try:
                ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
                print("Serial reconnected")
            except Exception:
                pass
        except Exception as e:
            print(f"Parse error: {e}")


def debug_data_generator():
    """Generate fake pressure data for GUI testing without ESP32."""
    global grid_raw, scan_hz
    scan_hz = 17.8
    t = 0

    print("DEBUG MODE: generating fake pressure data")
    while True:
        t += 1
        with lock:
            for r in range(ROWS):
                for c in range(COLS):
                    base = 100
                    if t > 15:  # After calibration settles
                        # Blob 1: slow moving
                        cx1 = 20 + 12 * math.sin(t * 0.015)
                        cy1 = 15 + 8 * math.cos(t * 0.02)
                        d1 = math.sqrt((r - cx1) ** 2 + (c - cy1) ** 2)
                        blob1 = 2500 * math.exp(-d1 * d1 / 18)
                        # Blob 2: faster, smaller
                        cx2 = 10 + 8 * math.sin(t * 0.04 + 1)
                        cy2 = 20 + 6 * math.cos(t * 0.05 + 2)
                        d2 = math.sqrt((r - cx2) ** 2 + (c - cy2) ** 2)
                        blob2 = 1500 * math.exp(-d2 * d2 / 12)
                        grid_raw[r][c] = min(4095, int(base + blob1 + blob2 + random.randint(0, 30)))
                    else:
                        grid_raw[r][c] = base + random.randint(0, 20)
            process_full_scan()
        _time.sleep(0.056)


def serial_reader():
    """Auto-select reader based on mode and debug flag."""
    if DEBUG_MODE:
        debug_data_generator()
        return
    mode = os.environ.get("SERIAL_MODE", "ascii").lower()
    if mode == "binary":
        print("Using binary serial parser")
        serial_reader_binary()
    else:
        print("Using ASCII serial parser")
        serial_reader_ascii()


async def ws_handler(websocket):
    """Send grid data to browser and handle commands."""
    async def sender():
        while True:
            with lock:
                data = {
                    "type": "frame",
                    "rows": ROWS,
                    "cols": COLS,
                    "raw": [row[:] for row in grid_raw],
                    "grid": [row[:] for row in grid_filtered],
                    "baseline": [row[:] for row in baseline],
                    "hz": scan_hz,
                    "pressed": pressed,
                    "calibrating": calibrating,
                    "noise_floor": noise_floor,
                    "vertebra_settings": dict(vertebra_settings),
                }
            await websocket.send(json.dumps(data))
            await asyncio.sleep(0.033)

    async def receiver():
        global noise_floor
        async for msg in websocket:
            cmd = json.loads(msg)
            action = cmd.get("action")
            if action == "calibrate":
                with lock:
                    start_calibration()
                print("Recalibrating...")
            elif action == "set_noise_floor":
                with lock:
                    noise_floor = int(cmd["value"])
                print(f"Noise floor set to {noise_floor}")
            elif action == "save_vertebra_settings":
                try:
                    save_vertebra_settings_to_disk(cmd["settings"])
                    await websocket.send(json.dumps({
                        "type": "vertebra_settings_saved",
                        "settings": vertebra_settings,
                    }))
                except Exception as e:
                    await websocket.send(json.dumps({
                        "type": "vertebra_settings_error",
                        "error": str(e),
                    }))
            elif action == "reset_vertebra_settings":
                defaults = {k: dict(v) for k, v in VERTEBRA_DEFAULTS.items()}
                save_vertebra_settings_to_disk(defaults)
                await websocket.send(json.dumps({
                    "type": "vertebra_settings_reset",
                    "settings": vertebra_settings,
                }))

    await asyncio.gather(sender(), receiver())


async def main():
    load_vertebra_settings()
    t = threading.Thread(target=serial_reader, daemon=True)
    t.start()
    if DEBUG_MODE:
        print("DEBUG MODE — no serial port needed")
    else:
        print(f"Serial reader started on {SERIAL_PORT} @ {BAUD_RATE} baud")
    print(f"Grid size: {ROWS}x{COLS} ({ROWS*COLS} cells)")
    print("WebSocket server on ws://localhost:8765")
    print("Open http://localhost:8080 in your browser")

    import http.server
    import functools
    gui_dir = os.path.dirname(os.path.abspath(__file__))
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler,
        directory=gui_dir,
    )
    httpd = http.server.HTTPServer(("0.0.0.0", 8080), handler)
    http_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    http_thread.start()
    print("HTTP server on http://localhost:8080")

    async with websockets.serve(ws_handler, "0.0.0.0", 8765):
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
