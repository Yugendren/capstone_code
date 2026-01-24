"""
================================================================================
20x12 Piezoelectric Force Sensing Grid - Professional GUI Application
================================================================================

Physiotherapy Training System - Real-time pressure visualization with spinal
landmark detection and palpation feedback.

Features:
- Real-time 20x12 heatmap display with landmark overlay
- Hardware setup mode for GPIO/ADC configuration
- Spine-line calibration workflow
- L1-L5 vertebra visualization with uncertainty circles
- Palpation pressure feedback (0-4095 ADC range)
- Palpation frequency counter (Hz)
- Movement speed feedback
- Force-over-time waveform graph with flip to pseudo-displacement
- Peak, Trough, Frequency statistics
- Recording mode with countdown, CSV export, video recording
- Drift warning during recording
- Binary protocol communication with STM32

Usage:
    python grid_gui.py

Author: Capstone Project
Date: 2026-01-24
================================================================================
"""

import sys
import struct
import time
import csv
import os
import threading
from collections import deque
from datetime import datetime
from typing import Optional, Tuple, List
from pathlib import Path

import numpy as np
from scipy import signal
import serial
import serial.tools.list_ports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QStatusBar, QGroupBox, QSpinBox,
    QSlider, QFrame, QProgressBar, QDialog, QDialogButtonBox, QFileDialog,
    QSplitter, QSizePolicy
)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QThread, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QPalette, QColor, QPainter, QPen, QBrush, QLinearGradient
import pyqtgraph as pg

# Import spine detector module
from spine_detector import (
    SpineDetector, MovementTracker, PalpationZones, SpeedZones,
    SpinalLandmark, SpineCalibration
)

# Import hardware configuration and setup
from hardware_config import HardwareConfig, get_default_config, save_default_config
from setup_dialog import SetupModeDialog

# Optional imports for recording
try:
    import cv2
    import mss
    from PIL import Image
    RECORDING_AVAILABLE = True
except ImportError:
    RECORDING_AVAILABLE = False
    print("Warning: opencv-python, mss, or Pillow not installed. Recording disabled.")

try:
    import matplotlib.pyplot as plt
    import matplotlib.backends.backend_pdf
    EXPORT_AVAILABLE = True
except ImportError:
    EXPORT_AVAILABLE = False
    print("Warning: matplotlib not installed. PDF export disabled.")


# ============================================================================
# Constants
# ============================================================================

GRID_ROWS = 12
GRID_COLS = 20
GRID_TOTAL = GRID_ROWS * GRID_COLS  # 240

# Binary protocol
SYNC_BYTE_1 = 0xAA
SYNC_BYTE_2 = 0x55
HEADER_SIZE = 2
PAYLOAD_SIZE = GRID_TOTAL * 2  # 480 bytes (16-bit values)
FOOTER_SIZE = 4  # 2-byte checksum + CR + LF
PACKET_SIZE = HEADER_SIZE + PAYLOAD_SIZE + FOOTER_SIZE  # 486 bytes

# Waveform history
WAVEFORM_HISTORY_SIZE = 200  # ~8 seconds at 25 Hz

# Recording
COUNTDOWN_SECONDS = 2
RECORDING_FPS = 25

# ADC Range
ADC_MIN = 0
ADC_MAX = 4095

# ============================================================================
# Professional Apple-Inspired Color Palette
# ============================================================================

# Base colors - SF Pro inspired dark theme
COLORS = {
    'bg_primary': '#000000',        # Pure black background
    'bg_secondary': '#1c1c1e',      # Elevated surface
    'bg_tertiary': '#2c2c2e',       # Cards and panels
    'bg_quaternary': '#3a3a3c',     # Hover states

    'text_primary': '#ffffff',       # Primary text
    'text_secondary': '#8e8e93',     # Secondary text
    'text_tertiary': '#636366',      # Tertiary/disabled text

    'accent_blue': '#0a84ff',        # Primary action
    'accent_green': '#30d158',       # Success/optimal
    'accent_red': '#ff453a',         # Error/warning
    'accent_orange': '#ff9f0a',      # Caution
    'accent_yellow': '#ffd60a',      # Attention
    'accent_purple': '#bf5af2',      # Special
    'accent_teal': '#64d2ff',        # Info

    'separator': '#38383a',          # Dividers
    'fill_primary': '#787880',       # Input fills
}

# Heatmap gradient colors (blue to red)
HEATMAP_COLORS = [
    (0, 0, 40),       # Deep blue (no pressure)
    (0, 60, 180),     # Blue
    (0, 180, 220),    # Cyan
    (60, 220, 60),    # Green
    (220, 220, 0),    # Yellow
    (255, 140, 0),    # Orange
    (255, 40, 40),    # Red (high pressure)
]


# ============================================================================
# Serial Reader Thread
# ============================================================================

class SerialReader(QThread):
    """Background thread for reading serial data."""

    data_received = pyqtSignal(np.ndarray)  # Emits grid numpy array
    error_occurred = pyqtSignal(str)

    def __init__(self, port: str, baudrate: int = 115200):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = False
        self.serial: Optional[serial.Serial] = None

    def run(self):
        """Main thread loop - reads and parses binary packets."""
        try:
            self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
            self.running = True
            buffer = bytearray()

            while self.running:
                # Read available data
                if self.serial.in_waiting:
                    buffer.extend(self.serial.read(self.serial.in_waiting))

                # Look for sync bytes
                while len(buffer) >= PACKET_SIZE:
                    # Find sync pattern
                    sync_idx = -1
                    for i in range(len(buffer) - 1):
                        if buffer[i] == SYNC_BYTE_1 and buffer[i+1] == SYNC_BYTE_2:
                            sync_idx = i
                            break

                    if sync_idx == -1:
                        buffer = buffer[-1:]
                        break

                    if sync_idx > 0:
                        buffer = buffer[sync_idx:]

                    if len(buffer) < PACKET_SIZE:
                        break

                    packet = buffer[:PACKET_SIZE]
                    buffer = buffer[PACKET_SIZE:]

                    payload = packet[HEADER_SIZE:HEADER_SIZE + PAYLOAD_SIZE]

                    expected_checksum = struct.unpack('<H',
                        packet[HEADER_SIZE + PAYLOAD_SIZE:HEADER_SIZE + PAYLOAD_SIZE + 2])[0]
                    actual_checksum = sum(payload) & 0xFFFF

                    if expected_checksum != actual_checksum:
                        continue

                    values = struct.unpack(f'<{GRID_TOTAL}H', payload)
                    grid_data = np.array(values, dtype=np.uint16).reshape(GRID_ROWS, GRID_COLS)

                    self.data_received.emit(grid_data)

                time.sleep(0.001)

        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            if self.serial and self.serial.is_open:
                self.serial.close()

    def stop(self):
        """Stop the reader thread."""
        self.running = False
        self.wait(1000)


