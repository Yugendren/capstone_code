"""PressureMat — Desktop GUI entry point.

Launches a pywebview window with a WebSocket-backed pressure heatmap.
"""

import logging
import os
import sys
import threading
import time

import webview

from backend import PressureBackend

# Logging — use %APPDATA%/PressureMat when frozen, else script dir
if getattr(sys, "frozen", False):
    _log_dir = os.path.join(os.environ.get("APPDATA", os.path.dirname(sys.executable)), "PressureMat")
    os.makedirs(_log_dir, exist_ok=True)
    log_path = os.path.join(_log_dir, "pressuremat.log")
else:
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pressuremat.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_path, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("pressuremat")

backend = PressureBackend()


class ApiHandler:
    """Bridge between pywebview JS and PressureBackend."""

    def get_serial_ports(self):
        return backend.list_ports()

    def connect(self, port):
        return backend.connect(port)

    def connect_debug(self):
        return backend.connect_debug()

    def disconnect(self):
        return backend.disconnect()

    def get_connection_status(self):
        return {
            "connected": backend.connected,
            "port": backend.port_name,
            "scan_rate": round(backend.scan_hz, 1),
        }

    def get_ws_port(self):
        """Return the WebSocket server port (frontend needs this to connect)."""
        return backend.ws_port

    def start_session(self, exercise):
        return backend.start_session(exercise)

    def stop_session(self):
        return backend.stop_session()

    def open_recordings_folder(self):
        folder = backend._recordings_dir
        os.makedirs(folder, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(folder)
        else:
            import subprocess
            subprocess.Popen(["xdg-open", folder])

    def calibrate_baseline(self):
        with backend.lock:
            backend.start_calibration()

    def set_noise_floor(self, value):
        with backend.lock:
            backend.noise_floor = int(value)

    # Force calibration (legacy)
    def start_force_capture(self):
        backend.start_force_capture()

    def stop_force_capture(self):
        return backend.stop_force_capture()

    def compute_force_calibration(self, weight_grams, ref_points):
        return backend.compute_force_gain_map(weight_grams, ref_points)

    def get_force_gain_map(self):
        return backend.force_gain_map

    def clear_force_calibration(self):
        backend.clear_force_calibration()

    def load_force_calibration_data(self):
        return backend.get_force_calibration_data()

    # Polynomial force calibration (per-vertebra cubic)
    def compute_force_polynomial(self, vertebra, cal_points):
        return backend.compute_force_polynomial(vertebra, cal_points)

    def get_force_polynomials(self):
        return backend.get_force_polynomials()

    def get_force_calibration_full(self):
        return backend.get_force_calibration_full()

    def clear_force_calibration_vertebra(self, vertebra):
        backend.clear_force_calibration_vertebra(vertebra)

    # Session replay
    def list_recordings(self):
        return backend.list_recordings()

    def load_recording(self, csv_path):
        return backend.load_recording(csv_path)

    # Firmware flash
    def get_firmware_info(self):
        return backend.get_firmware_info()

    def start_flash(self, port):
        return backend.start_flash(port)

    def get_flash_progress(self):
        return backend.get_flash_progress()

    def get_settings(self):
        return backend.load_settings()

    def save_settings(self, data):
        backend.save_settings(data)

    # Vertebra settings
    def get_vertebra_settings(self):
        return backend.vertebra_settings

    def save_vertebra_settings(self, data):
        backend.save_vertebra_settings(data)
        return backend.vertebra_settings

    def reset_vertebra_settings(self):
        return backend.reset_vertebra_settings()


_ws_error = {"message": ""}


def run_ws_loop():
    """Run the asyncio+WS event loop in a daemon thread."""
    try:
        backend.start_ws_server()
    except Exception as e:
        _ws_error["message"] = str(e)
        log.error("WebSocket server failed to start: %s", e)


def on_closed():
    """Clean up on window close."""
    backend.update_settings({
        "last_port": backend.port_name,
        "noise_floor": backend.noise_floor,
    })
    backend.disconnect()


def main():
    # Start WebSocket server in daemon thread
    ws_thread = threading.Thread(target=run_ws_loop, daemon=True)
    ws_thread.start()

    # Give WS server a moment to bind
    time.sleep(0.3)

    if _ws_error["message"]:
        # WS could not bind — surface a hard error instead of a blank UI
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk(); root.withdraw()
            messagebox.showerror("PressureMat", f"Cannot start: {_ws_error['message']}")
        except Exception:
            print(f"FATAL: {_ws_error['message']}", file=sys.stderr)
        sys.exit(1)

    api = ApiHandler()

    # Resolve HTML path
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if getattr(sys, "frozen", False):
        base_dir = sys._MEIPASS

    app_html = os.path.join(base_dir, "app.html")

    window = webview.create_window(
        "PressureMat",
        url=app_html,
        js_api=api,
        width=1280,
        height=800,
        min_size=(1024, 700),
    )

    window.events.closed += on_closed

    webview.start()


if __name__ == "__main__":
    main()
