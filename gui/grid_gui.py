"""
================================================================================
40×40 Piezoelectric Force Sensing Grid - GUI Application
================================================================================

Physiotherapy Training System - Real-time pressure visualization

Features:
- Real-time 40×40 heatmap display
- Force-over-time waveform graph for selected cell
- Calibration support
- Binary protocol communication with STM32

Usage:
    python grid_gui.py

Author: Capstone Project
Date: 2026-01-12
================================================================================
"""

import sys
import struct
import time
from collections import deque
from typing import Optional

import numpy as np
import serial
import serial.tools.list_ports
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QStatusBar, QGroupBox, QSpinBox,
    QSlider, QFrame
)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QPalette, QColor
import pyqtgraph as pg


# ============================================================================
# Constants
# ============================================================================

GRID_ROWS = 40
GRID_COLS = 40
GRID_TOTAL = GRID_ROWS * GRID_COLS  # 1600

# Binary protocol
SYNC_BYTE_1 = 0xAA
SYNC_BYTE_2 = 0x55
HEADER_SIZE = 2
PAYLOAD_SIZE = GRID_TOTAL * 2  # 3200 bytes (16-bit values)
FOOTER_SIZE = 4  # 2-byte checksum + CR + LF
PACKET_SIZE = HEADER_SIZE + PAYLOAD_SIZE + FOOTER_SIZE  # 3206 bytes

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


# ============================================================================
# Serial Reader Thread
# ============================================================================

class SerialReader(QThread):
    """Background thread for reading serial data."""
    
    data_received = pyqtSignal(np.ndarray)  # Emits 40x40 numpy array
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
                        # No sync found, keep last byte (might be start of sync)
                        buffer = buffer[-1:]
                        break
                    
                    # Discard bytes before sync
                    if sync_idx > 0:
                        buffer = buffer[sync_idx:]
                    
                    # Check if we have complete packet
                    if len(buffer) < PACKET_SIZE:
                        break
                    
                    # Extract packet
                    packet = buffer[:PACKET_SIZE]
                    buffer = buffer[PACKET_SIZE:]
                    
                    # Parse payload (skip 2-byte header)
                    payload = packet[HEADER_SIZE:HEADER_SIZE + PAYLOAD_SIZE]
                    
                    # Verify checksum
                    expected_checksum = struct.unpack('<H', 
                        packet[HEADER_SIZE + PAYLOAD_SIZE:HEADER_SIZE + PAYLOAD_SIZE + 2])[0]
                    actual_checksum = sum(payload) & 0xFFFF
                    
                    if expected_checksum != actual_checksum:
                        continue  # Skip corrupted packet
                    
                    # Unpack 16-bit values (little-endian)
                    values = struct.unpack(f'<{GRID_TOTAL}H', payload)
                    grid_data = np.array(values, dtype=np.uint16).reshape(GRID_ROWS, GRID_COLS)
                    
                    self.data_received.emit(grid_data)
                
                time.sleep(0.001)  # Prevent CPU spinning
                
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
# Main Window
# ============================================================================