# ============================================================================
# Screen Recorder Thread
# ============================================================================

class ScreenRecorder(QThread):
    """Background thread for screen recording."""

    recording_complete = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, output_path: str, region: dict, fps: int = 25):
        super().__init__()
        self.output_path = output_path
        self.region = region
        self.fps = fps
        self.running = False
        self.frames = []

    def run(self):
        if not RECORDING_AVAILABLE:
            self.error_occurred.emit("Recording libraries not available")
            return

        try:
            self.running = True
            sct = mss.mss()

            while self.running:
                # Capture screen region
                screenshot = sct.grab(self.region)
                frame = np.array(screenshot)
                # Convert BGRA to BGR
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                self.frames.append(frame)
                time.sleep(1.0 / self.fps)

            # Write video
            if self.frames:
                height, width = self.frames[0].shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                out = cv2.VideoWriter(self.output_path, fourcc, self.fps, (width, height))
                for frame in self.frames:
                    out.write(frame)
                out.release()
                self.recording_complete.emit(self.output_path)

        except Exception as e:
            self.error_occurred.emit(str(e))

    def stop(self):
        self.running = False
        self.wait(2000)


# ============================================================================
# Palpation Frequency Analyzer
# ============================================================================

class FrequencyAnalyzer:
    """Analyzes palpation frequency from pressure data."""

    def __init__(self, sample_rate: float = 25.0, window_size: int = 50):
        self.sample_rate = sample_rate
        self.window_size = window_size
        self.pressure_history = deque(maxlen=window_size)
        self.press_times = deque(maxlen=20)
        self.threshold = 200  # ADC threshold for detecting a press
        self.was_pressed = False
        self.last_frequency = 0.0

    def update(self, max_pressure: int, timestamp: float) -> float:
        """Update with new pressure reading and return frequency in Hz."""
        self.pressure_history.append(max_pressure)

        # Detect press events
        is_pressed = max_pressure > self.threshold

        if is_pressed and not self.was_pressed:
            # Rising edge - new press
            self.press_times.append(timestamp)

        self.was_pressed = is_pressed

        # Calculate frequency from recent presses
        if len(self.press_times) >= 2:
            # Time span of recorded presses
            time_span = self.press_times[-1] - self.press_times[0]
            if time_span > 0:
                # Frequency = (number of presses - 1) / time span
                self.last_frequency = (len(self.press_times) - 1) / time_span

        return self.last_frequency

    def get_stats(self) -> dict:
        """Get current statistics."""
        if len(self.pressure_history) < 2:
            return {'peak': 0, 'trough': 0, 'frequency': 0.0}

        data = list(self.pressure_history)
        return {
            'peak': max(data),
            'trough': min(data),
            'frequency': self.last_frequency
        }


# ============================================================================
# Calibration Dialog
# ============================================================================

class CalibrationDialog(QDialog):
    """Dialog for spine calibration wizard."""

    calibration_complete = pyqtSignal(object)  # Emits SpineDetector

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Spine Calibration")
        self.setMinimumSize(500, 320)
        self.setModal(True)

        self.detector = SpineDetector()
        self._is_recording = False

        self._build_ui()
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['bg_primary']};
                color: {COLORS['text_primary']};
            }}
            QLabel {{
                color: {COLORS['text_primary']};
                font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', sans-serif;
            }}
            QPushButton {{
                background-color: {COLORS['bg_tertiary']};
                color: {COLORS['text_primary']};
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-weight: 500;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_quaternary']};
            }}
            QProgressBar {{
                border: none;
                border-radius: 4px;
                background-color: {COLORS['bg_tertiary']};
                height: 8px;
            }}
            QProgressBar::chunk {{
                background-color: {COLORS['accent_blue']};
                border-radius: 4px;
            }}
        """)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title = QLabel("Spine Calibration")
        title.setFont(QFont("-apple-system", 20, QFont.Weight.DemiBold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Instructions
        self.instruction_label = QLabel(
            "Place the sensing mat on the patient's lower back.\n"
            "Click 'Start Recording' and drag your finger firmly\n"
            "along the spine from top to bottom."
        )
        self.instruction_label.setWordWrap(True)
        self.instruction_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.instruction_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        layout.addWidget(self.instruction_label)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        # Status
        self.status_label = QLabel("Ready to calibrate")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(f"color: {COLORS['accent_yellow']}; font-weight: 500;")
        layout.addWidget(self.status_label)

        layout.addStretch()

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.record_btn = QPushButton("Start Recording")
        self.record_btn.clicked.connect(self._toggle_recording)
        self.record_btn.setStyleSheet(f"background-color: {COLORS['accent_green']}; color: {COLORS['bg_primary']};")
        btn_layout.addWidget(self.record_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

        self._frame_count = 0

    def _toggle_recording(self):
        if self._is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        self._is_recording = True
        self._frame_count = 0
        self.detector.start_calibration()
        self.record_btn.setText("Stop Recording")
        self.record_btn.setStyleSheet(f"background-color: {COLORS['accent_red']}; color: {COLORS['text_primary']};")
        self.status_label.setText("Recording... Drag finger along spine")
        self.status_label.setStyleSheet(f"color: {COLORS['accent_green']}; font-weight: 500;")

    def _stop_recording(self):
        self._is_recording = False
        self.record_btn.setText("Start Recording")
        self.record_btn.setStyleSheet(f"background-color: {COLORS['accent_green']}; color: {COLORS['bg_primary']};")

        success, message = self.detector.finalize_calibration()

        if success:
            self.status_label.setText(message)
            self.status_label.setStyleSheet(f"color: {COLORS['accent_green']}; font-weight: 500;")
            self.progress_bar.setValue(100)
            QTimer.singleShot(1500, self._accept_calibration)
        else:
            self.status_label.setText(message)
            self.status_label.setStyleSheet(f"color: {COLORS['accent_red']}; font-weight: 500;")
            self.progress_bar.setValue(0)

    def _accept_calibration(self):
        self.calibration_complete.emit(self.detector)
        self.accept()

    def add_frame(self, frame: np.ndarray):
        if self._is_recording:
            self.detector.add_calibration_frame(frame)
            self._frame_count += 1
            progress = min(100, int(self._frame_count / 50 * 100))
            self.progress_bar.setValue(progress)


# ============================================================================
# Color Legend Widget
# ============================================================================

class ColorLegendWidget(QWidget):
    """Vertical color legend for heatmap scale."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(60)
        self.setMinimumHeight(200)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw gradient
        gradient_rect = self.rect().adjusted(5, 30, -25, -30)
        gradient = QLinearGradient(0, gradient_rect.bottom(), 0, gradient_rect.top())

        for i, color in enumerate(HEATMAP_COLORS):
            pos = i / (len(HEATMAP_COLORS) - 1)
            gradient.setColorAt(pos, QColor(*color))

        painter.fillRect(gradient_rect, gradient)

        # Draw border
        painter.setPen(QPen(QColor(COLORS['separator']), 1))
        painter.drawRect(gradient_rect)

        # Draw labels
        painter.setPen(QPen(QColor(COLORS['text_secondary'])))
        font = QFont("-apple-system", 10)
        painter.setFont(font)

        # Top label (max)
        painter.drawText(gradient_rect.right() + 5, gradient_rect.top() + 5, "4095")

        # Middle label
        mid_y = (gradient_rect.top() + gradient_rect.bottom()) // 2
        painter.drawText(gradient_rect.right() + 5, mid_y + 4, "2048")

        # Bottom label (min)
        painter.drawText(gradient_rect.right() + 5, gradient_rect.bottom() + 4, "0")

        # Title
        painter.setPen(QPen(QColor(COLORS['text_primary'])))
        painter.drawText(5, 18, "ADC")


