"""
================================================================================
Main Window - Application Core
================================================================================

This module contains the main application window that ties together all
components: visualization, controls, recording, and feedback.

Design Philosophy:
    "Simplicity is the ultimate sophistication." - Leonardo da Vinci
    "That's been one of my mantras - focus and simplicity." - Steve Jobs

The window is organized into clear sections:
    - Left side: Visualization (heatmap, graph, stats)
    - Right side: Controls (connection, calibration, recording)

The interface should feel intuitive without requiring a manual.
"""

import sys
import csv
import time
from collections import deque
from datetime import datetime
from typing import Optional, List

import numpy as np
import serial.tools.list_ports
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QStatusBar, QProgressBar, QFileDialog,
    QScrollArea, QApplication
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QFont, QColor
import pyqtgraph as pg

# Internal modules - support both package and direct execution
try:
    from .styles.theme import COLORS, HEATMAP_COLORS, FONT_FAMILY
    from .utils.constants import (
        GRID_ROWS, GRID_COLS, ADC_MIN, ADC_MAX,
        WAVEFORM_HISTORY_SIZE, COUNTDOWN_SECONDS, RECORDING_FPS
    )
    from .widgets import (
        AnimatedButton, FriendlyCard, StatDisplay,
        PulsingDot, ColorLegendWidget, LandmarkOverlay, DriftWarningWidget
    )
    from .core import SerialReader, FrequencyAnalyzer, ScreenRecorder, RECORDING_AVAILABLE
    from .dialogs import CalibrationDialog
except ImportError:
    from styles.theme import COLORS, HEATMAP_COLORS, FONT_FAMILY
    from utils.constants import (
        GRID_ROWS, GRID_COLS, ADC_MIN, ADC_MAX,
        WAVEFORM_HISTORY_SIZE, COUNTDOWN_SECONDS, RECORDING_FPS
    )
    from widgets import (
        AnimatedButton, FriendlyCard, StatDisplay,
        PulsingDot, ColorLegendWidget, LandmarkOverlay, DriftWarningWidget
    )
    from core import SerialReader, FrequencyAnalyzer, ScreenRecorder, RECORDING_AVAILABLE
    from dialogs import CalibrationDialog

# External modules
from spine_detector import (
    SpineDetector, MovementTracker, PalpationZones, SpineLine
)
from hardware_config import HardwareConfig, get_default_config, save_default_config
from setup_dialog import SetupModeDialog

# Optional export libraries
try:
    import matplotlib.pyplot as plt
    EXPORT_AVAILABLE = True
except ImportError:
    EXPORT_AVAILABLE = False


