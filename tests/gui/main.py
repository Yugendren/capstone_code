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

# Logging
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

    def calibrate_baseline(self):
        with backend.lock:
            backend.start_calibration()

    def calibrate_spine_point(self, label):
        # Runs in background since it blocks for ~1.2s
        return backend.start_spine_calibration(label)

    def save_spine_calibration(self):
        backend.save_spine_calibration()

    def set_spine_markers(self, markers):
        backend.set_spine_markers(markers)

    def load_calibration(self):
        return backend.spine_markers if backend.spine_markers else None

    def clear_calibration(self):
        backend.clear_spine_calibration()

    def set_noise_floor(self, value):
        with backend.lock:
            backend.noise_floor = int(value)

    # Force calibration
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

    def get_settings(self):
        return backend.load_settings()

    def save_settings(self, data):
        backend.save_settings(data)


def run_ws_loop():
    """Run the asyncio+WS event loop in a daemon thread."""
    backend.start_ws_server()


def on_closed():
    """Clean up on window close."""
    settings = backend.load_settings()
    settings["last_port"] = backend.port_name
    settings["noise_floor"] = backend.noise_floor
    backend.save_settings(settings)
    backend.disconnect()


def main():
    # Start WebSocket server in daemon thread
    ws_thread = threading.Thread(target=run_ws_loop, daemon=True)
    ws_thread.start()

    # Give WS server a moment to bind
    time.sleep(0.3)

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
