"""
================================================================================
20×12 Piezoelectric Force Sensing Grid - GUI Application
================================================================================

Physiotherapy Training System - Real-time pressure visualization with spinal
landmark detection and palpation feedback.

Features:
- Real-time 20×12 heatmap display with landmark overlay
- Hardware setup mode for GPIO/ADC configuration
- Spine-line calibration workflow
- L1-L5 vertebra visualization
- Palpation pressure feedback (0-15N velostat range)
- Movement speed feedback
- Force-over-time waveform graph for selected cell
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
from collections import deque
from typing import Optional
from pathlib import Path

import numpy as np
import serial
import serial.tools.list_ports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QStatusBar, QGroupBox, QSpinBox,
    QSlider, QFrame, QProgressBar, QDialog, QDialogButtonBox, QFileDialog
)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QPalette, QColor, QPainter, QPen, QBrush
import pyqtgraph as pg

# Import spine detector module
from spine_detector import (
    SpineDetector, MovementTracker, PalpationZones, SpeedZones,
    SpinalLandmark, SpineCalibration
)

# Import hardware configuration and setup
from hardware_config import HardwareConfig, get_default_config, save_default_config
from setup_dialog import SetupModeDialog


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

# UI Colors (dark theme)
DARK_BG = "#1e1e2e"
DARK_SURFACE = "#313244"
DARK_TEXT = "#cdd6f4"
ACCENT_BLUE = "#89b4fa"
ACCENT_GREEN = "#a6e3a1"
ACCENT_RED = "#f38ba8"
ACCENT_YELLOW = "#f9e2af"
ACCENT_ORANGE = "#fab387"
ACCENT_PURPLE = "#cba6f7"


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
# Calibration Dialog
# ============================================================================

class CalibrationDialog(QDialog):
    """Dialog for spine calibration wizard."""
    
    calibration_complete = pyqtSignal(object)  # Emits SpineDetector
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Spine Calibration Wizard")
        self.setMinimumSize(500, 300)
        self.setModal(True)
        
        self.detector = SpineDetector()
        self._is_recording = False
        
        self._build_ui()
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        
        # Instructions
        self.instruction_label = QLabel(
            "Calibration Instructions:\n\n"
            "1. Place the sensing mat on the patient's lower back\n"
            "2. Click 'Start Recording' below\n"
            "3. Drag your finger firmly along the spine from top to bottom\n"
            "4. Maintain consistent pressure throughout\n"
            "5. Click 'Stop Recording' when done"
        )
        self.instruction_label.setWordWrap(True)
        self.instruction_label.setStyleSheet("font-size: 12px; padding: 10px;")
        layout.addWidget(self.instruction_label)
        
        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        
        # Status
        self.status_label = QLabel("Ready to calibrate")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet(f"color: {ACCENT_YELLOW}; font-weight: bold;")
        layout.addWidget(self.status_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.record_btn = QPushButton("▶ Start Recording")
        self.record_btn.clicked.connect(self._toggle_recording)
        self.record_btn.setStyleSheet(f"background-color: {ACCENT_GREEN}; color: {DARK_BG};")
        btn_layout.addWidget(self.record_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(btn_layout)
        
        # Frame counter
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
        self.record_btn.setText("⏹ Stop Recording")
        self.record_btn.setStyleSheet(f"background-color: {ACCENT_RED}; color: {DARK_BG};")
        self.status_label.setText("Recording... Drag finger along spine!")
        self.status_label.setStyleSheet(f"color: {ACCENT_GREEN}; font-weight: bold;")
    
    def _stop_recording(self):
        self._is_recording = False
        self.record_btn.setText("▶ Start Recording")
        self.record_btn.setStyleSheet(f"background-color: {ACCENT_GREEN}; color: {DARK_BG};")
        
        # Finalize calibration
        success, message = self.detector.finalize_calibration()
        
        if success:
            self.status_label.setText(f"✓ {message}")
            self.status_label.setStyleSheet(f"color: {ACCENT_GREEN}; font-weight: bold;")
            self.progress_bar.setValue(100)
            
            # Auto-accept after success
            QTimer.singleShot(1500, self._accept_calibration)
        else:
            self.status_label.setText(f"✗ {message}")
            self.status_label.setStyleSheet(f"color: {ACCENT_RED}; font-weight: bold;")
            self.progress_bar.setValue(0)
    
    def _accept_calibration(self):
        self.calibration_complete.emit(self.detector)
        self.accept()
    
    def add_frame(self, frame: np.ndarray):
        """Add a pressure frame during recording."""
        if self._is_recording:
            self.detector.add_calibration_frame(frame)
            self._frame_count += 1
            
            # Update progress (aim for ~50 frames)
            progress = min(100, int(self._frame_count / 50 * 100))
            self.progress_bar.setValue(progress)


# ============================================================================
# Landmark Overlay Widget
# ============================================================================

class LandmarkOverlay(pg.GraphicsObject):
    """Overlay for drawing spinal landmarks on heatmap."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.landmarks: list = []
        self.spine_line = None
        self.show_labels = True
        self.highlight_landmark = None
    
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
            pen = QPen(QColor(ACCENT_PURPLE))
            pen.setWidth(2)
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
            
            # Choose color based on type
            if lm.landmark_type == 'spinous':
                color = QColor(ACCENT_GREEN) if is_highlighted else QColor(ACCENT_BLUE)
                size = 4 if is_highlighted else 3
            else:
                color = QColor(ACCENT_YELLOW) if is_highlighted else QColor(ACCENT_ORANGE)
                size = 3 if is_highlighted else 2
            
            # Draw filled circle
            painter.setPen(QPen(color, 1))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(
                int(lm.col - size/2), int(lm.row - size/2),
                size, size
            )
            
            # Draw label for spinous processes
            if self.show_labels and lm.landmark_type == 'spinous':
                painter.setPen(QPen(QColor(DARK_TEXT)))
                font = painter.font()
                font.setPointSize(7)
                painter.setFont(font)
                painter.drawText(int(lm.col + 3), int(lm.row + 2), lm.level)


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
        
        # Pressure feedback
        pressure_group = QGroupBox("Pressure Feedback")
        pressure_layout = QVBoxLayout(pressure_group)
        
        self.pressure_bar = QProgressBar()
        self.pressure_bar.setRange(0, 4095)
        self.pressure_bar.setTextVisible(False)
        pressure_layout.addWidget(self.pressure_bar)
        
        self.pressure_label = QLabel("No contact")
        self.pressure_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pressure_label.setStyleSheet("font-weight: bold;")
        pressure_layout.addWidget(self.pressure_label)
        
        layout.addWidget(pressure_group)
        
        # Speed feedback
        speed_group = QGroupBox("Movement Speed")
        speed_layout = QVBoxLayout(speed_group)
        
        self.speed_bar = QProgressBar()
        self.speed_bar.setRange(0, 100)
        self.speed_bar.setTextVisible(False)
        speed_layout.addWidget(self.speed_bar)
        
        self.speed_label = QLabel("Stationary")
        self.speed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.speed_label.setStyleSheet("font-weight: bold;")
        speed_layout.addWidget(self.speed_label)
        
        layout.addWidget(speed_group)
        
        # Target feedback
        target_group = QGroupBox("Target Guidance")
        target_layout = QVBoxLayout(target_group)
        
        self.target_label = QLabel("Calibrate to enable guidance")
        self.target_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.target_label.setWordWrap(True)
        self.target_label.setStyleSheet(f"color: {ACCENT_YELLOW};")
        target_layout.addWidget(self.target_label)
        
        self.distance_label = QLabel("")
        self.distance_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        target_layout.addWidget(self.distance_label)
        
        layout.addWidget(target_group)
    
    def update_pressure(self, value: int):
        """Update pressure display."""
        self.pressure_bar.setValue(value)
        zone_name, color, message = PalpationZones.get_zone(value)
        self.pressure_label.setText(message)
        self.pressure_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        
        # Color the progress bar
        self.pressure_bar.setStyleSheet(f"""
            QProgressBar::chunk {{
                background-color: {color};
            }}
        """)
    
    def update_speed(self, speed: float):
        """Update speed display."""
        # Normalize speed for progress bar (0-25 cells/sec -> 0-100%)
        normalized = min(100, int(speed * 4))
        self.speed_bar.setValue(normalized)
        
        zone_name, color, message = SpeedZones.get_zone(speed)
        self.speed_label.setText(f"{message} ({speed:.1f} cells/s)")
        self.speed_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        
        self.speed_bar.setStyleSheet(f"""
            QProgressBar::chunk {{
                background-color: {color};
            }}
        """)
    
    def update_target(self, feedback: dict):
        """Update target guidance from detector feedback."""
        if feedback['nearest_landmark'] is None:
            self.target_label.setText("Calibrate to enable guidance")
            self.distance_label.setText("")
            return
        
        lm = feedback['nearest_landmark']
        dist = feedback['distance_to_landmark']
        
        if feedback['on_target']:
            self.target_label.setText(f"✓ On {lm.level} {lm.landmark_type}")
            self.target_label.setStyleSheet(f"color: {ACCENT_GREEN}; font-weight: bold;")
        else:
            self.target_label.setText(feedback['feedback'])
            self.target_label.setStyleSheet(f"color: {ACCENT_YELLOW}; font-weight: bold;")
        
        self.distance_label.setText(f"Distance: {dist:.1f} cells")


