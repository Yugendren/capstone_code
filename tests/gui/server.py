#!/usr/bin/env python3
"""6x6 Pressure Matrix GUI - WebSocket server that reads ESP32 serial data."""

import asyncio
import json
import os
import re
import threading
import serial
import websockets

SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 115200
ROWS = 6
COLS = 6

# Raw grid from ESP32
grid_raw = [[0]*COLS for _ in range(ROWS)]
# Filtered grid (baseline subtracted, noise removed)
grid_filtered = [[0]*COLS for _ in range(ROWS)]
# Baseline captured at startup or on calibrate
baseline = [[0]*COLS for _ in range(ROWS)]
# Accumulator for calibration averaging
cal_accum = [[0]*COLS for _ in range(ROWS)]
cal_count = 0
cal_target = 10  # number of scans to average for baseline
calibrating = True

scan_hz = 0.0
pressed = 0
noise_floor = 200  # values below this (after baseline sub) are zeroed
lock = threading.Lock()


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


def start_calibration():
    """Reset calibration to capture new baseline."""
    global cal_accum, cal_count, calibrating
    cal_accum = [[0]*COLS for _ in range(ROWS)]
    cal_count = 0
    calibrating = True


def serial_reader():
    """Read serial data and parse grid values."""
    global grid_raw, scan_hz, cal_count, calibrating, baseline
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    row_pattern = re.compile(r"Row(\d)\s+\|(.+)\|")
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

                    # When full scan received
                    if len(rows_received) == ROWS:
                        rows_received.clear()
                        with lock:
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

            m2 = stat_pattern.search(line)
            if m2:
                with lock:
                    scan_hz = float(m2.group(2))
        except Exception:
            pass


async def ws_handler(websocket):
    """Send grid data to browser and handle commands."""
    async def sender():
        while True:
            with lock:
                data = {
                    "raw": [row[:] for row in grid_raw],
                    "grid": [row[:] for row in grid_filtered],
                    "baseline": [row[:] for row in baseline],
                    "hz": scan_hz,
                    "pressed": pressed,
                    "calibrating": calibrating,
                    "noise_floor": noise_floor,
                }
            await websocket.send(json.dumps(data))
            await asyncio.sleep(0.033)

    async def receiver():
        global noise_floor
        async for msg in websocket:
            cmd = json.loads(msg)
            if cmd.get("action") == "calibrate":
                with lock:
                    start_calibration()
                print("Recalibrating...")
            elif cmd.get("action") == "set_noise_floor":
                with lock:
                    noise_floor = int(cmd["value"])
                print(f"Noise floor set to {noise_floor}")

    await asyncio.gather(sender(), receiver())


async def main():
    t = threading.Thread(target=serial_reader, daemon=True)
    t.start()
    print("Serial reader started on", SERIAL_PORT)
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