# ============================================================================
# Landmark Overlay Widget
# ============================================================================

class LandmarkOverlay(pg.GraphicsObject):
    """Overlay for drawing spinal landmarks on heatmap with uncertainty circles."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.landmarks: list = []
        self.spine_line = None
        self.show_labels = True
        self.highlight_landmark = None
        self.uncertainty_radius = 2.5  # Cells

    def set_landmarks(self, landmarks: list, spine_line=None):
        self.landmarks = landmarks
        self.spine_line = spine_line
        self.update()

    def highlight(self, landmark):
        self.highlight_landmark = landmark
        self.update()

    def boundingRect(self):
        return pg.QtCore.QRectF(0, 0, GRID_COLS, GRID_ROWS)

    def paint(self, painter, option, widget):
        if not self.landmarks:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw spine line
        if self.spine_line:
            pen = QPen(QColor(COLORS['accent_purple']))
            pen.setWidthF(0.15)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)

            y1 = self.spine_line.start_row
            x1 = self.spine_line.get_col_at_row(y1)
            y2 = self.spine_line.end_row
            x2 = self.spine_line.get_col_at_row(y2)

            painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        # Draw landmarks
        for lm in self.landmarks:
            is_highlighted = (self.highlight_landmark and
                            lm.level == self.highlight_landmark.level and
                            lm.landmark_type == self.highlight_landmark.landmark_type)

            # Only draw spinous processes with labels
            if lm.landmark_type == 'spinous':
                # Uncertainty circle
                uncertainty_color = QColor(COLORS['accent_blue'])
                uncertainty_color.setAlpha(60)
                painter.setPen(QPen(QColor(COLORS['accent_blue']), 0.1))
                painter.setBrush(QBrush(uncertainty_color))

                radius = self.uncertainty_radius * 1.5 if is_highlighted else self.uncertainty_radius
                painter.drawEllipse(
                    pg.QtCore.QPointF(lm.col, lm.row),
                    radius, radius
                )

                # Center point
                center_color = QColor(COLORS['accent_green']) if is_highlighted else QColor(COLORS['text_primary'])
                painter.setPen(QPen(center_color, 0.15))
                painter.setBrush(QBrush(center_color))
                painter.drawEllipse(
                    pg.QtCore.QPointF(lm.col, lm.row),
                    0.4, 0.4
                )

                # Label
                if self.show_labels:
                    painter.setPen(QPen(QColor(COLORS['text_primary'])))
                    font = painter.font()
                    font.setPointSizeF(2.5)
                    font.setBold(True)
                    painter.setFont(font)
                    painter.drawText(pg.QtCore.QPointF(lm.col + 1, lm.row + 0.5), lm.level)

            # Transverse processes - smaller dots
            else:
                tp_color = QColor(COLORS['accent_orange']) if is_highlighted else QColor(COLORS['accent_teal'])
                tp_color.setAlpha(150)
                painter.setPen(QPen(tp_color, 0.08))
                painter.setBrush(QBrush(tp_color))
                painter.drawEllipse(
                    pg.QtCore.QPointF(lm.col, lm.row),
                    0.3, 0.3
                )


# ============================================================================
# Statistics Panel Widget
# ============================================================================

class StatsPanel(QWidget):
    """Panel showing real-time statistics."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Stats container
        self.peak_label = self._create_stat_row("Peak", "0")
        self.trough_label = self._create_stat_row("Trough", "0")
        self.freq_label = self._create_stat_row("Frequency", "0.0 Hz")

        layout.addWidget(self.peak_label)
        layout.addWidget(self.trough_label)
        layout.addWidget(self.freq_label)
        layout.addStretch()

    def _create_stat_row(self, label: str, value: str) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        label_widget = QLabel(label)
        label_widget.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px;")

        value_widget = QLabel(value)
        value_widget.setObjectName(f"value_{label.lower()}")
        value_widget.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 13px; font-weight: 600;")
        value_widget.setAlignment(Qt.AlignmentFlag.AlignRight)

        layout.addWidget(label_widget)
        layout.addWidget(value_widget)

        container.value_label = value_widget
        return container

    def update_stats(self, peak: int, trough: int, frequency: float):
        self.peak_label.value_label.setText(str(peak))
        self.trough_label.value_label.setText(str(trough))
        self.freq_label.value_label.setText(f"{frequency:.1f} Hz")


# ============================================================================
# Feedback Panel Widget
# ============================================================================