class GridVisualizerWindow(QMainWindow):
    """Main application window with heatmap and waveform display."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("40×40 Force Sensing Grid - Physiotherapy Training")
        self.setMinimumSize(1200, 800)
        
        # Data storage
        self.grid_data = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.uint16)
        self.selected_row = GRID_ROWS // 2
        self.selected_col = GRID_COLS // 2
        self.waveform_history = deque(maxlen=WAVEFORM_HISTORY_SIZE)
        self.frame_count = 0
        self.start_time = time.time()
        
        # Serial connection
        self.serial_reader: Optional[SerialReader] = None
        
        # Apply dark theme
        self._apply_dark_theme()
        
        # Build UI
        self._build_ui()
        
        # Demo timer (for testing without hardware)
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
        
        # Heatmap title
        heatmap_label = QLabel("Real-time Pressure Heatmap")
        heatmap_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        heatmap_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_panel.addWidget(heatmap_label)
        
        # PyQtGraph ImageView for heatmap
        self.heatmap_widget = pg.ImageView()
        self.heatmap_widget.ui.roiBtn.hide()
        self.heatmap_widget.ui.menuBtn.hide()
        self.heatmap_widget.ui.histogram.hide()
        
        # Set colormap (jet-like)
        colors = [
            (0, 0, 0.5),      # Dark blue
            (0, 0, 1),        # Blue
            (0, 1, 1),        # Cyan
            (0, 1, 0),        # Green
            (1, 1, 0),        # Yellow
            (1, 0.5, 0),      # Orange
            (1, 0, 0),        # Red
        ]
        positions = np.linspace(0, 1, len(colors))
        colormap = pg.ColorMap(positions, [tuple(int(c*255) for c in color) for color in colors])
        self.heatmap_widget.setColorMap(colormap)
        self.heatmap_widget.setLevels(0, 4095)
        
        # Initial empty image
        self.heatmap_widget.setImage(self.grid_data.T)
        
        # Click handler for cell selection
        self.heatmap_widget.getView().scene().sigMouseClicked.connect(self._on_heatmap_click)
        
        left_panel.addWidget(self.heatmap_widget, stretch=1)
        
        # Color bar legend
        legend_layout = QHBoxLayout()
        legend_layout.addWidget(QLabel("No Pressure"))
        legend_layout.addStretch()
        legend_layout.addWidget(QLabel("Maximum Pressure"))
        left_panel.addLayout(legend_layout)
        
        main_layout.addLayout(left_panel, stretch=2)
        
        # ---- Right Panel: Waveform + Controls ----
        right_panel = QVBoxLayout()
        
        # Waveform graph
        waveform_group = QGroupBox("Force vs Time (Selected Cell)")
        waveform_layout = QVBoxLayout(waveform_group)
        
        self.waveform_plot = pg.PlotWidget()
        self.waveform_plot.setBackground(DARK_SURFACE)
        self.waveform_plot.setLabel('left', 'Pressure', units='raw')
        self.waveform_plot.setLabel('bottom', 'Time', units='s')
        self.waveform_plot.setYRange(0, 4095)
        self.waveform_plot.showGrid(x=True, y=True, alpha=0.3)
        
        self.waveform_curve = self.waveform_plot.plot(
            pen=pg.mkPen(color=ACCENT_BLUE, width=2)
        )
        
        waveform_layout.addWidget(self.waveform_plot)
        
        # Selected cell indicator
        self.selected_label = QLabel(f"Selected: Row {self.selected_row}, Col {self.selected_col}")
        self.selected_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selected_label.setStyleSheet(f"color: {ACCENT_YELLOW}; font-weight: bold;")
        waveform_layout.addWidget(self.selected_label)
        
        right_panel.addWidget(waveform_group, stretch=1)
        
        # Controls
        controls_group = QGroupBox("Controls")
        controls_layout = QVBoxLayout(controls_group)
        
        # COM port selection
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
        
        # Connect/Disconnect buttons
        btn_layout = QHBoxLayout()
        self.connect_btn = QPushButton("▶ Connect")
        self.connect_btn.clicked.connect(self._toggle_connection)
        self.connect_btn.setStyleSheet(f"background-color: {ACCENT_GREEN}; color: {DARK_BG};")
        btn_layout.addWidget(self.connect_btn)
        
        self.demo_btn = QPushButton("🎮 Demo Mode")
        self.demo_btn.clicked.connect(self._toggle_demo)
        btn_layout.addWidget(self.demo_btn)
        controls_layout.addLayout(btn_layout)
        
        # Calibrate button
        self.calibrate_btn = QPushButton("🔧 Calibrate")
        self.calibrate_btn.clicked.connect(self._calibrate)
        controls_layout.addWidget(self.calibrate_btn)
        
        right_panel.addWidget(controls_group)
        
        # Stats display
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        self.fps_label = QLabel("FPS: 0")
        self.max_label = QLabel("Max Value: 0")
        self.avg_label = QLabel("Avg Value: 0")
        
        stats_layout.addWidget(self.fps_label)
        stats_layout.addWidget(self.max_label)
        stats_layout.addWidget(self.avg_label)
        
        right_panel.addWidget(stats_group)
        
        main_layout.addLayout(right_panel, stretch=1)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Select COM port and click Connect")
    
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
            # Disconnect
            self.serial_reader.stop()
            self.serial_reader = None
            self.connect_btn.setText("▶ Connect")
            self.connect_btn.setStyleSheet(f"background-color: {ACCENT_GREEN}; color: {DARK_BG};")
            self.status_bar.showMessage("Disconnected")
        else:
            # Connect
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
        """Toggle demo mode for testing without hardware."""
        if self.demo_timer.isActive():
            self.demo_timer.stop()
            self.demo_btn.setText("🎮 Demo Mode")
            self.status_bar.showMessage("Demo mode stopped")
        else:
            self.demo_timer.start(40)  # ~25 Hz
            self.demo_btn.setText("⏹ Stop Demo")
            self.status_bar.showMessage("Demo mode active - simulating pressure data")
    
    def _generate_demo_data(self):
        """Generate fake pressure data for demo mode."""
        # Create moving pressure spots
        t = time.time() * 0.5
        x = int((np.sin(t) * 0.4 + 0.5) * GRID_COLS)
        y = int((np.cos(t * 0.7) * 0.4 + 0.5) * GRID_ROWS)
        
        # Gaussian-like pressure distribution
        data = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.uint16)
        for i in range(GRID_ROWS):
            for j in range(GRID_COLS):
                dist = np.sqrt((i - y)**2 + (j - x)**2)
                data[i, j] = int(4000 * np.exp(-dist**2 / 50))
        
        # Add some noise
        data = data + np.random.randint(0, 100, data.shape, dtype=np.uint16)
        
        self._on_data_received(data)
    
    def _on_data_received(self, data: np.ndarray):
        """Handle received grid data."""
        self.grid_data = data
        self.frame_count += 1
        
        # Update heatmap
        self.heatmap_widget.setImage(data.T, autoLevels=False)
        
        # Update waveform for selected cell
        cell_value = data[self.selected_row, self.selected_col]
        self.waveform_history.append(cell_value)
        
        if len(self.waveform_history) > 1:
            time_axis = np.linspace(0, len(self.waveform_history) / 25, len(self.waveform_history))
            self.waveform_curve.setData(time_axis, list(self.waveform_history))
        
        # Update statistics
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            fps = self.frame_count / elapsed
            self.fps_label.setText(f"FPS: {fps:.1f}")
        
        self.max_label.setText(f"Max Value: {np.max(data)}")
        self.avg_label.setText(f"Avg Value: {np.mean(data):.0f}")
    
    def _on_serial_error(self, error: str):
        """Handle serial errors."""
        self.status_bar.showMessage(f"Error: {error}")
        self.connect_btn.setText("▶ Connect")
        self.connect_btn.setStyleSheet(f"background-color: {ACCENT_GREEN}; color: {DARK_BG};")
    
    def _on_heatmap_click(self, event):
        """Handle click on heatmap to select cell."""
        pos = event.scenePos()
        view = self.heatmap_widget.getView()
        
        if view.sceneBoundingRect().contains(pos):
            mouse_point = view.mapSceneToView(pos)
            col = int(mouse_point.x())
            row = int(mouse_point.y())
            
            if 0 <= row < GRID_ROWS and 0 <= col < GRID_COLS:
                self.selected_row = row
                self.selected_col = col
                self.selected_label.setText(f"Selected: Row {row}, Col {col}")
                self.waveform_history.clear()
    
    def _calibrate(self):
        """Trigger calibration (placeholder)."""
        self.status_bar.showMessage("Calibration: Not implemented in GUI - use STM32 button")
    
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
