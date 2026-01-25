"""
================================================================================
Hardware Setup Mode Dialog
================================================================================

Interactive dialog for configuring GPIO and ADC pin mappings by physically
testing the pressure sensing grid.

Features:
- Professional Apple-inspired UI design
- Visual grid representation showing detected presses
- Guided row-by-row GPIO configuration sequence with animation
- Auto-detect when force applied to each row
- ADC channel detection and mapping
- Real-time validation
- Configuration export

Author: Capstone Project
Date: 2026-01-24
================================================================================
"""

import numpy as np
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QLineEdit, QTextEdit,
    QGroupBox, QSpinBox, QProgressBar, QMessageBox, QFileDialog,
    QHeaderView, QComboBox, QFrame, QStackedWidget, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QFont, QColor, QPainter, QPen, QBrush, QLinearGradient
import pyqtgraph as pg

from hardware_config import HardwareConfig, save_default_config


# Professional Apple-Inspired Color Palette
COLORS = {
    'bg_primary': '#000000',
    'bg_secondary': '#1c1c1e',
    'bg_tertiary': '#2c2c2e',
    'bg_quaternary': '#3a3a3c',
    'text_primary': '#ffffff',
    'text_secondary': '#8e8e93',
    'text_tertiary': '#636366',
    'accent_blue': '#0a84ff',
    'accent_green': '#30d158',
    'accent_red': '#ff453a',
    'accent_orange': '#ff9f0a',
    'accent_yellow': '#ffd60a',
    'accent_purple': '#bf5af2',
    'accent_teal': '#64d2ff',
    'separator': '#38383a',
}


class GridPreviewWidget(QWidget):
    """Visual preview of the grid dimensions."""

    def __init__(self, rows=12, cols=20, parent=None):
        super().__init__(parent)
        self.rows = rows
        self.cols = cols
        self.setMinimumSize(120, 80)

    def set_dimensions(self, rows: int, cols: int):
        """Update grid dimensions."""
        self.rows = rows
        self.cols = cols
        self.update()

    def paintEvent(self, event):
        """Draw the grid preview."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # Add padding
        padding = 8
        available_width = width - 2 * padding
        available_height = height - 2 * padding

        cell_width = available_width / self.cols
        cell_height = available_height / self.rows

        # Draw grid cells
        for r in range(self.rows):
            for c in range(self.cols):
                x = padding + c * cell_width
                y = padding + r * cell_height

                # Alternate colors for visibility
                if (r + c) % 2 == 0:
                    color = QColor(COLORS['bg_quaternary'])
                else:
                    color = QColor(COLORS['separator'])

                painter.fillRect(int(x), int(y), max(1, int(cell_width)), max(1, int(cell_height)), color)

        # Draw border
        painter.setPen(QPen(QColor(COLORS['accent_blue']), 2))
        painter.drawRect(padding, padding, int(available_width), int(available_height))

        # Draw dimensions text
        painter.setPen(QPen(QColor(COLORS['text_secondary'])))
        font = QFont("-apple-system", 9)
        painter.setFont(font)
        dim_text = f"{self.rows}×{self.cols}"
        painter.drawText(padding, height - 2, dim_text)


class AnimatedRowIndicator(QWidget):
    """Visual indicator showing which row to press with pulsing animation."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_row = 0
        self.total_rows = 12
        self.pulse_phase = 0
        self.is_active = False

        # Pulse animation timer
        self.pulse_timer = QTimer()
        self.pulse_timer.timeout.connect(self._update_pulse)
        self.pulse_timer.setInterval(50)

    def set_row(self, row: int, total_rows: int = 12):
        self.current_row = row
        self.total_rows = total_rows
        self.update()

    def start_animation(self):
        self.is_active = True
        self.pulse_timer.start()

    def stop_animation(self):
        self.is_active = False
        self.pulse_timer.stop()
        self.update()

    def _update_pulse(self):
        self.pulse_phase = (self.pulse_phase + 1) % 60
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()
        row_height = height / self.total_rows

        # Draw all rows
        for i in range(self.total_rows):
            y = i * row_height

            if i == self.current_row and self.is_active:
                # Animated highlight for current row
                pulse_intensity = 0.5 + 0.5 * np.sin(self.pulse_phase * 0.2)
                alpha = int(100 + 100 * pulse_intensity)

                gradient = QLinearGradient(0, y, width, y)
                color = QColor(COLORS['accent_blue'])
                color.setAlpha(alpha)
                gradient.setColorAt(0, color)
                gradient.setColorAt(0.5, QColor(COLORS['accent_blue']))
                gradient.setColorAt(1, color)

                painter.fillRect(QRect(0, int(y), width, int(row_height)), gradient)

                # Arrow indicator
                painter.setPen(QPen(QColor(COLORS['text_primary']), 2))
                arrow_x = width - 25
                arrow_y = y + row_height / 2
                painter.drawLine(int(arrow_x - 10), int(arrow_y), int(arrow_x), int(arrow_y))
                painter.drawLine(int(arrow_x - 5), int(arrow_y - 5), int(arrow_x), int(arrow_y))
                painter.drawLine(int(arrow_x - 5), int(arrow_y + 5), int(arrow_x), int(arrow_y))
            else:
                # Normal row background
                color = QColor(COLORS['bg_tertiary']) if i % 2 == 0 else QColor(COLORS['bg_secondary'])
                painter.fillRect(QRect(0, int(y), width, int(row_height)), color)

            # Row label
            painter.setPen(QPen(QColor(COLORS['text_secondary'])))
            font = QFont("-apple-system", 10)
            painter.setFont(font)
            painter.drawText(8, int(y + row_height / 2 + 4), f"Row {i}")