# ============================================================================
# Main Window
# ============================================================================

class GridVisualizerWindow(QMainWindow):
    """Main application window with heatmap, calibration, and feedback."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("20×12 Force Sensing Grid - Physiotherapy Training")
        self.setMinimumSize(1400, 900)
        
        # Data storage
        self.grid_data = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.uint16)
        self.selected_row = GRID_ROWS // 2
        self.selected_col = GRID_COLS // 2
        self.waveform_history = deque(maxlen=WAVEFORM_HISTORY_SIZE)
        self.frame_count = 0
        self.start_time = time.time()
        
        # Serial connection
        self.serial_reader: Optional[SerialReader] = None
        
        # Spine detection
        self.spine_detector = SpineDetector()
        self.movement_tracker = MovementTracker()

        # Calibration dialog reference
        self.calibration_dialog: Optional[CalibrationDialog] = None

        # Hardware configuration
        self.hardware_config = get_default_config()
        self.setup_dialog: Optional[SetupModeDialog] = None
        
        # Apply dark theme
        self._apply_dark_theme()
        
        # Build UI
        self._build_ui()
        
        # Demo timer
        self.demo_timer = QTimer()
        self.demo_timer.timeout.connect(self._generate_demo_data)
    
    def _apply_dark_theme(self):
        """Apply dark color scheme."""
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{
                background-color: {DARK_BG};
                color: {DARK_TEXT};
            }}
            QGroupBox {{
                border: 1px solid {DARK_SURFACE};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
            QPushButton {{
                background-color: {DARK_SURFACE};
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {ACCENT_BLUE};
                color: {DARK_BG};
            }}
            QPushButton:pressed {{
                background-color: {ACCENT_GREEN};
            }}
            QComboBox {{
                background-color: {DARK_SURFACE};
                border: 1px solid {DARK_SURFACE};
                border-radius: 4px;
                padding: 5px;
            }}
            QLabel {{
                color: {DARK_TEXT};
            }}
            QStatusBar {{
                background-color: {DARK_SURFACE};
            }}
            QProgressBar {{
                border: 1px solid {DARK_SURFACE};
                border-radius: 4px;
                background-color: {DARK_BG};
                height: 20px;
            }}
            QProgressBar::chunk {{
                background-color: {ACCENT_BLUE};
                border-radius: 3px;
            }}
        """)
    
    def _build_ui(self):
        """Construct the user interface."""
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # ---- Left Panel: Heatmap ----
        left_panel = QVBoxLayout()
        
        # Heatmap title with calibration status
        title_layout = QHBoxLayout()
        heatmap_label = QLabel("Real-time Pressure Heatmap")
        heatmap_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title_layout.addWidget(heatmap_label)
        
        self.calibration_status = QLabel("● Not Calibrated")
        self.calibration_status.setStyleSheet(f"color: {ACCENT_YELLOW};")
        title_layout.addWidget(self.calibration_status)
        title_layout.addStretch()
        
        left_panel.addLayout(title_layout)
        
        # Heatmap with overlay
        self.heatmap_widget = pg.PlotWidget()
        self.heatmap_widget.setAspectLocked(True)
        self.heatmap_widget.hideAxis('left')
        self.heatmap_widget.hideAxis('bottom')
        
        # Create ImageItem for heatmap
        self.heatmap_image = pg.ImageItem()
        self.heatmap_widget.addItem(self.heatmap_image)
        
        # Set colormap
        colors = [
            (0, 0, 128),      # Dark blue
            (0, 0, 255),      # Blue
            (0, 255, 255),    # Cyan
            (0, 255, 0),      # Green
            (255, 255, 0),    # Yellow
            (255, 128, 0),    # Orange
            (255, 0, 0),      # Red
        ]
        positions = np.linspace(0, 1, len(colors))
        colormap = pg.ColorMap(positions, colors)
        self.heatmap_image.setLookupTable(colormap.getLookupTable())
        self.heatmap_image.setLevels([0, 4095])
        
        # Initial empty image
        self.heatmap_image.setImage(self.grid_data.T)
        
        # Add landmark overlay
        self.landmark_overlay = LandmarkOverlay()
        self.heatmap_widget.addItem(self.landmark_overlay)
        
        # Click handler
        self.heatmap_widget.scene().sigMouseClicked.connect(self._on_heatmap_click)
        
        left_panel.addWidget(self.heatmap_widget, stretch=1)
        
        # Legend
        legend_layout = QHBoxLayout()
        legend_layout.addWidget(QLabel("No Pressure"))
        legend_layout.addStretch()
        legend_layout.addWidget(QLabel("Maximum Pressure"))
        left_panel.addLayout(legend_layout)
        
        main_layout.addLayout(left_panel, stretch=2)
        
        # ---- Right Panel: Controls + Feedback ----
        right_panel = QVBoxLayout()
        
        # Feedback panel
        self.feedback_panel = FeedbackPanel()
        right_panel.addWidget(self.feedback_panel)
        
        # Waveform graph
        waveform_group = QGroupBox("Force vs Time")
        waveform_layout = QVBoxLayout(waveform_group)
        
        self.waveform_plot = pg.PlotWidget()
        self.waveform_plot.setBackground(DARK_SURFACE)
        self.waveform_plot.setLabel('left', 'Pressure', units='raw')
        self.waveform_plot.setLabel('bottom', 'Time', units='s')
        self.waveform_plot.setYRange(0, 4095)
        self.waveform_plot.showGrid(x=True, y=True, alpha=0.3)
        self.waveform_plot.setMaximumHeight(150)
        
        self.waveform_curve = self.waveform_plot.plot(
            pen=pg.mkPen(color=ACCENT_BLUE, width=2)
        )
        waveform_layout.addWidget(self.waveform_plot)
        
        self.selected_label = QLabel(f"Selected: Row {self.selected_row}, Col {self.selected_col}")
        self.selected_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selected_label.setStyleSheet(f"color: {ACCENT_YELLOW}; font-weight: bold;")
        waveform_layout.addWidget(self.selected_label)
        
        right_panel.addWidget(waveform_group)
        
        # Controls
        controls_group = QGroupBox("Controls")
        controls_layout = QVBoxLayout(controls_group)
        
        # COM port
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("COM Port:"))
        self.port_combo = QComboBox()
        self._refresh_ports()
        port_layout.addWidget(self.port_combo, stretch=1)
        
        self.refresh_btn = QPushButton("🔄")
        self.refresh_btn.setMaximumWidth(40)
        self.refresh_btn.clicked.connect(self._refresh_ports)
        port_layout.addWidget(self.refresh_btn)
        controls_layout.addLayout(port_layout)
        
        # Connect/Demo buttons
        btn_layout = QHBoxLayout()
        self.connect_btn = QPushButton("▶ Connect")
        self.connect_btn.clicked.connect(self._toggle_connection)
        self.connect_btn.setStyleSheet(f"background-color: {ACCENT_GREEN}; color: {DARK_BG};")
        btn_layout.addWidget(self.connect_btn)
        
        self.demo_btn = QPushButton("🎮 Demo")
        self.demo_btn.clicked.connect(self._toggle_demo)
        btn_layout.addWidget(self.demo_btn)
        controls_layout.addLayout(btn_layout)
        
        # Setup Mode button
        self.setup_btn = QPushButton("⚙ Hardware Setup Mode")
        self.setup_btn.clicked.connect(self._open_setup_mode)
        self.setup_btn.setStyleSheet(f"background-color: {ACCENT_PURPLE}; color: {DARK_BG};")
        controls_layout.addWidget(self.setup_btn)

        # Calibration buttons
        calib_layout = QHBoxLayout()
        self.calibrate_btn = QPushButton("🎯 Calibrate Spine")
        self.calibrate_btn.clicked.connect(self._start_calibration)
        calib_layout.addWidget(self.calibrate_btn)

        self.load_calib_btn = QPushButton("📂 Load")
        self.load_calib_btn.clicked.connect(self._load_calibration)
        self.load_calib_btn.setMaximumWidth(60)
        calib_layout.addWidget(self.load_calib_btn)

        self.save_calib_btn = QPushButton("💾 Save")
        self.save_calib_btn.clicked.connect(self._save_calibration)
        self.save_calib_btn.setMaximumWidth(60)
        calib_layout.addWidget(self.save_calib_btn)
        controls_layout.addLayout(calib_layout)
        
        right_panel.addWidget(controls_group)
        
        # Stats
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        self.fps_label = QLabel("FPS: 0")
        self.max_label = QLabel("Max Value: 0")
        self.avg_label = QLabel("Avg Value: 0")
        
        stats_layout.addWidget(self.fps_label)
        stats_layout.addWidget(self.max_label)
        stats_layout.addWidget(self.avg_label)
        
        right_panel.addWidget(stats_group)
        right_panel.addStretch()
        
        main_layout.addLayout(right_panel, stretch=1)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Calibrate spine or connect to start")
    
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
            self.connect_btn.setText("▶ Connect")
            self.connect_btn.setStyleSheet(f"background-color: {ACCENT_GREEN}; color: {DARK_BG};")
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
            
            self.connect_btn.setText("⏹ Disconnect")
            self.connect_btn.setStyleSheet(f"background-color: {ACCENT_RED}; color: {DARK_BG};")
            self.status_bar.showMessage(f"Connected to {port}")
    
    def _toggle_demo(self):
        """Toggle demo mode."""
        if self.demo_timer.isActive():
            self.demo_timer.stop()
            self.demo_btn.setText("🎮 Demo")
            self.status_bar.showMessage("Demo mode stopped")
        else:
            self.demo_timer.start(40)
            self.demo_btn.setText("⏹ Stop")
            self.status_bar.showMessage("Demo mode active - simulating spinal palpation")
    
    def _generate_demo_data(self):
        """Generate demo data simulating spine palpation."""
        t = time.time()
        
        # Simulate finger position moving along spine
        spine_col = GRID_COLS / 2 + np.sin(t * 0.3) * 3  # Slight lateral movement
        spine_row = 5 + ((t * 3) % 30)  # Move up and down
        
        # Generate pressure around finger position
        data = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.uint16)
        for i in range(GRID_ROWS):
            for j in range(GRID_COLS):
                dist = np.sqrt((i - spine_row)**2 + (j - spine_col)**2)
                # Finger-sized pressure spot with realistic velostat range
                data[i, j] = int(2000 * np.exp(-dist**2 / 8))
        
        # Add noise
        data = data + np.random.randint(0, 50, data.shape, dtype=np.uint16)
        
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
        
        # Update feedback
        max_pressure = int(np.max(data))
        self.feedback_panel.update_pressure(max_pressure)
        self.feedback_panel.update_speed(speed)
        
        # Get technique feedback if calibrated
        if pos and self.spine_detector.calibration.is_calibrated:
            feedback = self.spine_detector.get_technique_feedback(
                pos[0], pos[1], max_pressure
            )
            self.feedback_panel.update_target(feedback)
            
            # Highlight nearest landmark
            if feedback['nearest_landmark']:
                self.landmark_overlay.highlight(feedback['nearest_landmark'])
        
        # Update waveform
        cell_value = data[self.selected_row, self.selected_col]
        self.waveform_history.append(cell_value)
        
        if len(self.waveform_history) > 1:
            time_axis = np.linspace(0, len(self.waveform_history) / 25, len(self.waveform_history))
            self.waveform_curve.setData(time_axis, list(self.waveform_history))
        
        # Update stats
        elapsed = current_time - self.start_time
        if elapsed > 0:
            fps = self.frame_count / elapsed
            self.fps_label.setText(f"FPS: {fps:.1f}")
        
        self.max_label.setText(f"Max Value: {max_pressure}")
        self.avg_label.setText(f"Avg Value: {np.mean(data):.0f}")
    
    def _on_serial_error(self, error: str):
        """Handle serial errors."""
        self.status_bar.showMessage(f"Error: {error}")
        self.connect_btn.setText("▶ Connect")
        self.connect_btn.setStyleSheet(f"background-color: {ACCENT_GREEN}; color: {DARK_BG};")
    
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
    
    def _start_calibration(self):
        """Open calibration dialog."""
        self.calibration_dialog = CalibrationDialog(self)
        self.calibration_dialog.calibration_complete.connect(self._on_calibration_complete)
        self.calibration_dialog.show()
    
    def _on_calibration_complete(self, detector: SpineDetector):
        """Handle completed calibration."""
        self.spine_detector = detector
        
        # Update overlay
        if detector.calibration.is_calibrated:
            self.landmark_overlay.set_landmarks(
                detector.calibration.landmarks,
                detector.calibration.spine_line
            )
            self.calibration_status.setText("✓ Calibrated")
            self.calibration_status.setStyleSheet(f"color: {ACCENT_GREEN};")
            self.status_bar.showMessage("Calibration complete! Landmarks visible on heatmap")
        
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
                self.calibration_status.setText("✓ Calibrated")
                self.calibration_status.setStyleSheet(f"color: {ACCENT_GREEN};")
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
        self.status_bar.showMessage("Hardware setup mode active - press on grid to configure")

    def _on_config_updated(self, config: HardwareConfig):
        """Handle updated hardware configuration."""
        self.hardware_config = config
        save_default_config(config)
        self.status_bar.showMessage("Hardware configuration updated and saved")
    
    def closeEvent(self, event):
        """Clean up on window close."""
        if self.serial_reader:
            self.serial_reader.stop()
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