class GridVisualizerWindow(QMainWindow):
    """
    Main application window with friendly, animated design.

    The window provides:
        - Real-time pressure heatmap visualization
        - Waveform display for selected cell
        - Spinal landmark overlay after calibration
        - Recording with CSV and video export
        - Palpation frequency analysis
        - Drift detection during recording

    Example:
        >>> app = QApplication(sys.argv)
        >>> window = GridVisualizerWindow()
        >>> window.show()
        >>> sys.exit(app.exec())
    """

    def __init__(self):
        """Initialize the main window."""
        super().__init__()
        self.setWindowTitle("Physio Training System")
        self.setMinimumSize(1400, 900)

        # Initialize state
        self._init_data_state()
        self._init_connection_state()
        self._init_recording_state()

        # Build the UI
        self._build_ui()

        # Setup demo timer
        self.demo_timer = QTimer()
        self.demo_timer.timeout.connect(self._generate_demo_data)

    # =========================================================================
    # Initialization
    # =========================================================================

    def _init_data_state(self) -> None:
        """Initialize data-related state variables."""
        self.grid_data = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.uint16)
        self.selected_row = GRID_ROWS // 2
        self.selected_col = GRID_COLS // 2
        self.waveform_history = deque(maxlen=WAVEFORM_HISTORY_SIZE)
        self.waveform_time = deque(maxlen=WAVEFORM_HISTORY_SIZE)
        self.frame_count = 0
        self.start_time = time.time()
        self.graph_inverted = False

    def _init_connection_state(self) -> None:
        """Initialize connection-related state variables."""
        self.serial_reader: Optional[SerialReader] = None
        self.spine_detector = SpineDetector()
        self.movement_tracker = MovementTracker()
        self.frequency_analyzer = FrequencyAnalyzer()
        self.calibration_dialog: Optional[CalibrationDialog] = None
        self.hardware_config = get_default_config()
        self.setup_dialog = None

    def _init_recording_state(self) -> None:
        """Initialize recording-related state variables."""
        self.is_recording = False
        self.recording_data_raw: List[np.ndarray] = []
        self.recording_data_annotated: List[dict] = []
        self.recording_start_time: Optional[float] = None
        self.screen_recorder: Optional[ScreenRecorder] = None
        self.selected_target_landmark = None

    # =========================================================================
    # UI Building
    # =========================================================================

    def _build_ui(self) -> None:
        """Build the complete user interface."""
        self._apply_global_styles()

        # Main layout
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Left side: Display panel
        main_layout.addLayout(self._build_display_panel(), stretch=3)

        # Right side: Controls panel
        main_layout.addWidget(self._build_controls_panel())

        # Status bar
        self._build_status_bar()

        # Countdown timer for recording
        self.countdown_value = 0
        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self._countdown_tick)

    def _apply_global_styles(self) -> None:
        """Apply application-wide styles."""
        app = QApplication.instance()
        app.setFont(QFont("Comic Sans MS", 10))

        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {COLORS['bg_main']};
            }}
            QLabel {{
                font-family: {FONT_FAMILY};
            }}
            QComboBox {{
                font-family: {FONT_FAMILY};
                background-color: {COLORS['bg_card']};
                border: 2px solid {COLORS['border']};
                border-radius: 10px;
                padding: 10px 15px;
                font-size: 12px;
                color: {COLORS['text_dark']};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 15px;
            }}
            QComboBox:hover {{
                border-color: {COLORS['primary']};
            }}
            QStatusBar {{
                background-color: {COLORS['bg_card']};
                color: {COLORS['text_light']};
                font-family: {FONT_FAMILY};
                font-size: 11px;
                padding: 8px;
            }}
        """)

    def _build_display_panel(self) -> QVBoxLayout:
        """Build the left display panel with heatmap and graph."""
        layout = QVBoxLayout()
        layout.setSpacing(16)

        # Header
        header = QLabel("Pressure Heatmap")
        header.setFont(QFont("Comic Sans MS", 20, QFont.Weight.Bold))
        header.setStyleSheet(f"color: {COLORS['text_dark']};")
        layout.addWidget(header)

        # Heatmap card
        layout.addWidget(self._build_heatmap_card(), stretch=2)

        # Drift warning (positioned absolutely)
        self.drift_warning = DriftWarningWidget(self)
        self.drift_warning.move(250, 150)

        # Stats row
        layout.addLayout(self._build_stats_row())

        # Graph card
        layout.addWidget(self._build_graph_card(), stretch=1)

        return layout

    def _build_heatmap_card(self) -> FriendlyCard:
        """Build the heatmap visualization card."""
        card = FriendlyCard()
        heatmap_layout = QHBoxLayout()

        # Heatmap plot
        self.heatmap_widget = pg.PlotWidget()
        self.heatmap_widget.setAspectLocked(True)
        self.heatmap_widget.hideAxis('left')
        self.heatmap_widget.hideAxis('bottom')
        self.heatmap_widget.setBackground(COLORS['bg_card'])

        # Heatmap image
        self.heatmap_image = pg.ImageItem()
        self.heatmap_widget.addItem(self.heatmap_image)

        # Configure colormap
        positions = np.linspace(0, 1, len(HEATMAP_COLORS))
        colormap = pg.ColorMap(positions, HEATMAP_COLORS)
        self.heatmap_image.setLookupTable(colormap.getLookupTable())
        self.heatmap_image.setLevels([ADC_MIN, ADC_MAX])
        self.heatmap_image.setImage(self.grid_data.T)

        # Landmark overlay
        self.landmark_overlay = LandmarkOverlay()
        self.heatmap_widget.addItem(self.landmark_overlay)

        # Click handler
        self.heatmap_widget.scene().sigMouseClicked.connect(self._on_heatmap_click)

        heatmap_layout.addWidget(self.heatmap_widget, stretch=1)

        # Color legend
        self.color_legend = ColorLegendWidget()
        heatmap_layout.addWidget(self.color_legend)

        card.add_layout(heatmap_layout)
        return card

    def _build_stats_row(self) -> QHBoxLayout:
        """Build the statistics display row."""
        layout = QHBoxLayout()
        layout.setSpacing(12)

        self.peak_stat = StatDisplay("Peak", "0", COLORS['danger'])
        self.trough_stat = StatDisplay("Trough", "0", COLORS['info'])
        self.freq_stat = StatDisplay("Frequency", "0 Hz", COLORS['success'])
        self.fps_stat = StatDisplay("FPS", "0", COLORS['primary'])

        layout.addWidget(self.peak_stat)
        layout.addWidget(self.trough_stat)
        layout.addWidget(self.freq_stat)
        layout.addWidget(self.fps_stat)

        return layout

    def _build_graph_card(self) -> FriendlyCard:
        """Build the waveform graph card."""
        card = FriendlyCard("Force Over Time")

        # Header with flip button
        header = QHBoxLayout()

        self.selected_label = QLabel(f"Watching: Row {self.selected_row}, Col {self.selected_col}")
        self.selected_label.setFont(QFont("Comic Sans MS", 10))
        self.selected_label.setStyleSheet(
            f"color: {COLORS['text_light']}; background: transparent; border: none;"
        )
        header.addWidget(self.selected_label)
        header.addStretch()

        self.flip_btn = AnimatedButton("Flip View", "secondary")
        self.flip_btn.setFixedWidth(100)
        self.flip_btn.clicked.connect(self._toggle_graph_flip)
        header.addWidget(self.flip_btn)

        card.add_layout(header)

        # Waveform plot
        self.waveform_plot = pg.PlotWidget()
        self.waveform_plot.setBackground(COLORS['bg_card'])
        self.waveform_plot.setLabel('left', 'Value')
        self.waveform_plot.setLabel('bottom', 'Time (s)')
        self.waveform_plot.setYRange(0, 4095)
        self.waveform_plot.showGrid(x=True, y=True, alpha=0.2)

        self.waveform_curve = self.waveform_plot.plot(
            pen=pg.mkPen(color=COLORS['primary'], width=3)
        )

        card.add_widget(self.waveform_plot)
        return card

    def _build_controls_panel(self) -> QScrollArea:
        """Build the right controls panel."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(16)
        layout.setContentsMargins(0, 0, 0, 0)

        # Add control cards
        layout.addWidget(self._build_connection_card())
        layout.addWidget(self._build_calibration_card())
        layout.addWidget(self._build_recording_card())
        layout.addWidget(self._build_settings_card())
        layout.addWidget(self._build_feedback_card())
        layout.addStretch()

        scroll.setWidget(widget)
        scroll.setFixedWidth(320)
        return scroll

    def _build_connection_card(self) -> FriendlyCard:
        """Build the connection controls card."""
        card = FriendlyCard("Connection")

        # Port selection
        port_layout = QHBoxLayout()
        port_label = QLabel("Port:")
        port_label.setFont(QFont("Comic Sans MS", 11))
        port_label.setStyleSheet(
            f"color: {COLORS['text_dark']}; background: transparent; border: none;"
        )
        port_layout.addWidget(port_label)

        self.port_combo = QComboBox()
        self._refresh_ports()
        port_layout.addWidget(self.port_combo, stretch=1)
        card.add_layout(port_layout)

        # Connection buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.connect_btn = AnimatedButton("Connect", "success")
        self.connect_btn.clicked.connect(self._toggle_connection)
        btn_layout.addWidget(self.connect_btn)

        self.refresh_btn = AnimatedButton("Refresh", "secondary")
        self.refresh_btn.clicked.connect(self._refresh_ports)
        btn_layout.addWidget(self.refresh_btn)
        card.add_layout(btn_layout)

        # Demo button
        self.demo_btn = AnimatedButton("Start Demo", "primary")
        self.demo_btn.clicked.connect(self._toggle_demo)
        card.add_widget(self.demo_btn)

        return card

    def _build_calibration_card(self) -> FriendlyCard:
        """Build the calibration controls card."""
        card = FriendlyCard("Calibration")

        # Status
        self.calib_status = QLabel("Not calibrated yet")
        self.calib_status.setFont(QFont("Comic Sans MS", 11))
        self.calib_status.setStyleSheet(
            f"color: {COLORS['warning']}; background: transparent; border: none;"
        )
        self.calib_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card.add_widget(self.calib_status)

        # Calibrate button
        self.calibrate_btn = AnimatedButton("Calibrate Spine", "primary")
        self.calibrate_btn.clicked.connect(self._start_calibration)
        card.add_widget(self.calibrate_btn)

        # Save/Load buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.save_calib_btn = AnimatedButton("Save", "secondary")
        self.save_calib_btn.clicked.connect(self._save_calibration)
        btn_layout.addWidget(self.save_calib_btn)

        self.load_calib_btn = AnimatedButton("Load", "secondary")
        self.load_calib_btn.clicked.connect(self._load_calibration)
        btn_layout.addWidget(self.load_calib_btn)
        card.add_layout(btn_layout)

        return card

    def _build_recording_card(self) -> FriendlyCard:
        """Build the recording controls card."""
        card = FriendlyCard("Recording")

        # Status with pulsing dot
        status_layout = QHBoxLayout()
        status_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.recording_dot = PulsingDot(COLORS['danger'])
        status_layout.addWidget(self.recording_dot)

        self.recording_status = QLabel("Ready to record")
        self.recording_status.setFont(QFont("Comic Sans MS", 11))
        self.recording_status.setStyleSheet(
            f"color: {COLORS['text_light']}; background: transparent; border: none;"
        )
        status_layout.addWidget(self.recording_status)
        status_layout.addStretch()
        card.add_layout(status_layout)

        # Countdown display
        self.countdown_label = QLabel("")
        self.countdown_label.setFont(QFont("Comic Sans MS", 32, QFont.Weight.Bold))
        self.countdown_label.setStyleSheet(
            f"color: {COLORS['danger']}; background: transparent; border: none;"
        )
        self.countdown_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card.add_widget(self.countdown_label)

        # Record button
        self.record_btn = AnimatedButton("Start Recording", "danger")
        self.record_btn.clicked.connect(self._on_record_clicked)
        card.add_widget(self.record_btn)

        return card

    def _build_settings_card(self) -> FriendlyCard:
        """Build the settings card."""
        card = FriendlyCard("Settings")

        self.setup_btn = AnimatedButton("Hardware Setup", "primary")
        self.setup_btn.clicked.connect(self._open_setup_mode)
        card.add_widget(self.setup_btn)

        return card

    def _build_feedback_card(self) -> FriendlyCard:
        """Build the live feedback card."""
        card = FriendlyCard("Live Feedback")

        # Pressure label
        pressure_title = QLabel("Pressure")
        pressure_title.setFont(QFont("Comic Sans MS", 11, QFont.Weight.Bold))
        pressure_title.setStyleSheet(
            f"color: {COLORS['text_dark']}; background: transparent; border: none;"
        )
        card.add_widget(pressure_title)

        # Pressure bar
        self.pressure_bar = QProgressBar()
        self.pressure_bar.setRange(0, 4095)
        self.pressure_bar.setTextVisible(False)
        self.pressure_bar.setFixedHeight(12)
        self.pressure_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 6px;
                background-color: {COLORS['border']};
            }}
            QProgressBar::chunk {{
                background-color: {COLORS['success']};
                border-radius: 6px;
            }}
        """)
        card.add_widget(self.pressure_bar)

        # Pressure description
        self.pressure_label = QLabel("No contact")
        self.pressure_label.setFont(QFont("Comic Sans MS", 10))
        self.pressure_label.setStyleSheet(
            f"color: {COLORS['text_light']}; background: transparent; border: none;"
        )
        self.pressure_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card.add_widget(self.pressure_label)

        # Palpation rate
        self.palp_rate_label = QLabel("0.0 Hz")
        self.palp_rate_label.setFont(QFont("Comic Sans MS", 28, QFont.Weight.Bold))
        self.palp_rate_label.setStyleSheet(
            f"color: {COLORS['primary']}; background: transparent; border: none;"
        )
        self.palp_rate_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card.add_widget(self.palp_rate_label)

        palp_sublabel = QLabel("Palpation Rate")
        palp_sublabel.setFont(QFont("Comic Sans MS", 10))
        palp_sublabel.setStyleSheet(
            f"color: {COLORS['text_light']}; background: transparent; border: none;"
        )
        palp_sublabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card.add_widget(palp_sublabel)

        # Target guidance
        self.target_label = QLabel("Calibrate to see guidance")
        self.target_label.setFont(QFont("Comic Sans MS", 11))
        self.target_label.setStyleSheet(
            f"color: {COLORS['text_light']}; background: transparent; border: none;"
        )
        self.target_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.target_label.setWordWrap(True)
        card.add_widget(self.target_label)

        return card

    def _build_status_bar(self) -> None:
        """Build the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Welcome! Connect to a device or try the demo mode.")

    # =========================================================================
    # Connection Handlers
    # =========================================================================

    def _refresh_ports(self) -> None:
        """Refresh the list of available serial ports."""
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(f"{port.device}", port.device)
        if not ports:
            self.port_combo.addItem("No ports found", None)

    def _toggle_connection(self) -> None:
        """Toggle serial connection on/off."""
        if self.serial_reader and self.serial_reader.running:
            self._disconnect()
        else:
            self._connect()

    def _connect(self) -> None:
        """Establish serial connection."""
        port = self.port_combo.currentData()
        if not port:
            self.status_bar.showMessage("Please select a port first!")
            return

        self.serial_reader = SerialReader(port)
        self.serial_reader.data_received.connect(self._on_data_received)
        self.serial_reader.error_occurred.connect(self._on_serial_error)
        self.serial_reader.start()

        self.connect_btn.setText("Disconnect")
        self.connect_btn.set_color_scheme("danger")
        self.status_bar.showMessage(f"Connected to {port}!")

    def _disconnect(self) -> None:
        """Close serial connection."""
        self.serial_reader.stop()
        self.serial_reader = None

        self.connect_btn.setText("Connect")
        self.connect_btn.set_color_scheme("success")
        self.status_bar.showMessage("Disconnected!")

    def _on_serial_error(self, error: str) -> None:
        """Handle serial communication errors."""
        self.status_bar.showMessage(f"Oops! Error: {error}")
        self.connect_btn.setText("Connect")
        self.connect_btn.set_color_scheme("success")

    # =========================================================================
    # Demo Mode
    # =========================================================================

    def _toggle_demo(self) -> None:
        """Toggle demo mode on/off."""
        if self.demo_timer.isActive():
            self.demo_timer.stop()
            self.demo_btn.setText("Start Demo")
            self.status_bar.showMessage("Demo stopped!")
        else:
            self._setup_demo_calibration()
            self.demo_timer.start(40)  # ~25 fps
            self.demo_btn.setText("Stop Demo")
            self.status_bar.showMessage("Demo mode running - watch the magic!")

    def _setup_demo_calibration(self) -> None:
        """Setup calibration data for demo mode."""
        spine_line = SpineLine(
            start_row=1,
            end_row=10,
            coefficients=(0.0, GRID_COLS / 2)
        )

        self.spine_detector.calibration.spine_line = spine_line
        self.spine_detector.calibration.landmarks = spine_line.get_landmarks(lateral_offset=4)

        self.landmark_overlay.set_landmarks(
            self.spine_detector.calibration.landmarks,
            spine_line
        )
        self.calib_status.setText("Calibrated (Demo)")
        self.calib_status.setStyleSheet(
            f"color: {COLORS['success']}; background: transparent; border: none;"
        )

    def _generate_demo_data(self) -> None:
        """Generate simulated pressure data for demo mode."""
        t = time.time()

        # Moving pressure point simulating palpation
        spine_col = GRID_COLS / 2 + np.sin(t * 0.5) * 2
        spine_row = 2 + ((t * 2) % 8)

        # Create pressure distribution
        data = np.zeros((GRID_ROWS, GRID_COLS), dtype=np.uint16)
        for i in range(GRID_ROWS):
            for j in range(GRID_COLS):
                dist = np.sqrt((i - spine_row)**2 + (j - spine_col)**2)
                data[i, j] = int(2500 * np.exp(-dist**2 / 4))

        # Add noise
        data = data + np.random.randint(0, 30, data.shape, dtype=np.uint16)
        self._on_data_received(data)

    # =========================================================================
    # Data Processing
    # =========================================================================

    def _on_data_received(self, data: np.ndarray) -> None:
        """Process received pressure data."""
        self.grid_data = data
        self.frame_count += 1
        current_time = time.time()

        # Update visualizations
        self._update_heatmap(data)
        self._update_waveform(data, current_time)
        self._update_stats(data, current_time)
        self._update_feedback(data, current_time)

        # Forward data to dialogs if active
        self._forward_to_dialogs(data)

        # Handle recording
        if self.is_recording:
            self._record_frame(data, current_time)

    def _update_heatmap(self, data: np.ndarray) -> None:
        """Update the heatmap visualization."""
        self.heatmap_image.setImage(data.T, autoLevels=False)

    def _update_waveform(self, data: np.ndarray, current_time: float) -> None:
        """Update the waveform display."""
        cell_value = data[self.selected_row, self.selected_col]
        self.waveform_history.append(cell_value)
        self.waveform_time.append(current_time - self.start_time)

        if len(self.waveform_history) > 1:
            y_data = list(self.waveform_history)
            if self.graph_inverted:
                y_data = [ADC_MAX - v for v in y_data]
            self.waveform_curve.setData(list(self.waveform_time), y_data)

    def _update_stats(self, data: np.ndarray, current_time: float) -> None:
        """Update the statistics displays."""
        max_pressure = int(np.max(data))
        palpation_freq = self.frequency_analyzer.update(max_pressure, current_time)

        stats = self.frequency_analyzer.get_stats()
        self.peak_stat.set_value(str(stats['peak']))
        self.trough_stat.set_value(str(stats['trough']))
        self.freq_stat.set_value(f"{stats['frequency']:.1f} Hz")

        # FPS
        elapsed = current_time - self.start_time
        if elapsed > 0:
            fps = self.frame_count / elapsed
            self.fps_stat.set_value(f"{fps:.0f}")

    def _update_feedback(self, data: np.ndarray, current_time: float) -> None:
        """Update live feedback displays."""
        max_pressure = int(np.max(data))
        pos, speed = self.movement_tracker.update(data, current_time)

        # Pressure bar and description
        self.pressure_bar.setValue(max_pressure)
        zone_name, color, message = PalpationZones.get_zone(max_pressure)
        self.pressure_label.setText(message)
        self.pressure_label.setStyleSheet(
            f"color: {color}; background: transparent; border: none;"
        )
        self.pressure_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 6px;
                background-color: {COLORS['border']};
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 6px;
            }}
        """)

        # Palpation rate
        palpation_freq = self.frequency_analyzer.update(max_pressure, current_time)
        self.palp_rate_label.setText(f"{palpation_freq:.1f} Hz")

        # Target guidance
        if pos and self.spine_detector.calibration.is_calibrated:
            self._update_target_guidance(pos, max_pressure)

    def _update_target_guidance(self, pos: tuple, pressure: int) -> None:
        """Update target guidance and drift detection."""
        feedback = self.spine_detector.get_technique_feedback(pos[0], pos[1], pressure)

        if feedback['nearest_landmark']:
            self.landmark_overlay.highlight(feedback['nearest_landmark'])

            if feedback['on_target']:
                self.target_label.setText(f"On target: {feedback['nearest_landmark'].level}")
                self.target_label.setStyleSheet(
                    f"color: {COLORS['success']}; background: transparent; border: none;"
                )
            else:
                self.target_label.setText(feedback['feedback'])
                self.target_label.setStyleSheet(
                    f"color: {COLORS['warning']}; background: transparent; border: none;"
                )

        # Drift check during recording
        if self.is_recording and self.selected_target_landmark:
            dist = feedback['distance_to_landmark']
            if dist > 5.0:
                self.drift_warning.show_warning(
                    f"Move back to {self.selected_target_landmark.level}"
                )
            else:
                self.drift_warning.hide_warning()

    def _forward_to_dialogs(self, data: np.ndarray) -> None:
        """Forward data to any active dialogs."""
        if self.calibration_dialog and self.calibration_dialog.is_recording:
            self.calibration_dialog.add_frame(data)

        if self.setup_dialog and self.setup_dialog.isVisible():
            self.setup_dialog.update_frame(data)

    # =========================================================================
    # Interaction Handlers
    # =========================================================================

    def _on_heatmap_click(self, event) -> None:
        """Handle clicks on the heatmap."""
        pos = event.scenePos()
        mouse_point = self.heatmap_widget.plotItem.vb.mapSceneToView(pos)
        col = int(mouse_point.x())
        row = int(mouse_point.y())

        if 0 <= row < GRID_ROWS and 0 <= col < GRID_COLS:
            self.selected_row = row
            self.selected_col = col
            self.selected_label.setText(f"Watching: Row {row}, Col {col}")
            self.waveform_history.clear()
            self.waveform_time.clear()

            if self.spine_detector.calibration.is_calibrated:
                lm, _ = self.spine_detector.find_nearest_landmark(row, col)
                self.selected_target_landmark = lm

    def _toggle_graph_flip(self) -> None:
        """Toggle between normal and inverted graph view."""
        self.graph_inverted = not self.graph_inverted
        if self.graph_inverted:
            self.flip_btn.setText("Normal View")
            self.waveform_plot.setLabel('left', 'Displacement')
        else:
            self.flip_btn.setText("Flip View")
            self.waveform_plot.setLabel('left', 'Value')

    # =========================================================================
    # Calibration
    # =========================================================================

    def _start_calibration(self) -> None:
        """Open the calibration dialog."""
        self.calibration_dialog = CalibrationDialog(self)
        self.calibration_dialog.calibration_complete.connect(self._on_calibration_complete)
        self.calibration_dialog.show()

    def _on_calibration_complete(self, detector: SpineDetector) -> None:
        """Handle calibration completion."""
        self.spine_detector = detector

        if detector.calibration.is_calibrated:
            self.landmark_overlay.set_landmarks(
                detector.calibration.landmarks,
                detector.calibration.spine_line
            )
            self.calib_status.setText("Calibrated!")
            self.calib_status.setStyleSheet(
                f"color: {COLORS['success']}; background: transparent; border: none;"
            )
            self.status_bar.showMessage(
                "Calibration complete! L1-L5 landmarks visible on the heatmap."
            )

        self.calibration_dialog = None

    def _save_calibration(self) -> None:
        """Save calibration to file."""
        if not self.spine_detector.calibration.is_calibrated:
            self.status_bar.showMessage("Nothing to save - calibrate first!")
            return

        filepath, _ = QFileDialog.getSaveFileName(self, "Save Calibration", "", "JSON Files (*.json)")
        if filepath:
            self.spine_detector.save_calibration(filepath)
            self.status_bar.showMessage(f"Saved to {filepath}!")

    def _load_calibration(self) -> None:
        """Load calibration from file."""
        filepath, _ = QFileDialog.getOpenFileName(self, "Load Calibration", "", "JSON Files (*.json)")
        if filepath:
            if self.spine_detector.load_calibration(filepath):
                self.landmark_overlay.set_landmarks(
                    self.spine_detector.calibration.landmarks,
                    self.spine_detector.calibration.spine_line
                )
                self.calib_status.setText("Calibrated!")
                self.calib_status.setStyleSheet(
                    f"color: {COLORS['success']}; background: transparent; border: none;"
                )
                self.status_bar.showMessage(f"Loaded from {filepath}!")
            else:
                self.status_bar.showMessage("Couldn't load that file!")

    # =========================================================================
    # Hardware Setup
    # =========================================================================

    def _open_setup_mode(self) -> None:
        """Open the hardware setup dialog."""
        self.setup_dialog = SetupModeDialog(
            grid_rows=GRID_ROWS,
            grid_cols=GRID_COLS,
            initial_config=self.hardware_config,
            parent=self
        )
        self.setup_dialog.config_updated.connect(self._on_config_updated)
        self.setup_dialog.show()
        self.status_bar.showMessage("Hardware setup mode - configure your pins!")

    def _on_config_updated(self, config: HardwareConfig) -> None:
        """Handle hardware configuration updates."""
        self.hardware_config = config
        save_default_config(config)
        self.status_bar.showMessage("Hardware configuration saved!")

    # =========================================================================
    # Recording
    # =========================================================================

    def _on_record_clicked(self) -> None:
        """Handle record button clicks."""
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_countdown()

    def _start_countdown(self) -> None:
        """Start the pre-recording countdown."""
        self.countdown_value = COUNTDOWN_SECONDS
        self.countdown_label.setText(str(self.countdown_value))
        self.record_btn.setEnabled(False)
        self.countdown_timer.start(1000)

    def _countdown_tick(self) -> None:
        """Handle countdown timer tick."""
        self.countdown_value -= 1
        if self.countdown_value > 0:
            self.countdown_label.setText(str(self.countdown_value))
        else:
            self.countdown_timer.stop()
            self.countdown_label.setText("")
            self._start_recording()

    def _start_recording(self) -> None:
        """Start recording data."""
        self.is_recording = True
        self.recording_data_raw = []
        self.recording_data_annotated = []
        self.recording_start_time = time.time()

        # Update UI
        self.record_btn.setText("Stop Recording")
        self.record_btn.setEnabled(True)
        self.recording_status.setText("Recording...")
        self.recording_status.setStyleSheet(
            f"color: {COLORS['danger']}; background: transparent; border: none;"
        )
        self.recording_dot.start()

        # Start screen recording
        if RECORDING_AVAILABLE:
            self._start_screen_recording()

        self.status_bar.showMessage("Recording started!")

    def _start_screen_recording(self) -> None:
        """Start screen capture recording."""
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

    def _stop_recording(self) -> None:
        """Stop recording and export data."""
        self.is_recording = False
        self.drift_warning.hide_warning()

        # Update UI
        self.record_btn.setText("Start Recording")
        self.recording_status.setText("Ready to record")
        self.recording_status.setStyleSheet(
            f"color: {COLORS['text_light']}; background: transparent; border: none;"
        )
        self.recording_dot.stop()

        # Stop screen recorder
        if self.screen_recorder:
            self.screen_recorder.stop()
            self.screen_recorder = None

        # Export data
        self._export_recording()

    def _record_frame(self, data: np.ndarray, timestamp: float) -> None:
        """Record a single frame of data."""
        self.recording_data_raw.append(data.copy())

        pos, _ = self.movement_tracker.update(data, timestamp)
        max_pressure = int(np.max(data))

        annotation = {
            'timestamp': timestamp - self.recording_start_time,
            'max_pressure': max_pressure,
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

    def _export_recording(self) -> None:
        """Export recorded data to files."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Raw CSV
        raw_csv_path = f"recording_raw_{timestamp}.csv"
        self._export_raw_csv(raw_csv_path)

        # Annotated CSV
        annotated_csv_path = f"recording_annotated_{timestamp}.csv"
        self._export_annotated_csv(annotated_csv_path)

        # Graph PDF
        if EXPORT_AVAILABLE:
            graph_path = f"recording_graph_{timestamp}.pdf"
            self._export_graph(graph_path)

        self.status_bar.showMessage(f"Recording saved! Check {raw_csv_path}")

    def _export_raw_csv(self, filepath: str) -> None:
        """Export raw grid data to CSV."""
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            header = ['frame'] + [f'r{r}c{c}' for r in range(GRID_ROWS) for c in range(GRID_COLS)]
            writer.writerow(header)
            for i, frame in enumerate(self.recording_data_raw):
                row = [i] + frame.flatten().tolist()
                writer.writerow(row)

    def _export_annotated_csv(self, filepath: str) -> None:
        """Export annotated data to CSV."""
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'max_pressure', 'pos_row', 'pos_col', 'nearest_landmark', 'distance'])
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

    def _export_graph(self, filepath: str) -> None:
        """Export waveform graph to PDF."""
        if not self.waveform_history:
            return

        fig, ax = plt.subplots(figsize=(10, 4))
        y_data = list(self.waveform_history)
        x_data = list(self.waveform_time)

        ax.plot(x_data, y_data, color=COLORS['primary'], linewidth=2)
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('ADC Value')
        ax.set_title('Force vs Time')
        ax.set_ylim(0, 4095)
        ax.grid(True, alpha=0.3)

        if y_data:
            ax.axhline(y=max(y_data), color=COLORS['danger'], linestyle='--',
                      alpha=0.5, label=f'Peak: {max(y_data)}')
            ax.axhline(y=min(y_data), color=COLORS['info'], linestyle='--',
                      alpha=0.5, label=f'Trough: {min(y_data)}')
            ax.legend()

        fig.tight_layout()
        fig.savefig(filepath, format='pdf', dpi=150)
        plt.close(fig)

    # =========================================================================
    # Cleanup
    # =========================================================================

    def closeEvent(self, event) -> None:
        """Handle window close event."""
        if self.serial_reader:
            self.serial_reader.stop()
        if self.screen_recorder:
            self.screen_recorder.stop()
        self.demo_timer.stop()
        event.accept()