class SetupModeDialog(QDialog):
    """
    Dialog for hardware configuration setup mode.

    Features:
    - Guided calibration sequence with visual indicators
    - Auto-detection of active rows
    - Professional Apple-inspired UI
    """

    config_updated = pyqtSignal(HardwareConfig)

    def __init__(self, grid_rows: int = 12, grid_cols: int = 20,
                 initial_config: HardwareConfig = None, parent=None):
        super().__init__(parent)
        self.grid_rows = grid_rows
        self.grid_cols = grid_cols

        if initial_config:
            self.config = initial_config
        else:
            self.config = HardwareConfig(grid_rows=grid_rows, grid_cols=grid_cols)

        # State tracking
        self.current_frame = np.zeros((grid_rows, grid_cols), dtype=np.uint16)
        self.detected_row = None
        self.is_monitoring = False

        # Calibration sequence state
        self.sequence_active = False
        self.sequence_row = 0
        self.sequence_gpio_prefix = "GPIO_"

        # Detection parameters
        self.detection_threshold = 500
        self.detection_hold_frames = 5
        self.detection_counter = 0
        self.last_detected_row = None

        self.setWindowTitle("Hardware Setup")
        self.setMinimumSize(1100, 800)
        self.setModal(True)

        self._build_ui()
        self._apply_style()
        self._update_table()

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
            QPushButton:disabled {{
                background-color: {COLORS['bg_tertiary']};
                color: {COLORS['text_tertiary']};
            }}
            QLineEdit {{
                background-color: {COLORS['bg_tertiary']};
                border: none;
                border-radius: 8px;
                padding: 10px 12px;
                color: {COLORS['text_primary']};
                font-size: 13px;
            }}
            QLineEdit:focus {{
                background-color: {COLORS['bg_quaternary']};
            }}
            QTableWidget {{
                background-color: {COLORS['bg_secondary']};
                alternate-background-color: {COLORS['bg_tertiary']};
                gridline-color: {COLORS['separator']};
                border: none;
                border-radius: 8px;
            }}
            QTableWidget::item {{
                padding: 8px;
            }}
            QHeaderView::section {{
                background-color: {COLORS['bg_tertiary']};
                color: {COLORS['text_secondary']};
                border: none;
                padding: 8px;
                font-weight: 500;
                font-size: 11px;
                text-transform: uppercase;
            }}
            QTextEdit {{
                background-color: {COLORS['bg_tertiary']};
                border: none;
                border-radius: 8px;
                color: {COLORS['text_primary']};
                padding: 12px;
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
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Header
        header_layout = QHBoxLayout()

        title = QLabel("Hardware Configuration")
        title.setFont(QFont("-apple-system", 22, QFont.Weight.DemiBold))
        header_layout.addWidget(title)

        header_layout.addStretch()

        layout.addLayout(header_layout)

        # Description
        desc = QLabel(
            "Configure GPIO pin mappings by pressing on each row of the physical grid. "
            "Use the guided sequence or manually assign pins."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 14px; margin-bottom: 8px;")
        layout.addWidget(desc)

        # Grid Size Configuration
        size_group = QGroupBox("Grid Dimensions")
        size_layout = QHBoxLayout(size_group)
        size_layout.setSpacing(16)

        # Grid dimensions display
        grid_info = QVBoxLayout()
        grid_label = QLabel("Configure the physical grid size")
        grid_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        grid_info.addWidget(grid_label)

        dims_layout = QHBoxLayout()
        dims_layout.setSpacing(12)

        # Rows spinbox
        rows_label = QLabel("Rows:")
        rows_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 14px; font-weight: 500;")
        dims_layout.addWidget(rows_label)

        self.rows_spinbox = QSpinBox()
        self.rows_spinbox.setRange(1, 50)
        self.rows_spinbox.setValue(self.grid_rows)
        self.rows_spinbox.setFixedWidth(80)
        self.rows_spinbox.valueChanged.connect(self._on_grid_size_changed)
        self.rows_spinbox.setStyleSheet(f"""
            QSpinBox {{
                background-color: {COLORS['bg_tertiary']};
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
                color: {COLORS['text_primary']};
                font-size: 16px;
                font-weight: bold;
            }}
        """)
        dims_layout.addWidget(self.rows_spinbox)

        # Multiplication symbol
        times_label = QLabel("×")
        times_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 18px;")
        dims_layout.addWidget(times_label)

        # Columns spinbox
        cols_label = QLabel("Columns:")
        cols_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 14px; font-weight: 500;")
        dims_layout.addWidget(cols_label)

        self.cols_spinbox = QSpinBox()
        self.cols_spinbox.setRange(1, 50)
        self.cols_spinbox.setValue(self.grid_cols)
        self.cols_spinbox.setFixedWidth(80)
        self.cols_spinbox.valueChanged.connect(self._on_grid_size_changed)
        self.cols_spinbox.setStyleSheet(f"""
            QSpinBox {{
                background-color: {COLORS['bg_tertiary']};
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
                color: {COLORS['text_primary']};
                font-size: 16px;
                font-weight: bold;
            }}
        """)
        dims_layout.addWidget(self.cols_spinbox)

        # Total sensors display
        dims_layout.addStretch()
        self.total_sensors_label = QLabel(f"Total: {self.grid_rows * self.grid_cols} sensors")
        self.total_sensors_label.setStyleSheet(f"color: {COLORS['accent_blue']}; font-size: 14px; font-weight: 600;")
        dims_layout.addWidget(self.total_sensors_label)

        grid_info.addLayout(dims_layout)
        size_layout.addLayout(grid_info)

        # Visual grid preview
        preview_container = QVBoxLayout()
        preview_label = QLabel("Grid Preview")
        preview_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; text-transform: uppercase;")
        preview_container.addWidget(preview_label)

        self.grid_preview = GridPreviewWidget(self.grid_rows, self.grid_cols)
        self.grid_preview.setStyleSheet(f"background-color: {COLORS['bg_tertiary']}; border-radius: 8px;")
        preview_container.addWidget(self.grid_preview)
        size_layout.addLayout(preview_container)

        layout.addWidget(size_group)

        # Main content
        main_layout = QHBoxLayout()
        main_layout.setSpacing(16)

        # Left: Grid visualization
        left_panel = QVBoxLayout()
        left_panel.setSpacing(12)

        grid_group = QGroupBox("Grid Activity")
        grid_layout = QHBoxLayout(grid_group)
        grid_layout.setSpacing(12)

        # Animated row indicator
        self.row_indicator = AnimatedRowIndicator()
        self.row_indicator.set_row(0, self.grid_rows)
        self.row_indicator.setFixedWidth(100)
        grid_layout.addWidget(self.row_indicator)

        # Heatmap
        self.grid_widget = pg.PlotWidget()
        self.grid_widget.setAspectLocked(True)
        self.grid_widget.hideAxis('left')
        self.grid_widget.hideAxis('bottom')
        self.grid_widget.setBackground(COLORS['bg_tertiary'])

        self.grid_image = pg.ImageItem()
        self.grid_widget.addItem(self.grid_image)

        colors = [(0, 0, 40), (0, 180, 220), (60, 220, 60), (255, 140, 0), (255, 40, 40)]
        positions = np.linspace(0, 1, len(colors))
        colormap = pg.ColorMap(positions, colors)
        self.grid_image.setLookupTable(colormap.getLookupTable())
        self.grid_image.setLevels([0, 4095])
        self.grid_image.setImage(self.current_frame.T)

        grid_layout.addWidget(self.grid_widget, stretch=1)

        left_panel.addWidget(grid_group)

        # Detection status
        status_group = QGroupBox("Detection Status")
        status_layout = QVBoxLayout(status_group)

        self.detection_label = QLabel("Waiting for input...")
        self.detection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detection_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 14px;")
        status_layout.addWidget(self.detection_label)

        self.detection_progress = QProgressBar()
        self.detection_progress.setRange(0, self.detection_hold_frames)
        self.detection_progress.setValue(0)
        self.detection_progress.setTextVisible(False)
        status_layout.addWidget(self.detection_progress)

        left_panel.addWidget(status_group)

        main_layout.addLayout(left_panel, stretch=2)

        # Right: Configuration
        right_panel = QVBoxLayout()
        right_panel.setSpacing(12)

        # Calibration sequence controls
        sequence_group = QGroupBox("Guided Calibration")
        sequence_layout = QVBoxLayout(sequence_group)

        sequence_desc = QLabel(
            "Start the guided sequence to automatically configure each row. "
            "Press on the highlighted row when prompted."
        )
        sequence_desc.setWordWrap(True)
        sequence_desc.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        sequence_layout.addWidget(sequence_desc)

        # GPIO prefix input
        prefix_layout = QHBoxLayout()
        prefix_label = QLabel("GPIO Prefix:")
        prefix_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 12px;")
        prefix_layout.addWidget(prefix_label)

        self.prefix_input = QLineEdit("GPIOA_PIN")
        self.prefix_input.setFixedWidth(150)
        prefix_layout.addWidget(self.prefix_input)

        prefix_layout.addStretch()
        sequence_layout.addLayout(prefix_layout)

        # Sequence buttons
        btn_layout = QHBoxLayout()

        self.start_sequence_btn = QPushButton("Start Sequence")
        self.start_sequence_btn.clicked.connect(self._start_sequence)
        self.start_sequence_btn.setStyleSheet(f"background-color: {COLORS['accent_green']}; color: {COLORS['bg_primary']};")
        btn_layout.addWidget(self.start_sequence_btn)

        self.stop_sequence_btn = QPushButton("Stop")
        self.stop_sequence_btn.clicked.connect(self._stop_sequence)
        self.stop_sequence_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_sequence_btn)

        sequence_layout.addLayout(btn_layout)

        # Sequence progress
        self.sequence_label = QLabel("")
        self.sequence_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sequence_label.setStyleSheet(f"color: {COLORS['accent_blue']}; font-weight: 600;")
        sequence_layout.addWidget(self.sequence_label)

        right_panel.addWidget(sequence_group)

        # Configuration table
        table_group = QGroupBox("Pin Mapping")
        table_layout = QVBoxLayout(table_group)

        self.config_table = QTableWidget(self.grid_rows, 3)
        self.config_table.setHorizontalHeaderLabels(["Row", "GPIO Pin", "Status"])
        self.config_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.config_table.verticalHeader().setVisible(False)
        self.config_table.setAlternatingRowColors(True)
        table_layout.addWidget(self.config_table)

        right_panel.addWidget(table_group)

        # Manual configuration
        manual_group = QGroupBox("Manual Configuration")
        manual_layout = QVBoxLayout(manual_group)

        row_layout = QHBoxLayout()
        row_layout.addWidget(QLabel("Row:"))
        self.row_spinbox = QSpinBox()
        self.row_spinbox.setRange(0, self.grid_rows - 1)
        self.row_spinbox.setFixedWidth(60)
        row_layout.addWidget(self.row_spinbox)

        row_layout.addWidget(QLabel("GPIO:"))
        self.gpio_input = QLineEdit()
        self.gpio_input.setPlaceholderText("e.g., GPIOA_PIN0")
        row_layout.addWidget(self.gpio_input, stretch=1)

        self.assign_btn = QPushButton("Assign")
        self.assign_btn.clicked.connect(self._assign_gpio)
        row_layout.addWidget(self.assign_btn)

        manual_layout.addLayout(row_layout)
        right_panel.addWidget(manual_group)

        # Validation
        validation_group = QGroupBox("Validation")
        validation_layout = QVBoxLayout(validation_group)

        self.validation_text = QTextEdit()
        self.validation_text.setReadOnly(True)
        self.validation_text.setMaximumHeight(80)
        validation_layout.addWidget(self.validation_text)

        self.validate_btn = QPushButton("Validate Configuration")
        self.validate_btn.clicked.connect(self._validate_config)
        validation_layout.addWidget(self.validate_btn)

        right_panel.addWidget(validation_group)

        main_layout.addLayout(right_panel, stretch=1)
        layout.addLayout(main_layout, stretch=1)

        # Bottom buttons
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(12)

        self.save_btn = QPushButton("Save Configuration")
        self.save_btn.clicked.connect(self._save_config)
        self.save_btn.setStyleSheet(f"background-color: {COLORS['accent_blue']}; color: {COLORS['text_primary']};")
        bottom_layout.addWidget(self.save_btn)

        self.export_btn = QPushButton("Export C Header")
        self.export_btn.clicked.connect(self._export_header)
        bottom_layout.addWidget(self.export_btn)

        bottom_layout.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(self.close_btn)

        layout.addLayout(bottom_layout)

    def _update_table(self):
        """Update the configuration table with current settings."""
        for row in range(self.grid_rows):
            # Row number
            row_item = QTableWidgetItem(str(row))
            row_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.config_table.setItem(row, 0, row_item)

            # GPIO pin
            gpio = self.config.get_row_gpio(row) or "UNDEFINED"
            gpio_item = QTableWidgetItem(gpio)
            if "UNDEFINED" in gpio:
                gpio_item.setForeground(QColor(COLORS['accent_red']))
            else:
                gpio_item.setForeground(QColor(COLORS['accent_green']))
            self.config_table.setItem(row, 1, gpio_item)

            # Status
            is_configured = "UNDEFINED" not in gpio
            status = "Configured" if is_configured else "Not Set"
            status_item = QTableWidgetItem(status)
            status_item.setForeground(QColor(COLORS['accent_green'] if is_configured else COLORS['accent_yellow']))
            self.config_table.setItem(row, 2, status_item)

    def _start_sequence(self):
        """Start the guided calibration sequence."""
        self.sequence_active = True
        self.sequence_row = 0
        self.sequence_gpio_prefix = self.prefix_input.text().strip() or "GPIO_"

        self.start_sequence_btn.setEnabled(False)
        self.stop_sequence_btn.setEnabled(True)
        self.is_monitoring = True

        self.row_indicator.set_row(0, self.grid_rows)
        self.row_indicator.start_animation()

        self._update_sequence_ui()

    def _stop_sequence(self):
        """Stop the calibration sequence."""
        self.sequence_active = False
        self.is_monitoring = False

        self.start_sequence_btn.setEnabled(True)
        self.stop_sequence_btn.setEnabled(False)
        self.sequence_label.setText("")

        self.row_indicator.stop_animation()

    def _update_sequence_ui(self):
        """Update UI for current sequence step."""
        if not self.sequence_active:
            return

        if self.sequence_row >= self.grid_rows:
            # Sequence complete
            self._stop_sequence()
            self.sequence_label.setText("Calibration Complete")
            self.sequence_label.setStyleSheet(f"color: {COLORS['accent_green']}; font-weight: 600;")
            QMessageBox.information(self, "Complete", "All rows have been configured.")
            return

        self.row_indicator.set_row(self.sequence_row, self.grid_rows)
        self.sequence_label.setText(f"Press on Row {self.sequence_row}")
        self.sequence_label.setStyleSheet(f"color: {COLORS['accent_blue']}; font-weight: 600;")

    def _advance_sequence(self, detected_row: int):
        """Advance to next row in sequence after successful detection."""
        if not self.sequence_active:
            return

        if detected_row == self.sequence_row:
            # Auto-assign GPIO
            gpio_pin = f"{self.sequence_gpio_prefix}{self.sequence_row}"
            self.config.set_row_gpio(self.sequence_row, gpio_pin)
            self._update_table()

            # Flash success
            self.detection_label.setText(f"Row {self.sequence_row} configured as {gpio_pin}")
            self.detection_label.setStyleSheet(f"color: {COLORS['accent_green']}; font-size: 14px; font-weight: 600;")

            # Move to next row
            self.sequence_row += 1
            QTimer.singleShot(500, self._update_sequence_ui)

    def update_frame(self, frame: np.ndarray):
        """Update with new frame from serial data."""
        self.current_frame = frame
        self.grid_image.setImage(frame.T, autoLevels=False)

        if self.is_monitoring or self.sequence_active:
            self._detect_active_row(frame)

    def _detect_active_row(self, frame: np.ndarray):
        """Detect which row has the most activity."""
        row_sums = np.sum(frame, axis=1)
        max_row = int(np.argmax(row_sums))
        max_value = row_sums[max_row]

        if max_value > self.detection_threshold:
            if max_row == self.last_detected_row:
                self.detection_counter += 1
            else:
                self.detection_counter = 1
                self.last_detected_row = max_row

            self.detection_progress.setValue(min(self.detection_counter, self.detection_hold_frames))

            if self.detection_counter >= self.detection_hold_frames:
                # Confirmed detection
                self.detected_row = max_row
                self.detection_label.setText(f"Detected: Row {max_row}")
                self.detection_label.setStyleSheet(f"color: {COLORS['accent_green']}; font-size: 14px; font-weight: 600;")

                # Set spinbox to detected row
                self.row_spinbox.setValue(max_row)

                # If in sequence mode, advance
                if self.sequence_active:
                    self._advance_sequence(max_row)

                # Reset counter for next detection
                self.detection_counter = 0
        else:
            self.detection_counter = 0
            self.last_detected_row = None
            self.detection_progress.setValue(0)

            if not self.sequence_active:
                self.detection_label.setText("Waiting for input...")
                self.detection_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 14px;")

    def _assign_gpio(self):
        """Assign GPIO pin to selected row."""
        row = self.row_spinbox.value()
        gpio_pin = self.gpio_input.text().strip()

        if not gpio_pin:
            QMessageBox.warning(self, "Invalid Input", "Please enter a GPIO pin name.")
            return

        try:
            self.config.set_row_gpio(row, gpio_pin)
            self._update_table()
            self.gpio_input.clear()

            # Highlight the configured row briefly
            self.detection_label.setText(f"Row {row} set to {gpio_pin}")
            self.detection_label.setStyleSheet(f"color: {COLORS['accent_green']}; font-size: 14px; font-weight: 600;")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to assign GPIO: {e}")

    def _validate_config(self):
        """Validate the current configuration."""
        issues = self.config.validate()

        if not issues:
            self.validation_text.setHtml(
                f"<span style='color: {COLORS['accent_green']}; font-weight: bold;'>"
                "Configuration is valid</span>"
            )
        else:
            issue_text = "<br>".join([f"- {issue}" for issue in issues])
            self.validation_text.setHtml(
                f"<span style='color: {COLORS['accent_red']};'>"
                f"<b>Issues found:</b><br>{issue_text}</span>"
            )

    def _save_config(self):
        """Save configuration to file."""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Hardware Configuration", "hardware_config.json", "JSON Files (*.json)"
        )

        if filepath:
            try:
                self.config.save(filepath)
                save_default_config(self.config)
                QMessageBox.information(self, "Saved", f"Configuration saved to:\n{filepath}")
                self.config_updated.emit(self.config)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")

    def _export_header(self):
        """Export configuration as C header file."""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export C Header", "hardware_config.h", "Header Files (*.h)"
        )

        if filepath:
            try:
                self.config.export_c_header(filepath)
                QMessageBox.information(self, "Exported", f"C header exported to:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export:\n{e}")

    def _on_grid_size_changed(self):
        """Handle grid size change."""
        new_rows = self.rows_spinbox.value()
        new_cols = self.cols_spinbox.value()

        # Update config
        self.grid_rows = new_rows
        self.grid_cols = new_cols
        self.config.grid_rows = new_rows
        self.config.grid_cols = new_cols

        # Update total sensors label
        total = new_rows * new_cols
        self.total_sensors_label.setText(f"Total: {total} sensors")

        # Update row indicator
        self.row_indicator.total_rows = new_rows
        self.row_indicator.set_row(self.row_indicator.current_row, new_rows)

        # Rebuild table with new row count
        self.config_table.setRowCount(new_rows)
        self._update_table()

        # Update grid preview
        self.grid_preview.set_dimensions(new_rows, new_cols)