class FeedbackPanel(QWidget):
    """Panel showing real-time palpation and speed feedback."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Pressure feedback
        pressure_group = self._create_section("Pressure")
        pressure_layout = QVBoxLayout(pressure_group)
        pressure_layout.setContentsMargins(16, 12, 16, 12)

        self.pressure_bar = QProgressBar()
        self.pressure_bar.setRange(0, 4095)
        self.pressure_bar.setTextVisible(False)
        self.pressure_bar.setFixedHeight(8)
        pressure_layout.addWidget(self.pressure_bar)

        self.pressure_label = QLabel("No contact")
        self.pressure_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pressure_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        pressure_layout.addWidget(self.pressure_label)

        layout.addWidget(pressure_group)

        # Speed feedback
        speed_group = self._create_section("Movement Speed")
        speed_layout = QVBoxLayout(speed_group)
        speed_layout.setContentsMargins(16, 12, 16, 12)

        self.speed_bar = QProgressBar()
        self.speed_bar.setRange(0, 100)
        self.speed_bar.setTextVisible(False)
        self.speed_bar.setFixedHeight(8)
        speed_layout.addWidget(self.speed_bar)

        self.speed_label = QLabel("Stationary")
        self.speed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.speed_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        speed_layout.addWidget(self.speed_label)

        layout.addWidget(speed_group)

        # Target feedback
        target_group = self._create_section("Target Guidance")
        target_layout = QVBoxLayout(target_group)
        target_layout.setContentsMargins(16, 12, 16, 12)

        self.target_label = QLabel("Calibrate to enable")
        self.target_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.target_label.setWordWrap(True)
        self.target_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        target_layout.addWidget(self.target_label)

        self.distance_label = QLabel("")
        self.distance_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.distance_label.setStyleSheet(f"color: {COLORS['text_tertiary']}; font-size: 11px;")
        target_layout.addWidget(self.distance_label)

        layout.addWidget(target_group)

        # Palpation frequency
        freq_group = self._create_section("Palpation Rate")
        freq_layout = QVBoxLayout(freq_group)
        freq_layout.setContentsMargins(16, 12, 16, 12)

        self.palpation_freq_label = QLabel("0.0 Hz")
        self.palpation_freq_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.palpation_freq_label.setStyleSheet(f"color: {COLORS['accent_blue']}; font-size: 24px; font-weight: 600;")
        freq_layout.addWidget(self.palpation_freq_label)

        layout.addWidget(freq_group)

    def _create_section(self, title: str) -> QWidget:
        group = QWidget()
        group.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['bg_secondary']};
                border-radius: 12px;
            }}
        """)
        return group

    def update_pressure(self, value: int):
        self.pressure_bar.setValue(value)
        zone_name, color, message = PalpationZones.get_zone(value)
        self.pressure_label.setText(message)
        self.pressure_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 500;")

        self.pressure_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 4px;
                background-color: {COLORS['bg_tertiary']};
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 4px;
            }}
        """)

    def update_speed(self, speed: float):
        normalized = min(100, int(speed * 4))
        self.speed_bar.setValue(normalized)

        zone_name, color, message = SpeedZones.get_zone(speed)
        self.speed_label.setText(f"{message} ({speed:.1f} cells/s)")
        self.speed_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 500;")

        self.speed_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 4px;
                background-color: {COLORS['bg_tertiary']};
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 4px;
            }}
        """)

    def update_target(self, feedback: dict):
        if feedback['nearest_landmark'] is None:
            self.target_label.setText("Calibrate to enable")
            self.target_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
            self.distance_label.setText("")
            return

        lm = feedback['nearest_landmark']
        dist = feedback['distance_to_landmark']

        if feedback['on_target']:
            self.target_label.setText(f"On {lm.level} {lm.landmark_type}")
            self.target_label.setStyleSheet(f"color: {COLORS['accent_green']}; font-size: 12px; font-weight: 600;")
        else:
            self.target_label.setText(feedback['feedback'])
            self.target_label.setStyleSheet(f"color: {COLORS['accent_yellow']}; font-size: 12px; font-weight: 500;")

        self.distance_label.setText(f"Distance: {dist:.1f} cells")

    def update_palpation_frequency(self, freq: float):
        self.palpation_freq_label.setText(f"{freq:.1f} Hz")


# ============================================================================
# Drift Warning Widget
# ============================================================================

class DriftWarningWidget(QWidget):
    """Visual drift warning overlay."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setVisible(False)
        self.setFixedSize(300, 80)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 15)

        self.warning_label = QLabel("Drift Detected")
        self.warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.warning_label.setStyleSheet(f"""
            color: {COLORS['text_primary']};
            font-size: 16px;
            font-weight: 600;
        """)
        layout.addWidget(self.warning_label)

        self.detail_label = QLabel("Return to selected landmark")
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        layout.addWidget(self.detail_label)

        self.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['accent_red']};
                border-radius: 16px;
            }}
        """)

    def show_warning(self, message: str = "Return to selected landmark"):
        self.detail_label.setText(message)
        self.setVisible(True)
        # System beep
        print('\a', end='', flush=True)

    def hide_warning(self):
        self.setVisible(False)


# ============================================================================
# Recording Controls Widget
# ============================================================================

