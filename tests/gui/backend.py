"""PressureMat backend — serial reader, grid processing, sessions, calibration, WebSocket."""

import asyncio
import csv
import json
import logging
import math
import os
import random
import struct
import subprocess
import sys
import threading
import time
from datetime import datetime

import serial
import serial.tools.list_ports
import websockets

log = logging.getLogger("pressuremat")


class PressureBackend:
    def __init__(self, rows=40, cols=30):
        self.ROWS = rows
        self.COLS = cols

        # Grid state
        self.grid_raw = [[0] * cols for _ in range(rows)]
        self.grid_filtered = [[0] * cols for _ in range(rows)]
        self.baseline = [[0] * cols for _ in range(rows)]
        self.cal_accum = [[0] * cols for _ in range(rows)]
        self.cal_count = 0
        self.cal_target = 10
        self.calibrating = True

        self.scan_hz = 0.0
        self.pressed = 0
        self.noise_floor = 200
        self.lock = threading.Lock()

        # Serial
        self.ser = None
        self.connected = False
        self.port_name = ""
        self._reader_thread = None
        self._stop_event = threading.Event()

        # Session recording
        self.session_active = False
        self.session_exercise = ""
        self.session_start_time = 0.0
        self.session_frames = []  # list of (timestamp_ms, flat_grid_raw, flat_grid_filtered)

        # Spine calibration
        self.spine_markers = {}  # {'L1': [row, col], ...}
        self._spine_cal_label = None
        self._spine_cal_frames = []
        self._spine_calibrating = False

        # Force calibration
        self.force_gain_map = None          # 40×30 list of floats, or None
        self._force_cal_frames = []
        self._force_calibrating = False

        # Exercise region
        self.exercise_region = None  # (rmin, rmax, cmin, cmax) or None

        # WebSocket
        self.ws_port = 0
        self._ws_server = None
        self._ws_clients = set()
        self._loop = None

        # Paths — split resource (read-only, bundled) vs data (writable, persistent)
        if getattr(sys, "frozen", False):
            self._resource_dir = sys._MEIPASS
            self._data_dir = os.path.join(
                os.environ.get("APPDATA", os.path.dirname(sys.executable)),
                "PressureMat",
            )
        else:
            self._resource_dir = os.path.dirname(os.path.abspath(__file__))
            self._data_dir = self._resource_dir

        os.makedirs(self._data_dir, exist_ok=True)

        self._recordings_dir = os.path.join(self._data_dir, "recordings")
        self._cal_path = os.path.join(self._data_dir, "spine_calibration.json")
        self._force_cal_path = os.path.join(self._data_dir, "force_calibration.json")
        self._settings_path = os.path.join(self._data_dir, "settings.json")
        self._vertebra_settings_path = os.path.join(self._data_dir, "vertebra_settings.json")
        self._firmware_dir = os.path.join(self._resource_dir, "firmware")

        # Firmware flash state
        self._flash_progress = {"status": "idle", "message": "", "percent": 0}
        self._flash_thread = None

        # Vertebra settings
        self.VERTEBRA_DEFAULTS = {
            "L1C": {"row": 4, "col": 5, "ext": 1},
            "L2C": {"row": 7, "col": 5, "ext": 1},
            "L3C": {"row": 9, "col": 5, "ext": 2},
            "L4C": {"row": 13, "col": 5, "ext": 2},
            "L5C": {"row": 17, "col": 5, "ext": 2},
        }
        self.vertebra_settings = {}

        # Debug mode
        self._debug_mode = False

        # Load saved calibrations
        self.load_spine_calibration()
        self.load_force_calibration()
        self.load_vertebra_settings()

    # ── Serial ──────────────────────────────────────────────────────

    def list_ports(self):
        """List available serial ports, ESP32 devices first."""
        ports = []
        for p in serial.tools.list_ports.comports():
            is_esp = "303A:1001" in (p.hwid or "").upper()
            ports.append({
                "port": p.device,
                "description": p.description or p.device,
                "hwid": p.hwid or "",
                "is_esp32": is_esp,
            })
        # Sort ESP32 devices to top
        ports.sort(key=lambda x: (not x["is_esp32"], x["port"]))
        return ports

    def connect(self, port, baud=115200):
        """Open COM port and start binary reader thread."""
        if self.connected:
            self.disconnect()
        try:
            self.ser = serial.Serial(port, baud, timeout=1)
            self.connected = True
            self.port_name = port
            self._stop_event.clear()

            # Reset calibration
            self.start_calibration()

            # Start reader thread
            self._reader_thread = threading.Thread(
                target=self._serial_reader_binary, daemon=True
            )
            self._reader_thread.start()
            log.info("Connected to %s", port)
            return {"success": True, "message": f"Connected to {port}"}
        except Exception as e:
            log.error("Connect failed: %s", e)
            self.connected = False
            return {"success": False, "message": str(e)}

    def disconnect(self):
        """Close serial port and stop reader thread."""
        self._stop_event.set()
        self.connected = False
        self._debug_mode = False
        self.port_name = ""
        if self.ser:
            try:
                self.ser.close()
            except Exception:
                pass
            self.ser = None
        log.info("Disconnected")
        return {"success": True}

    def connect_debug(self):
        """Start debug mode with fake data — no serial required."""
        if self.connected:
            self.disconnect()
        self.connected = True
        self._debug_mode = True
        self.port_name = "DEBUG"
        self._stop_event.clear()
        self.start_calibration()
        self._reader_thread = threading.Thread(
            target=self._debug_data_generator, daemon=True
        )
        self._reader_thread.start()
        log.info("Debug mode started — generating fake data")
        return {"success": True, "message": "Debug mode active"}

    def _debug_data_generator(self):
        """Generate fake pressure data for testing without ESP32."""
        t = 0
        log.info("Debug data generator running")
        while not self._stop_event.is_set():
            t += 1
            with self.lock:
                self.scan_hz = 17.8
                for r in range(self.ROWS):
                    for c in range(self.COLS):
                        base = 100
                        if t > 15:
                            cx1 = 20 + 12 * math.sin(t * 0.015)
                            cy1 = 15 + 8 * math.cos(t * 0.02)
                            d1 = math.sqrt((r - cx1) ** 2 + (c - cy1) ** 2)
                            blob1 = 2500 * math.exp(-d1 * d1 / 18)
                            cx2 = 10 + 8 * math.sin(t * 0.04 + 1)
                            cy2 = 20 + 6 * math.cos(t * 0.05 + 2)
                            d2 = math.sqrt((r - cx2) ** 2 + (c - cy2) ** 2)
                            blob2 = 1500 * math.exp(-d2 * d2 / 12)
                            self.grid_raw[r][c] = min(
                                4095, int(base + blob1 + blob2 + random.randint(0, 30))
                            )
                        else:
                            self.grid_raw[r][c] = base + random.randint(0, 20)
                self._process_full_scan()
            time.sleep(0.056)
        log.info("Debug data generator exiting")

    def _serial_reader_binary(self):
        """Binary frame parser — runs in its own thread."""
        HEADER = bytes([0xAA, 0x55])
        FOOTER = bytes([0xFF, 0xFE])
        frame_size = 2 + 4 + self.ROWS * self.COLS * 2 + 2  # 2408
        buf = bytearray()
        frame_count = 0

        log.info("Binary reader: expecting %d byte frames", frame_size)

        while not self._stop_event.is_set():
            try:
                if not self.ser or not self.ser.is_open:
                    break
                waiting = self.ser.in_waiting or 1
                data = self.ser.read(waiting)
                if not data:
                    continue
                buf.extend(data)

                # Prevent buffer from growing unbounded
                if len(buf) > frame_size * 4:
                    buf = buf[-(frame_size * 2):]

                while True:
                    header_pos = buf.find(HEADER)
                    if header_pos == -1:
                        if len(buf) > 1:
                            buf = buf[-1:]
                        break
                    if header_pos > 0:
                        buf = buf[header_pos:]

                    if len(buf) < frame_size:
                        break

                    # Verify footer
                    footer = buf[frame_size - 2 : frame_size]
                    if footer != FOOTER:
                        buf = buf[2:]
                        continue

                    scan_time_us = struct.unpack(">I", buf[2:6])[0]

                    with self.lock:
                        if scan_time_us > 0:
                            self.scan_hz = 1_000_000.0 / scan_time_us

                        offset = 6
                        for r in range(self.ROWS):
                            for c in range(self.COLS):
                                self.grid_raw[r][c] = struct.unpack(
                                    ">H", buf[offset : offset + 2]
                                )[0]
                                offset += 2
                        self._process_full_scan()

                    frame_count += 1
                    if frame_count <= 3 or frame_count % 500 == 0:
                        log.info("Frame %d: %.1f Hz", frame_count, self.scan_hz)

                    buf = buf[frame_size:]

            except serial.SerialException:
                log.warning("Serial disconnected")
                self.connected = False
                break
            except Exception as e:
                log.error("Parse error: %s", e)

        log.info("Reader thread exiting")

    # ── Grid Processing (called with lock held) ─────────────────────

    def _process_full_scan(self):
        """Handle calibration and filtering for a complete scan."""
        if self.calibrating:
            for r in range(self.ROWS):
                for c in range(self.COLS):
                    self.cal_accum[r][c] += self.grid_raw[r][c]
            self.cal_count += 1
            if self.cal_count >= self.cal_target:
                for r in range(self.ROWS):
                    for c in range(self.COLS):
                        self.baseline[r][c] = self.cal_accum[r][c] // self.cal_count
                self.calibrating = False
                log.info("Baseline captured (%d scans averaged)", self.cal_count)
        self._apply_filter()

        # Session recording
        if self.session_active:
            ts = int((time.time() - self.session_start_time) * 1000)
            raw_flat = []
            filt_flat = []
            for r in range(self.ROWS):
                raw_flat.extend(self.grid_raw[r])
                filt_flat.extend(self.grid_filtered[r])
            self.session_frames.append((ts, raw_flat, filt_flat))

        # Spine calibration capture
        if self._spine_calibrating:
            filt_flat = []
            for r in range(self.ROWS):
                filt_flat.extend(self.grid_filtered[r])
            self._spine_cal_frames.append(filt_flat)

        # Force calibration capture
        if self._force_calibrating:
            filt_flat = []
            for r in range(self.ROWS):
                filt_flat.extend(self.grid_filtered[r])
            self._force_cal_frames.append(filt_flat)

    def _apply_filter(self):
        """Subtract baseline and apply noise floor."""
        p = 0
        for r in range(self.ROWS):
            for c in range(self.COLS):
                val = self.grid_raw[r][c] - self.baseline[r][c]
                if val < self.noise_floor:
                    val = 0
                self.grid_filtered[r][c] = val
                if val > 0:
                    p += 1
        self.pressed = p

    def start_calibration(self):
        """Reset calibration to capture new baseline."""
        self.cal_accum = [[0] * self.COLS for _ in range(self.ROWS)]
        self.cal_count = 0
        self.calibrating = True

    # ── Session Recording ───────────────────────────────────────────

    def start_session(self, exercise="Free Flow"):
        """Begin recording frames."""
        with self.lock:
            self.session_exercise = exercise
            self.session_frames = []
            self.session_start_time = time.time()
            self.session_active = True
            # Update exercise region
            self.exercise_region = self.get_exercise_region(exercise)
        log.info("Session started: %s", exercise)
        return True

    def stop_session(self):
        """Stop recording, write CSVs, return summary."""
        with self.lock:
            self.session_active = False
            frames = self.session_frames
            self.session_frames = []
            exercise = self.session_exercise
            self.exercise_region = None

        if not frames:
            return {"duration": 0, "frame_count": 0, "avg_hz": 0,
                    "raw_csv": "", "filtered_csv": ""}

        duration_ms = frames[-1][0] if frames else 0
        duration_s = duration_ms / 1000.0
        frame_count = len(frames)
        avg_hz = frame_count / duration_s if duration_s > 0 else 0

        raw_path, filt_path, force_path = self._write_csvs(frames, exercise)

        log.info("Session stopped: %d frames, %.1f Hz, %.1f s",
                 frame_count, avg_hz, duration_s)
        return {
            "duration": round(duration_s, 1),
            "frame_count": frame_count,
            "avg_hz": round(avg_hz, 1),
            "raw_csv": raw_path,
            "filtered_csv": filt_path,
            "force_csv": force_path,
        }

    def _write_csvs(self, frames, exercise):
        """Write raw, filtered, and (optionally) force CSVs to recordings/ folder."""
        os.makedirs(self._recordings_dir, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = f"session_{stamp}"

        # Column headers
        header = ["timestamp_ms"]
        for r in range(self.ROWS):
            for c in range(self.COLS):
                header.append(f"R{r}C{c}")

        raw_path = os.path.join(self._recordings_dir, f"{base}_raw.csv")
        filt_path = os.path.join(self._recordings_dir, f"{base}_filtered.csv")

        with open(raw_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            for ts, raw_flat, _ in frames:
                w.writerow([ts] + raw_flat)

        with open(filt_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            for ts, _, filt_flat in frames:
                w.writerow([ts] + filt_flat)

        # Force CSV (only if gain map is loaded)
        force_path = ""
        if self.force_gain_map is not None:
            force_path = os.path.join(self._recordings_dir, f"{base}_force.csv")
            # Flatten gain map for fast lookup
            gain_flat = []
            for r in range(self.ROWS):
                gain_flat.extend(self.force_gain_map[r])
            with open(force_path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(header)
                for ts, _, filt_flat in frames:
                    force_row = [ts]
                    for i in range(len(filt_flat)):
                        force_row.append(round(filt_flat[i] * gain_flat[i], 2))
                    w.writerow(force_row)
            log.info("Force CSV written: %s", force_path)

        log.info("CSVs written: %s", raw_path)
        return raw_path, filt_path, force_path

    # ── Spine Calibration ───────────────────────────────────────────

    def start_spine_calibration(self, label):
        """Capture ~20 frames and find peak cell for a vertebra label."""
        with self.lock:
            self._spine_cal_label = label
            self._spine_cal_frames = []
            self._spine_calibrating = True

        # Wait for frames to accumulate
        time.sleep(1.2)  # ~20 frames at 17.8 Hz

        with self.lock:
            self._spine_calibrating = False
            frames = self._spine_cal_frames
            self._spine_cal_frames = []

        if not frames:
            return None

        # Average the captured frames
        n = len(frames)
        cells = self.ROWS * self.COLS
        avg = [0.0] * cells
        for flat in frames:
            for i in range(cells):
                avg[i] += flat[i]
        for i in range(cells):
            avg[i] /= n

        # Find peak cell
        peak_idx = max(range(cells), key=lambda i: avg[i])
        peak_row = peak_idx // self.COLS
        peak_col = peak_idx % self.COLS

        with self.lock:
            self.spine_markers[label] = [peak_row, peak_col]

        log.info("Spine %s: R%d C%d (avg %.0f, %d frames)",
                 label, peak_row, peak_col, avg[peak_idx], n)
        return {"row": peak_row, "col": peak_col, "label": label}

    def save_spine_calibration(self):
        """Persist spine markers to JSON."""
        with self.lock:
            data = dict(self.spine_markers)
        with open(self._cal_path, "w") as f:
            json.dump(data, f, indent=2)
        log.info("Spine calibration saved: %s", self._cal_path)

    def load_spine_calibration(self):
        """Load spine markers from JSON if exists."""
        if os.path.exists(self._cal_path):
            try:
                with open(self._cal_path) as f:
                    self.spine_markers = json.load(f)
                log.info("Spine calibration loaded: %s", self.spine_markers)
            except Exception as e:
                log.warning("Failed to load calibration: %s", e)

    def set_spine_markers(self, markers):
        """Directly set spine markers dict (from JS auto-detection) and save."""
        with self.lock:
            self.spine_markers = markers
        self.save_spine_calibration()
        log.info("Spine markers set: %s", markers)

    def clear_spine_calibration(self):
        """Remove all spine markers."""
        with self.lock:
            self.spine_markers = {}
        if os.path.exists(self._cal_path):
            os.remove(self._cal_path)

    def get_exercise_region(self, exercise):
        """Return (rmin, rmax, cmin, cmax) for exercise, or None."""
        # Map exercise to target vertebra
        exercise_targets = {
            "L4 Mobilization": "L4",
            "L5 Mobilization": "L5",
            "L3 Mobilization": "L3",
            "L2 Mobilization": "L2",
            "L1 Mobilization": "L1",
        }
        target = exercise_targets.get(exercise)
        if not target or target not in self.spine_markers:
            return None

        row, col = self.spine_markers[target]
        margin = 3
        rmin = max(0, row - margin)
        rmax = min(self.ROWS - 1, row + margin)
        cmin = max(0, col - margin)
        cmax = min(self.COLS - 1, col + margin)
        return (rmin, rmax, cmin, cmax)

    # ── Force Calibration ─────────────────────────────────────────

    def start_force_capture(self):
        """Begin accumulating frames for force calibration."""
        with self.lock:
            self._force_cal_frames = []
            self._force_calibrating = True

    def stop_force_capture(self):
        """Stop capture, average frames, find global peak. Returns dict."""
        # Let frames accumulate for ~2s
        time.sleep(2.0)

        with self.lock:
            self._force_calibrating = False
            frames = self._force_cal_frames
            self._force_cal_frames = []

        if not frames:
            return None

        # Average the captured frames
        n = len(frames)
        cells = self.ROWS * self.COLS
        avg = [0.0] * cells
        for flat in frames:
            for i in range(cells):
                avg[i] += flat[i]
        for i in range(cells):
            avg[i] /= n

        # Find global peak cell
        peak_idx = max(range(cells), key=lambda i: avg[i])
        peak_row = peak_idx // self.COLS
        peak_col = peak_idx % self.COLS
        peak_adc = avg[peak_idx]

        log.info("Force capture: peak R%d C%d ADC=%.0f (%d frames)",
                 peak_row, peak_col, peak_adc, n)
        return {
            "peak_adc": round(peak_adc),
            "row": peak_row,
            "col": peak_col,
            "frames": n,
        }

    def compute_force_gain_map(self, weight_grams, reference_points):
        """Compute per-cell gain map via IDW interpolation and save."""
        force_n = (weight_grams / 1000.0) * 9.81

        # Compute gain at each reference point
        for ref in reference_points:
            if ref["peak_adc"] > 0:
                ref["gain"] = force_n / ref["peak_adc"]
            else:
                ref["gain"] = 0.0

        # Filter out zero-gain references
        valid_refs = [r for r in reference_points if r["gain"] > 0]
        if not valid_refs:
            log.warning("No valid reference points for force calibration")
            return None

        # IDW interpolation for all cells
        # Physical pitch: row = 4mm, col = 5mm
        gain_map = [[0.0] * self.COLS for _ in range(self.ROWS)]
        for r in range(self.ROWS):
            for c in range(self.COLS):
                w_sum = 0.0
                wg_sum = 0.0
                for ref in valid_refs:
                    dr = (r - ref["row"]) * 4.0  # mm
                    dc = (c - ref["col"]) * 5.0  # mm
                    dist_sq = dr * dr + dc * dc
                    if dist_sq < 1.0:
                        # Exact match — use this gain directly
                        w_sum = 1.0
                        wg_sum = ref["gain"]
                        break
                    w = 1.0 / dist_sq
                    w_sum += w
                    wg_sum += w * ref["gain"]
                if w_sum > 0:
                    gain_map[r][c] = wg_sum / w_sum

        with self.lock:
            self.force_gain_map = gain_map

        # Save to JSON
        self.save_force_calibration(weight_grams, reference_points)

        log.info("Force gain map computed: %d refs, weight=%.1fg",
                 len(valid_refs), weight_grams)
        return gain_map

    def save_force_calibration(self, weight_grams, reference_points):
        """Persist force calibration to JSON."""
        force_n = (weight_grams / 1000.0) * 9.81
        data = {
            "weight_grams": weight_grams,
            "force_newtons": round(force_n, 4),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "reference_points": [
                {
                    "name": ref.get("name", ""),
                    "row": ref["row"],
                    "col": ref["col"],
                    "peak_adc": ref["peak_adc"],
                }
                for ref in reference_points
            ],
            "gain_map": self.force_gain_map,
        }
        with open(self._force_cal_path, "w") as f:
            json.dump(data, f, indent=2)
        log.info("Force calibration saved: %s", self._force_cal_path)

    def load_force_calibration(self):
        """Load force gain map from JSON if exists."""
        if os.path.exists(self._force_cal_path):
            try:
                with open(self._force_cal_path) as f:
                    data = json.load(f)
                self.force_gain_map = data.get("gain_map")
                log.info("Force calibration loaded: %dg, %d refs",
                         data.get("weight_grams", 0),
                         len(data.get("reference_points", [])))
            except Exception as e:
                log.warning("Failed to load force calibration: %s", e)

    def clear_force_calibration(self):
        """Reset force gain map and delete JSON."""
        with self.lock:
            self.force_gain_map = None
        if os.path.exists(self._force_cal_path):
            os.remove(self._force_cal_path)
        log.info("Force calibration cleared")

    def get_force_calibration_data(self):
        """Return full force calibration JSON data (for metadata display)."""
        if os.path.exists(self._force_cal_path):
            try:
                with open(self._force_cal_path) as f:
                    data = json.load(f)
                # Don't send the full gain_map to frontend for metadata display
                result = dict(data)
                result.pop("gain_map", None)
                return result
            except Exception:
                pass
        return None

    # ── Firmware Flash ────────────────────────────────────────────

    def get_firmware_info(self):
        """Return firmware file availability."""
        app_bin = os.path.join(self._firmware_dir, "t13_optimized.ino.bin")
        esptool = os.path.join(self._firmware_dir, "esptool.exe")
        return {
            "firmware_available": os.path.isfile(app_bin),
            "esptool_available": os.path.isfile(esptool),
        }

    def get_flash_progress(self):
        """Return current flash operation status."""
        return dict(self._flash_progress)

    def start_flash(self, port):
        """Flash firmware to ESP32-S3. Runs in background thread."""
        if self._flash_thread and self._flash_thread.is_alive():
            return {"success": False, "message": "Flash already in progress"}

        # Disconnect serial if we're connected to this port
        if self.connected and self.port_name == port:
            self.disconnect()

        self._flash_progress = {"status": "starting", "message": "Starting flash...", "percent": 0}
        self._flash_thread = threading.Thread(target=self._do_flash, args=(port,), daemon=True)
        self._flash_thread.start()
        return {"success": True, "message": "Flash started"}

    def _do_flash(self, port):
        """Execute esptool in a subprocess. Runs in background thread."""
        esptool = os.path.join(self._firmware_dir, "esptool.exe")
        bootloader = os.path.join(self._firmware_dir, "t13_optimized.ino.bootloader.bin")
        partitions = os.path.join(self._firmware_dir, "t13_optimized.ino.partitions.bin")
        boot_app0 = os.path.join(self._firmware_dir, "boot_app0.bin")
        app_bin = os.path.join(self._firmware_dir, "t13_optimized.ino.bin")

        # Verify all files exist
        for path in [esptool, bootloader, partitions, boot_app0, app_bin]:
            if not os.path.isfile(path):
                self._flash_progress = {
                    "status": "error",
                    "message": f"Missing: {os.path.basename(path)}",
                    "percent": 0,
                }
                return

        cmd = [
            esptool,
            "--chip", "esp32s3",
            "--port", port,
            "--baud", "921600",
            "--before", "default_reset",
            "--after", "hard_reset",
            "write_flash", "-z",
            "--flash-mode", "dio",
            "--flash-freq", "80m",
            "--flash-size", "16MB",
            "0x0", bootloader,
            "0x8000", partitions,
            "0xe000", boot_app0,
            "0x10000", app_bin,
        ]

        try:
            self._flash_progress = {"status": "flashing", "message": "Erasing flash...", "percent": 5}
            kwargs = {}
            if sys.platform == "win32":
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, **kwargs,
            )
            for line in proc.stdout:
                line = line.strip()
                log.info("esptool: %s", line)
                if "Writing at" in line and "%" in line:
                    try:
                        pct = int(line.split("(")[1].split("%")[0])
                        self._flash_progress = {
                            "status": "flashing",
                            "message": f"Writing... {pct}%",
                            "percent": 5 + int(pct * 0.90),
                        }
                    except (IndexError, ValueError):
                        pass
                elif "Hash of data verified" in line:
                    self._flash_progress = {"status": "flashing", "message": "Verifying...", "percent": 96}
                elif "Hard resetting" in line or "Leaving" in line:
                    self._flash_progress = {"status": "flashing", "message": "Resetting device...", "percent": 98}

            proc.wait()
            if proc.returncode == 0:
                self._flash_progress = {
                    "status": "done",
                    "message": "Flash complete! Device is restarting.",
                    "percent": 100,
                }
                log.info("Firmware flash succeeded on %s", port)
            else:
                self._flash_progress = {
                    "status": "error",
                    "message": f"Flash failed (exit code {proc.returncode})",
                    "percent": 0,
                }
                log.error("Firmware flash failed on %s (exit %d)", port, proc.returncode)
        except FileNotFoundError:
            self._flash_progress = {
                "status": "error",
                "message": "esptool.exe not found",
                "percent": 0,
            }
        except Exception as e:
            self._flash_progress = {"status": "error", "message": str(e), "percent": 0}
            log.error("Flash error: %s", e)

    # ── Vertebra Settings ─────────────────────────────────────────

    def load_vertebra_settings(self):
        """Load vertebra settings from JSON file, or use defaults."""
        if os.path.exists(self._vertebra_settings_path):
            try:
                with open(self._vertebra_settings_path) as f:
                    self.vertebra_settings = json.load(f)
                log.info("Vertebra settings loaded from %s", self._vertebra_settings_path)
                return
            except Exception as e:
                log.warning("Failed to load vertebra settings: %s", e)
        self.vertebra_settings = {k: dict(v) for k, v in self.VERTEBRA_DEFAULTS.items()}
        log.info("Using default vertebra settings")

    def save_vertebra_settings(self, data):
        """Write vertebra settings to JSON file."""
        self.vertebra_settings = data
        with open(self._vertebra_settings_path, "w") as f:
            json.dump(data, f, indent=2)
        log.info("Vertebra settings saved to %s", self._vertebra_settings_path)

    def reset_vertebra_settings(self):
        """Reset to defaults and save."""
        self.vertebra_settings = {k: dict(v) for k, v in self.VERTEBRA_DEFAULTS.items()}
        with open(self._vertebra_settings_path, "w") as f:
            json.dump(self.vertebra_settings, f, indent=2)
        log.info("Vertebra settings reset to defaults")
        return self.vertebra_settings

    # ── Settings ────────────────────────────────────────────────────

    def load_settings(self):
        """Load settings from JSON."""
        if os.path.exists(self._settings_path):
            try:
                with open(self._settings_path) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_settings(self, data):
        """Save settings to JSON."""
        with open(self._settings_path, "w") as f:
            json.dump(data, f, indent=2)

    # ── WebSocket Server ────────────────────────────────────────────

    async def _ws_handler(self, websocket):
        """Handle a single WebSocket client."""
        self._ws_clients.add(websocket)
        try:
            async def sender():
                while True:
                    with self.lock:
                        data = {
                            "type": "frame",
                            "rows": self.ROWS,
                            "cols": self.COLS,
                            "raw": [row[:] for row in self.grid_raw],
                            "grid": [row[:] for row in self.grid_filtered],
                            "baseline": [row[:] for row in self.baseline],
                            "hz": self.scan_hz,
                            "pressed": self.pressed,
                            "calibrating": self.calibrating,
                            "noise_floor": self.noise_floor,
                            "spine_markers": dict(self.spine_markers),
                            "exercise_region": self.exercise_region,
                            "session_active": self.session_active,
                            "vertebra_settings": dict(self.vertebra_settings),
                        }
                    await websocket.send(json.dumps(data))
                    await asyncio.sleep(0.033)  # ~30 FPS

            async def receiver():
                async for msg in websocket:
                    try:
                        cmd = json.loads(msg)
                        action = cmd.get("action")
                        if action == "calibrate":
                            with self.lock:
                                self.start_calibration()
                            log.info("Recalibrating (WS command)")
                        elif action == "set_noise_floor":
                            with self.lock:
                                self.noise_floor = int(cmd["value"])
                        elif action == "save_vertebra_settings":
                            try:
                                self.save_vertebra_settings(cmd["settings"])
                                await websocket.send(json.dumps({
                                    "type": "vertebra_settings_saved",
                                    "settings": self.vertebra_settings,
                                }))
                            except Exception as e:
                                await websocket.send(json.dumps({
                                    "type": "vertebra_settings_error",
                                    "error": str(e),
                                }))
                        elif action == "reset_vertebra_settings":
                            settings = self.reset_vertebra_settings()
                            await websocket.send(json.dumps({
                                "type": "vertebra_settings_reset",
                                "settings": settings,
                            }))
                    except Exception as e:
                        log.warning("WS command error: %s", e)

            await asyncio.gather(sender(), receiver())
        except websockets.ConnectionClosed:
            pass
        finally:
            self._ws_clients.discard(websocket)

    async def _run_ws_server(self):
        """Start WebSocket server, trying ports 8765-8774."""
        for port in range(8765, 8775):
            try:
                self._ws_server = await websockets.serve(
                    self._ws_handler, "127.0.0.1", port
                )
                self.ws_port = port
                log.info("WebSocket server on ws://127.0.0.1:%d", port)
                await self._ws_server.wait_closed()
                return
            except OSError:
                log.warning("Port %d in use, trying next...", port)
        log.error("Could not bind WebSocket server on any port 8765-8774")

    def start_ws_server(self):
        """Run the asyncio event loop with WS server in current thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._run_ws_server())