class RecordingControls(QWidget):
    """Recording controls with countdown display."""

    recording_started = pyqtSignal()
    recording_stopped = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_recording = False
        self.countdown_value = 0
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.record_btn = QPushButton("Record")
        self.record_btn.clicked.connect(self._on_record_clicked)
        self.record_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg_tertiary']};
                color: {COLORS['text_primary']};
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_quaternary']};
            }}
        """)
        layout.addWidget(self.record_btn)

        self.countdown_label = QLabel("")
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.countdown_label.setStyleSheet(f"color: {COLORS['accent_red']}; font-size: 18px; font-weight: 600;")
        self.countdown_label.setFixedWidth(50)
        layout.addWidget(self.countdown_label)

        self.status_indicator = QLabel("")
        self.status_indicator.setFixedSize(12, 12)
        self.status_indicator.setStyleSheet(f"background-color: transparent; border-radius: 6px;")
        layout.addWidget(self.status_indicator)

        layout.addStretch()

        # Countdown timer
        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self._countdown_tick)

    def _on_record_clicked(self):
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_countdown()

    def _start_countdown(self):
        self.countdown_value = COUNTDOWN_SECONDS
        self.countdown_label.setText(str(self.countdown_value))
        self.record_btn.setEnabled(False)
        self.countdown_timer.start(1000)

    def _countdown_tick(self):
        self.countdown_value -= 1
        if self.countdown_value > 0:
            self.countdown_label.setText(str(self.countdown_value))
        else:
            self.countdown_timer.stop()
            self.countdown_label.setText("")
            self._start_recording()

    def _start_recording(self):
        self.is_recording = True
        self.record_btn.setText("Stop")
        self.record_btn.setEnabled(True)
        self.record_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['accent_red']};
                color: {COLORS['text_primary']};
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 500;
            }}
        """)
        self.status_indicator.setStyleSheet(f"background-color: {COLORS['accent_red']}; border-radius: 6px;")
        self.recording_started.emit()

    def _stop_recording(self):
        self.is_recording = False
        self.record_btn.setText("Record")
        self.record_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg_tertiary']};
                color: {COLORS['text_primary']};
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_quaternary']};
            }}
        """)
        self.status_indicator.setStyleSheet(f"background-color: transparent; border-radius: 6px;")
        self.recording_stopped.emit()


# ============================================================================
# Main Window
# ============================================================================

class GridVisualizerWindow(QMainWindow):
    """Main application window with heatmap, calibration, and feedback."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Force Sensing Grid - Physiotherapy Training")
        self.setMinimumSize(1500, 950)

        # Data storage
        self.grid_data = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.uint16)
        self.selected_row = GRID_ROWS // 2
        self.selected_col = GRID_COLS // 2
        self.waveform_history = deque(maxlen=WAVEFORM_HISTORY_SIZE)
        self.waveform_time = deque(maxlen=WAVEFORM_HISTORY_SIZE)
        self.frame_count = 0
        self.start_time = time.time()

        # Graph state
        self.graph_inverted = False

        # Serial connection
        self.serial_reader: Optional[SerialReader] = None

        # Spine detection
        self.spine_detector = SpineDetector()
        self.movement_tracker = MovementTracker()
        self.frequency_analyzer = FrequencyAnalyzer()

        # Calibration dialog reference
        self.calibration_dialog: Optional[CalibrationDialog] = None

        # Hardware configuration
        self.hardware_config = get_default_config()
        self.setup_dialog: Optional[SetupModeDialog] = None

        # Recording state
        self.is_recording = False
        self.recording_data_raw: List[np.ndarray] = []
        self.recording_data_annotated: List[dict] = []
        self.recording_start_time: Optional[float] = None
        self.screen_recorder: Optional[ScreenRecorder] = None
        self.selected_target_landmark: Optional[SpinalLandmark] = None

        # Apply dark theme
        self._apply_dark_theme()

        # Build UI
        self._build_ui()

        # Demo timer
        self.demo_timer = QTimer()
        self.demo_timer.timeout.connect(self._generate_demo_data)

    def _apply_dark_theme(self):
        """Apply professional dark color scheme."""
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {COLORS['bg_primary']};
                color: {COLORS['text_primary']};
                font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', sans-serif;
            }}
            QGroupBox {{
                background-color: {COLORS['bg_secondary']};
                border: none;
                border-radius: 12px;
                margin-top: 8px;
                padding: 16px;
                font-weight: 500;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 16px;
                padding: 0 8px;
                color: {COLORS['text_secondary']};
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            QPushButton {{
                background-color: {COLORS['bg_tertiary']};
                color: {COLORS['text_primary']};
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-weight: 500;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {COLORS['bg_quaternary']};
            }}
            QPushButton:pressed {{
                background-color: {COLORS['accent_blue']};
            }}
            QComboBox {{
                background-color: {COLORS['bg_tertiary']};
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
                color: {COLORS['text_primary']};
                font-size: 13px;
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 10px;
            }}
            QLabel {{
                color: {COLORS['text_primary']};
            }}
            QStatusBar {{
                background-color: {COLORS['bg_secondary']};
                color: {COLORS['text_secondary']};
                font-size: 12px;
            }}
            QProgressBar {{
                border: none;
                border-radius: 4px;
                background-color: {COLORS['bg_tertiary']};
                height: 8px;
            }}
            QProgressBar::chunk {{
                background-color: {COLORS['accent_blue']};
                border-radius: 4px;
            }}
        """)

    def _build_ui(self):
        """Construct the user interface."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # ---- Left Panel: Heatmap ----
        left_panel = QVBoxLayout()
        left_panel.setSpacing(12)

        # Header with title and calibration status
        header_layout = QHBoxLayout()

        title = QLabel("Pressure Heatmap")
        title.setFont(QFont("-apple-system", 18, QFont.Weight.DemiBold))
        header_layout.addWidget(title)

        header_layout.addStretch()

        self.calibration_status = QLabel("Not Calibrated")
        self.calibration_status.setStyleSheet(f"color: {COLORS['accent_yellow']}; font-size: 12px;")
        header_layout.addWidget(self.calibration_status)

        left_panel.addLayout(header_layout)

        # Heatmap container
        heatmap_container = QHBoxLayout()

        # Heatmap with overlay
        self.heatmap_widget = pg.PlotWidget()
        self.heatmap_widget.setAspectLocked(True)
        self.heatmap_widget.hideAxis('left')
        self.heatmap_widget.hideAxis('bottom')
        self.heatmap_widget.setBackground(COLORS['bg_secondary'])

        # Create ImageItem for heatmap
        self.heatmap_image = pg.ImageItem()
        self.heatmap_widget.addItem(self.heatmap_image)

        # Set colormap
        positions = np.linspace(0, 1, len(HEATMAP_COLORS))
        colormap = pg.ColorMap(positions, HEATMAP_COLORS)
        self.heatmap_image.setLookupTable(colormap.getLookupTable())
        self.heatmap_image.setLevels([ADC_MIN, ADC_MAX])

        # Initial empty image
        self.heatmap_image.setImage(self.grid_data.T)

        # Add landmark overlay
        self.landmark_overlay = LandmarkOverlay()
        self.heatmap_widget.addItem(self.landmark_overlay)

        # Click handler
        self.heatmap_widget.scene().sigMouseClicked.connect(self._on_heatmap_click)

        heatmap_container.addWidget(self.heatmap_widget, stretch=1)

        # Color legend
        self.color_legend = ColorLegendWidget()
        heatmap_container.addWidget(self.color_legend)

        left_panel.addLayout(heatmap_container, stretch=1)

        # Drift warning overlay
        self.drift_warning = DriftWarningWidget(self)
        self.drift_warning.move(200, 100)

        main_layout.addLayout(left_panel, stretch=2)

        # ---- Middle Panel: Graph ----
        middle_panel = QVBoxLayout()
        middle_panel.setSpacing(12)

        # Graph header
        graph_header = QHBoxLayout()
        graph_title = QLabel("Force vs Time")
        graph_title.setFont(QFont("-apple-system", 14, QFont.Weight.Medium))
        graph_header.addWidget(graph_title)

        graph_header.addStretch()

        self.flip_btn = QPushButton("Flip View")
        self.flip_btn.clicked.connect(self._toggle_graph_flip)
        self.flip_btn.setFixedWidth(80)
        self.flip_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['bg_tertiary']};
                color: {COLORS['text_secondary']};
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
            }}
        """)
        graph_header.addWidget(self.flip_btn)

        middle_panel.addLayout(graph_header)

        # Waveform graph
        graph_container = QWidget()
        graph_container.setStyleSheet(f"background-color: {COLORS['bg_secondary']}; border-radius: 12px;")
        graph_layout = QHBoxLayout(graph_container)
        graph_layout.setContentsMargins(12, 12, 12, 12)

        self.waveform_plot = pg.PlotWidget()
        self.waveform_plot.setBackground(COLORS['bg_secondary'])
        self.waveform_plot.setLabel('left', 'ADC Value')
        self.waveform_plot.setLabel('bottom', 'Time', units='s')
        self.waveform_plot.setYRange(0, 4095)
        self.waveform_plot.showGrid(x=True, y=True, alpha=0.2)

        self.waveform_curve = self.waveform_plot.plot(
            pen=pg.mkPen(color=COLORS['accent_blue'], width=2)
        )
        graph_layout.addWidget(self.waveform_plot, stretch=1)

        # Stats panel next to graph
        self.stats_panel = StatsPanel()
        self.stats_panel.setFixedWidth(100)
        graph_layout.addWidget(self.stats_panel)

        middle_panel.addWidget(graph_container, stretch=1)

        # Selected cell label
        self.selected_label = QLabel(f"Selected: Row {self.selected_row}, Col {self.selected_col}")
        self.selected_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selected_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        middle_panel.addWidget(self.selected_label)

        main_layout.addLayout(middle_panel, stretch=1)

        # ---- Right Panel: Controls + Feedback ----
        right_panel = QVBoxLayout()
        right_panel.setSpacing(16)

        # Feedback panel
        self.feedback_panel = FeedbackPanel()
        right_panel.addWidget(self.feedback_panel)

        # Controls
        controls_group = QGroupBox("Controls")
        controls_layout = QVBoxLayout()
        controls_layout.setSpacing(12)

        # COM port
        port_layout = QHBoxLayout()
        port_label = QLabel("Port")
        port_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        port_layout.addWidget(port_label)

        self.port_combo = QComboBox()
        self._refresh_ports()
        port_layout.addWidget(self.port_combo, stretch=1)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setFixedWidth(70)
        self.refresh_btn.clicked.connect(self._refresh_ports)
        port_layout.addWidget(self.refresh_btn)
        controls_layout.addLayout(port_layout)

        # Connect/Demo buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)

        self.connect_btn = QPushButton("Connect")
        self.connect_btn.clicked.connect(self._toggle_connection)
        self.connect_btn.setStyleSheet(f"background-color: {COLORS['accent_green']}; color: {COLORS['bg_primary']};")
        btn_layout.addWidget(self.connect_btn)

        self.demo_btn = QPushButton("Demo")
        self.demo_btn.clicked.connect(self._toggle_demo)
        btn_layout.addWidget(self.demo_btn)
        controls_layout.addLayout(btn_layout)

        # Setup Mode button
        self.setup_btn = QPushButton("Hardware Setup")
        self.setup_btn.clicked.connect(self._open_setup_mode)
        self.setup_btn.setStyleSheet(f"background-color: {COLORS['accent_purple']}; color: {COLORS['text_primary']};")
        controls_layout.addWidget(self.setup_btn)

        # Calibration buttons
        calib_layout = QHBoxLayout()
        calib_layout.setSpacing(8)

        self.calibrate_btn = QPushButton("Calibrate Spine")
        self.calibrate_btn.clicked.connect(self._start_calibration)
        calib_layout.addWidget(self.calibrate_btn)

        self.load_calib_btn = QPushButton("Load")
        self.load_calib_btn.clicked.connect(self._load_calibration)
        self.load_calib_btn.setFixedWidth(60)
        calib_layout.addWidget(self.load_calib_btn)

        self.save_calib_btn = QPushButton("Save")
        self.save_calib_btn.clicked.connect(self._save_calibration)
        self.save_calib_btn.setFixedWidth(60)
        calib_layout.addWidget(self.save_calib_btn)
        controls_layout.addLayout(calib_layout)

        controls_group.setLayout(controls_layout)
        right_panel.addWidget(controls_group)

        # Recording controls
        recording_group = QGroupBox("Recording")
        recording_layout = QVBoxLayout()

        self.recording_controls = RecordingControls()
        self.recording_controls.recording_started.connect(self._start_recording)
        self.recording_controls.recording_stopped.connect(self._stop_recording)
        recording_layout.addWidget(self.recording_controls)

        recording_group.setLayout(recording_layout)
        right_panel.addWidget(recording_group)

        # Stats
        stats_group = QGroupBox("System")
        stats_layout = QVBoxLayout()

        self.fps_label = QLabel("FPS: 0")
        self.fps_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        stats_layout.addWidget(self.fps_label)

        stats_group.setLayout(stats_layout)
        right_panel.addWidget(stats_group)

        right_panel.addStretch()

        main_layout.addLayout(right_panel, stretch=1)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Connect to device or start demo mode")

    def _refresh_ports(self):
        """Refresh available COM ports."""
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(f"{port.device} - {port.description}", port.device)
        if not ports:
            self.port_combo.addItem("No ports found", None)

    def _toggle_connection(self):
        """Connect or disconnect from serial port."""
        if self.serial_reader and self.serial_reader.running:
            self.serial_reader.stop()
            self.serial_reader = None
            self.connect_btn.setText("Connect")
            self.connect_btn.setStyleSheet(f"background-color: {COLORS['accent_green']}; color: {COLORS['bg_primary']};")
            self.status_bar.showMessage("Disconnected")
        else:
            port = self.port_combo.currentData()
            if not port:
                self.status_bar.showMessage("No valid port selected")
                return

            self.serial_reader = SerialReader(port)
            self.serial_reader.data_received.connect(self._on_data_received)
            self.serial_reader.error_occurred.connect(self._on_serial_error)
            self.serial_reader.start()

            self.connect_btn.setText("Disconnect")
            self.connect_btn.setStyleSheet(f"background-color: {COLORS['accent_red']}; color: {COLORS['text_primary']};")
            self.status_bar.showMessage(f"Connected to {port}")

    def _toggle_demo(self):
        """Toggle demo mode."""
        if self.demo_timer.isActive():
            self.demo_timer.stop()
            self.demo_btn.setText("Demo")
            self.demo_btn.setStyleSheet(f"background-color: {COLORS['bg_tertiary']}; color: {COLORS['text_primary']};")
            self.status_bar.showMessage("Demo mode stopped")
        else:
            # Auto-calibrate for demo
            self._setup_demo_calibration()
            self.demo_timer.start(40)
            self.demo_btn.setText("Stop Demo")
            self.demo_btn.setStyleSheet(f"background-color: {COLORS['accent_orange']}; color: {COLORS['bg_primary']};")
            self.status_bar.showMessage("Demo mode active")

    def _setup_demo_calibration(self):
        """Set up demo calibration with L1-L5 landmarks."""
        from spine_detector import SpineLine

        # Create a spine line through the center
        spine_line = SpineLine(
            start_row=1,
            end_row=10,
            coefficients=(0.0, GRID_COLS / 2)  # Vertical line at center
        )

        self.spine_detector.calibration.spine_line = spine_line
        self.spine_detector.calibration.landmarks = spine_line.get_landmarks(lateral_offset=4)

        # Update overlay
        self.landmark_overlay.set_landmarks(
            self.spine_detector.calibration.landmarks,
            spine_line
        )
        self.calibration_status.setText("Calibrated (Demo)")
        self.calibration_status.setStyleSheet(f"color: {COLORS['accent_green']}; font-size: 12px;")

    def _generate_demo_data(self):
        """Generate demo data simulating spine palpation."""
        t = time.time()

        # Simulate finger position moving along spine
        spine_col = GRID_COLS / 2 + np.sin(t * 0.5) * 2
        spine_row = 2 + ((t * 2) % 8)

        # Generate pressure around finger position
        data = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.uint16)
        for i in range(GRID_ROWS):
            for j in range(GRID_COLS):
                dist = np.sqrt((i - spine_row)**2 + (j - spine_col)**2)
                data[i, j] = int(2500 * np.exp(-dist**2 / 4))

        # Add noise
        data = data + np.random.randint(0, 30, data.shape, dtype=np.uint16)

        self._on_data_received(data)

    def _on_data_received(self, data: np.ndarray):
        """Handle received grid data."""
        self.grid_data = data
        self.frame_count += 1
        current_time = time.time()

        # Update heatmap
        self.heatmap_image.setImage(data.T, autoLevels=False)

        # If calibrating, send frame to dialog
        if self.calibration_dialog and self.calibration_dialog._is_recording:
            self.calibration_dialog.add_frame(data)

        # If in setup mode, send frame to setup dialog
        if self.setup_dialog and self.setup_dialog.isVisible():
            self.setup_dialog.update_frame(data)

        # Update movement tracker
        pos, speed = self.movement_tracker.update(data, current_time)

        # Update frequency analyzer
        max_pressure = int(np.max(data))
        palpation_freq = self.frequency_analyzer.update(max_pressure, current_time)

        # Update feedback
        self.feedback_panel.update_pressure(max_pressure)
        self.feedback_panel.update_speed(speed)
        self.feedback_panel.update_palpation_frequency(palpation_freq)

        # Get technique feedback if calibrated
        if pos and self.spine_detector.calibration.is_calibrated:
            feedback = self.spine_detector.get_technique_feedback(
                pos[0], pos[1], max_pressure
            )
            self.feedback_panel.update_target(feedback)

            # Highlight nearest landmark
            if feedback['nearest_landmark']:
                self.landmark_overlay.highlight(feedback['nearest_landmark'])

            # Check for drift during recording
            if self.is_recording and self.selected_target_landmark:
                dist = feedback['distance_to_landmark']
                if dist > 5.0:  # Drift threshold
                    self.drift_warning.show_warning(f"Move back to {self.selected_target_landmark.level}")
                else:
                    self.drift_warning.hide_warning()

        # Update waveform
        cell_value = data[self.selected_row, self.selected_col]
        self.waveform_history.append(cell_value)
        self.waveform_time.append(current_time - self.start_time)

        if len(self.waveform_history) > 1:
            y_data = list(self.waveform_history)
            if self.graph_inverted:
                y_data = [ADC_MAX - v for v in y_data]
            self.waveform_curve.setData(list(self.waveform_time), y_data)

        # Update stats
        stats = self.frequency_analyzer.get_stats()
        self.stats_panel.update_stats(stats['peak'], stats['trough'], stats['frequency'])

        # Update FPS
        elapsed = current_time - self.start_time
        if elapsed > 0:
            fps = self.frame_count / elapsed
            self.fps_label.setText(f"FPS: {fps:.1f}")

        # Recording
        if self.is_recording:
            self._record_frame(data, current_time, pos, max_pressure)

    def _record_frame(self, data: np.ndarray, timestamp: float, pos, pressure: int):
        """Record frame data."""
        self.recording_data_raw.append(data.copy())

        # Annotated data
        annotation = {
            'timestamp': timestamp - self.recording_start_time,
            'max_pressure': pressure,
            'position': pos,
            'nearest_landmark': None,
            'distance': None
        }

        if pos and self.spine_detector.calibration.is_calibrated:
            lm, dist = self.spine_detector.find_nearest_landmark(pos[0], pos[1])
            if lm:
                annotation['nearest_landmark'] = lm.level
                annotation['distance'] = dist

        self.recording_data_annotated.append(annotation)

    def _on_serial_error(self, error: str):
        """Handle serial errors."""
        self.status_bar.showMessage(f"Error: {error}")
        self.connect_btn.setText("Connect")
        self.connect_btn.setStyleSheet(f"background-color: {COLORS['accent_green']}; color: {COLORS['bg_primary']};")

    def _on_heatmap_click(self, event):
        """Handle click on heatmap."""
        pos = event.scenePos()
        mouse_point = self.heatmap_widget.plotItem.vb.mapSceneToView(pos)
        col = int(mouse_point.x())
        row = int(mouse_point.y())

        if 0 <= row < GRID_ROWS and 0 <= col < GRID_COLS:
            self.selected_row = row
            self.selected_col = col
            self.selected_label.setText(f"Selected: Row {row}, Col {col}")
            self.waveform_history.clear()
            self.waveform_time.clear()

            # If calibrated, set target landmark
            if self.spine_detector.calibration.is_calibrated:
                lm, _ = self.spine_detector.find_nearest_landmark(row, col)
                self.selected_target_landmark = lm

    def _toggle_graph_flip(self):
        """Toggle graph between force and pseudo-displacement view."""
        self.graph_inverted = not self.graph_inverted

        if self.graph_inverted:
            self.flip_btn.setText("Normal")
            self.waveform_plot.setLabel('left', 'Pseudo-Displacement')
            self.waveform_plot.setYRange(0, 4095)
        else:
            self.flip_btn.setText("Flip View")
            self.waveform_plot.setLabel('left', 'ADC Value')
            self.waveform_plot.setYRange(0, 4095)

    def _start_calibration(self):
        """Open calibration dialog."""
        self.calibration_dialog = CalibrationDialog(self)
        self.calibration_dialog.calibration_complete.connect(self._on_calibration_complete)
        self.calibration_dialog.show()

    def _on_calibration_complete(self, detector: SpineDetector):
        """Handle completed calibration."""
        self.spine_detector = detector

        if detector.calibration.is_calibrated:
            self.landmark_overlay.set_landmarks(
                detector.calibration.landmarks,
                detector.calibration.spine_line
            )
            self.calibration_status.setText("Calibrated")
            self.calibration_status.setStyleSheet(f"color: {COLORS['accent_green']}; font-size: 12px;")
            self.status_bar.showMessage("Calibration complete - L1-L5 landmarks visible")

        self.calibration_dialog = None

    def _save_calibration(self):
        """Save calibration to file."""
        if not self.spine_detector.calibration.is_calibrated:
            self.status_bar.showMessage("No calibration to save")
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Calibration", "", "JSON Files (*.json)"
        )
        if filepath:
            self.spine_detector.save_calibration(filepath)
            self.status_bar.showMessage(f"Calibration saved to {filepath}")

    def _load_calibration(self):
        """Load calibration from file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Calibration", "", "JSON Files (*.json)"
        )
        if filepath:
            if self.spine_detector.load_calibration(filepath):
                self.landmark_overlay.set_landmarks(
                    self.spine_detector.calibration.landmarks,
                    self.spine_detector.calibration.spine_line
                )
                self.calibration_status.setText("Calibrated")
                self.calibration_status.setStyleSheet(f"color: {COLORS['accent_green']}; font-size: 12px;")
                self.status_bar.showMessage(f"Calibration loaded from {filepath}")
            else:
                self.status_bar.showMessage("Failed to load calibration")

    def _open_setup_mode(self):
        """Open hardware setup mode dialog."""
        self.setup_dialog = SetupModeDialog(
            grid_rows=GRID_ROWS,
            grid_cols=GRID_COLS,
            initial_config=self.hardware_config,
            parent=self
        )
        self.setup_dialog.config_updated.connect(self._on_config_updated)
        self.setup_dialog.show()
        self.status_bar.showMessage("Hardware setup mode active")

    def _on_config_updated(self, config: HardwareConfig):
        """Handle updated hardware configuration."""
        self.hardware_config = config
        save_default_config(config)
        self.status_bar.showMessage("Hardware configuration saved")

    def _start_recording(self):
        """Start recording session."""
        self.is_recording = True
        self.recording_data_raw = []
        self.recording_data_annotated = []
        self.recording_start_time = time.time()

        # Start screen recording if available
        if RECORDING_AVAILABLE:
            # Get window geometry
            geom = self.geometry()
            region = {
                'left': geom.x(),
                'top': geom.y(),
                'width': geom.width(),
                'height': geom.height()
            }

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_path = f"recording_{timestamp}.mp4"

            self.screen_recorder = ScreenRecorder(video_path, region)
            self.screen_recorder.start()

        self.status_bar.showMessage("Recording started")

    def _stop_recording(self):
        """Stop recording and export data."""
        self.is_recording = False
        self.drift_warning.hide_warning()

        # Stop screen recorder
        if self.screen_recorder:
            self.screen_recorder.stop()
            self.screen_recorder = None

        # Export data
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Export raw CSV
        raw_csv_path = f"recording_raw_{timestamp}.csv"
        self._export_raw_csv(raw_csv_path)

        # Export annotated CSV
        annotated_csv_path = f"recording_annotated_{timestamp}.csv"
        self._export_annotated_csv(annotated_csv_path)

        # Export graph image
        if EXPORT_AVAILABLE:
            graph_path = f"recording_graph_{timestamp}.pdf"
            self._export_graph(graph_path)

        self.status_bar.showMessage(f"Recording saved: {raw_csv_path}")

    def _export_raw_csv(self, filepath: str):
        """Export raw grid data to CSV."""
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header
            header = ['frame'] + [f'r{r}c{c}' for r in range(GRID_ROWS) for c in range(GRID_COLS)]
            writer.writerow(header)

            # Data
            for i, frame in enumerate(self.recording_data_raw):
                row = [i] + frame.flatten().tolist()
                writer.writerow(row)

    def _export_annotated_csv(self, filepath: str):
        """Export annotated data to CSV."""
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow(['timestamp', 'max_pressure', 'pos_row', 'pos_col',
                           'nearest_landmark', 'distance_to_landmark'])

            # Data
            for data in self.recording_data_annotated:
                pos = data['position']
                row = [
                    f"{data['timestamp']:.3f}",
                    data['max_pressure'],
                    f"{pos[0]:.2f}" if pos else '',
                    f"{pos[1]:.2f}" if pos else '',
                    data['nearest_landmark'] or '',
                    f"{data['distance']:.2f}" if data['distance'] else ''
                ]
                writer.writerow(row)

    def _export_graph(self, filepath: str):
        """Export waveform graph to PDF."""
        if not self.waveform_history:
            return

        fig, ax = plt.subplots(figsize=(10, 4))

        y_data = list(self.waveform_history)
        x_data = list(self.waveform_time)

        ax.plot(x_data, y_data, color='#0a84ff', linewidth=1.5)
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('ADC Value')
        ax.set_title('Force vs Time')
        ax.set_ylim(0, 4095)
        ax.grid(True, alpha=0.3)

        # Add stats
        if y_data:
            ax.axhline(y=max(y_data), color='#30d158', linestyle='--', alpha=0.5, label=f'Peak: {max(y_data)}')
            ax.axhline(y=min(y_data), color='#ff453a', linestyle='--', alpha=0.5, label=f'Trough: {min(y_data)}')
            ax.legend()

        fig.tight_layout()
        fig.savefig(filepath, format='pdf', dpi=150)
        plt.close(fig)

    def closeEvent(self, event):
        """Clean up on window close."""
        if self.serial_reader:
            self.serial_reader.stop()
        if self.screen_recorder:
            self.screen_recorder.stop()
        self.demo_timer.stop()
        event.accept()


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    """Application entry point."""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = GridVisualizerWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
