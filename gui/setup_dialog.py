"""
================================================================================
Hardware Setup Mode Dialog
================================================================================

Interactive dialog for configuring GPIO and ADC pin mappings by physically
testing the pressure sensing grid.

Features:
- Visual grid representation showing detected presses
- Row-by-row GPIO configuration workflow
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
    QHeaderView, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor
import pyqtgraph as pg

from hardware_config import HardwareConfig, save_default_config


# UI Colors (matching main GUI)
DARK_BG = "#1e1e2e"
DARK_SURFACE = "#313244"
DARK_TEXT = "#cdd6f4"
ACCENT_BLUE = "#89b4fa"
ACCENT_GREEN = "#a6e3a1"
ACCENT_RED = "#f38ba8"
ACCENT_YELLOW = "#f9e2af"
ACCENT_ORANGE = "#fab387"


class SetupModeDialog(QDialog):
    """
    Dialog for hardware configuration setup mode.

    Workflow:
    1. User presses on physical grid row by row
    2. System detects which row has activity
    3. User assigns GPIO pin name to detected row
    4. Repeat for all rows
    5. Configure ADC channels
    6. Save configuration
    """

    config_updated = pyqtSignal(HardwareConfig)

    def __init__(self, grid_rows: int = 12, grid_cols: int = 20,
                 initial_config: HardwareConfig = None, parent=None):
        super().__init__(parent)
        self.grid_rows = grid_rows
        self.grid_cols = grid_cols

        # Load or create configuration
        if initial_config:
            self.config = initial_config
        else:
            self.config = HardwareConfig(grid_rows=grid_rows, grid_cols=grid_cols)

        # State tracking
        self.current_frame = np.zeros((grid_rows, grid_cols), dtype=np.uint16)
        self.row_activity_history = {i: [] for i in range(grid_rows)}
        self.detected_row = None
        self.is_monitoring = False
        self.current_setup_row = 0

        self.setWindowTitle("Hardware Setup Mode")
        self.setMinimumSize(1000, 800)
        self.setModal(True)

        self._build_ui()
        self._update_table()

    def _build_ui(self):
        """Build the user interface."""
        layout = QVBoxLayout(self)

        # Title and instructions
        title = QLabel("⚙ Hardware Configuration Setup")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {ACCENT_BLUE}; padding: 10px;")
        layout.addWidget(title)

        instructions = QLabel(
            "Configure GPIO pin mappings by pressing on each row of the physical grid.\n"
            "The system will detect which row is active and allow you to assign the GPIO pin."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet(f"color: {DARK_TEXT}; padding: 5px; font-size: 11px;")
        layout.addWidget(instructions)

        # Main horizontal layout
        main_h_layout = QHBoxLayout()

        # Left: Visual grid
        left_panel = QVBoxLayout()

        grid_group = QGroupBox("Grid Activity Monitor")
        grid_layout = QVBoxLayout(grid_group)

        self.grid_widget = pg.PlotWidget()
        self.grid_widget.setAspectLocked(True)
        self.grid_widget.hideAxis('left')
        self.grid_widget.hideAxis('bottom')
        self.grid_widget.setMinimumHeight(400)

        self.grid_image = pg.ImageItem()
        self.grid_widget.addItem(self.grid_image)

        # Colormap
        colors = [(0, 0, 128), (0, 255, 255), (0, 255, 0), (255, 255, 0), (255, 0, 0)]
        positions = np.linspace(0, 1, len(colors))
        colormap = pg.ColorMap(positions, colors)
        self.grid_image.setLookupTable(colormap.getLookupTable())
        self.grid_image.setLevels([0, 4095])
        self.grid_image.setImage(self.current_frame.T)

        grid_layout.addWidget(self.grid_widget)

        # Detection status
        self.detection_label = QLabel("Waiting for press...")
        self.detection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detection_label.setStyleSheet(f"color: {ACCENT_YELLOW}; font-weight: bold; font-size: 12px;")
        grid_layout.addWidget(self.detection_label)

        left_panel.addWidget(grid_group)
        main_h_layout.addLayout(left_panel, stretch=2)

        # Right: Configuration table and controls
        right_panel = QVBoxLayout()

        # Row configuration table
        table_group = QGroupBox("Row GPIO Configuration")
        table_layout = QVBoxLayout(table_group)

        self.config_table = QTableWidget(self.grid_rows, 3)
        self.config_table.setHorizontalHeaderLabels(["Row", "GPIO Pin", "Status"])
        self.config_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.config_table.setMaximumHeight(300)
        table_layout.addWidget(self.config_table)

        right_panel.addWidget(table_group)

        # Current row setup
        setup_group = QGroupBox("Configure Current Row")
        setup_layout = QVBoxLayout(setup_group)

        row_select_layout = QHBoxLayout()
        row_select_layout.addWidget(QLabel("Row to Configure:"))
        self.row_spinbox = QSpinBox()
        self.row_spinbox.setRange(0, self.grid_rows - 1)
        self.row_spinbox.setValue(0)
        self.row_spinbox.valueChanged.connect(self._on_row_changed)
        row_select_layout.addWidget(self.row_spinbox)
        setup_layout.addLayout(row_select_layout)

        gpio_layout = QHBoxLayout()
        gpio_layout.addWidget(QLabel("GPIO Pin:"))
        self.gpio_input = QLineEdit()
        self.gpio_input.setPlaceholderText("e.g., GPIOA_0, PB1")
        gpio_layout.addWidget(self.gpio_input)
        setup_layout.addLayout(gpio_layout)

        btn_layout = QHBoxLayout()
        self.assign_btn = QPushButton("✓ Assign GPIO to Row")
        self.assign_btn.clicked.connect(self._assign_gpio)
        self.assign_btn.setStyleSheet(f"background-color: {ACCENT_GREEN}; color: {DARK_BG};")
        btn_layout.addWidget(self.assign_btn)

        self.auto_detect_btn = QPushButton("🔍 Auto-Detect")
        self.auto_detect_btn.clicked.connect(self._toggle_auto_detect)
        btn_layout.addWidget(self.auto_detect_btn)
        setup_layout.addLayout(btn_layout)

        self.auto_status = QLabel("")
        self.auto_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        setup_layout.addWidget(self.auto_status)

        right_panel.addWidget(setup_group)

        # ADC Configuration
        adc_group = QGroupBox("ADC Channel Configuration")
        adc_layout = QVBoxLayout(adc_group)

        adc_info = QLabel("Configure ADC channels used for column scanning:")
        adc_info.setWordWrap(True)
        adc_layout.addWidget(adc_info)

        self.adc_table = QTableWidget(2, 2)
        self.adc_table.setHorizontalHeaderLabels(["Channel", "ADC Name"])
        self.adc_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.adc_table.setMaximumHeight(120)

        for i in range(2):
            self.adc_table.setItem(i, 0, QTableWidgetItem(f"Channel {i}"))
            adc_name = self.config.get_adc_channel(i) or f"ADC1_IN{i}"
            adc_input = QLineEdit(adc_name)
            self.adc_table.setCellWidget(i, 1, adc_input)

        adc_layout.addWidget(self.adc_table)
        right_panel.addWidget(adc_group)

        # Validation
        validation_group = QGroupBox("Configuration Status")
        validation_layout = QVBoxLayout(validation_group)

        self.validation_text = QTextEdit()
        self.validation_text.setReadOnly(True)
        self.validation_text.setMaximumHeight(100)
        validation_layout.addWidget(self.validation_text)

        self.validate_btn = QPushButton("🔍 Validate Config")
        self.validate_btn.clicked.connect(self._validate_config)
        validation_layout.addWidget(self.validate_btn)

        right_panel.addWidget(validation_group)

        main_h_layout.addLayout(right_panel, stretch=1)
        layout.addLayout(main_h_layout)

        # Bottom buttons
        bottom_layout = QHBoxLayout()

        self.save_btn = QPushButton("💾 Save Configuration")
        self.save_btn.clicked.connect(self._save_config)
        self.save_btn.setStyleSheet(f"background-color: {ACCENT_BLUE}; color: {DARK_BG};")
        bottom_layout.addWidget(self.save_btn)

        self.export_btn = QPushButton("📤 Export C Header")
        self.export_btn.clicked.connect(self._export_header)
        bottom_layout.addWidget(self.export_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(self.close_btn)

        layout.addLayout(bottom_layout)

        # Apply dark theme
        self.setStyleSheet(f"""
            QDialog {{
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
            QLineEdit {{
                background-color: {DARK_SURFACE};
                border: 1px solid {DARK_SURFACE};
                border-radius: 4px;
                padding: 5px;
                color: {DARK_TEXT};
            }}
            QTableWidget {{
                background-color: {DARK_SURFACE};
                alternate-background-color: {DARK_BG};
                gridline-color: {DARK_BG};
            }}
            QTextEdit {{
                background-color: {DARK_SURFACE};
                border: 1px solid {DARK_BG};
                border-radius: 4px;
                color: {DARK_TEXT};
            }}
        """)

    def _update_table(self):
        """Update the configuration table with current settings."""
        for row in range(self.grid_rows):
            # Row number
            self.config_table.setItem(row, 0, QTableWidgetItem(str(row)))

            # GPIO pin
            gpio = self.config.get_row_gpio(row) or "UNDEFINED"
            gpio_item = QTableWidgetItem(gpio)
            if "UNDEFINED" in gpio:
                gpio_item.setForeground(QColor(ACCENT_RED))
            else:
                gpio_item.setForeground(QColor(ACCENT_GREEN))
            self.config_table.setItem(row, 1, gpio_item)

            # Status
            status = "✓ Configured" if "UNDEFINED" not in gpio else "⚠ Not Set"
            status_item = QTableWidgetItem(status)
            status_item.setForeground(QColor(ACCENT_GREEN if "✓" in status else ACCENT_YELLOW))
            self.config_table.setItem(row, 2, status_item)

    def _on_row_changed(self, row):
        """Handle row selection change."""
        self.current_setup_row = row
        gpio = self.config.get_row_gpio(row)
        if gpio and "UNDEFINED" not in gpio:
            self.gpio_input.setText(gpio)
        else:
            self.gpio_input.clear()

    def _assign_gpio(self):
        """Assign GPIO pin to current row."""
        gpio_pin = self.gpio_input.text().strip()
        if not gpio_pin:
            QMessageBox.warning(self, "Invalid Input", "Please enter a GPIO pin name.")
            return

        try:
            self.config.set_row_gpio(self.current_setup_row, gpio_pin)
            self._update_table()
            QMessageBox.information(self, "Success",
                                    f"GPIO '{gpio_pin}' assigned to Row {self.current_setup_row}")

            # Move to next row
            if self.current_setup_row < self.grid_rows - 1:
                self.row_spinbox.setValue(self.current_setup_row + 1)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to assign GPIO: {e}")

    def _toggle_auto_detect(self):
        """Toggle auto-detection mode."""
        self.is_monitoring = not self.is_monitoring
        if self.is_monitoring:
            self.auto_detect_btn.setText("⏹ Stop Detection")
            self.auto_detect_btn.setStyleSheet(f"background-color: {ACCENT_RED}; color: {DARK_BG};")
            self.auto_status.setText("Press on the physical grid...")
            self.auto_status.setStyleSheet(f"color: {ACCENT_GREEN};")
        else:
            self.auto_detect_btn.setText("🔍 Auto-Detect")
            self.auto_detect_btn.setStyleSheet("")
            self.auto_status.setText("")

    def update_frame(self, frame: np.ndarray):
        """
        Update with new frame from serial data.
        Call this from main GUI when in setup mode.
        """
        self.current_frame = frame
        self.grid_image.setImage(frame.T, autoLevels=False)

        # Detect active row
        self._detect_active_row(frame)

    def _detect_active_row(self, frame: np.ndarray):
        """Detect which row has the most activity."""
        row_sums = np.sum(frame, axis=1)
        max_row = np.argmax(row_sums)
        max_value = row_sums[max_row]

        # Threshold for detection
        if max_value > 1000:  # Significant pressure
            self.detected_row = max_row
            self.detection_label.setText(f"✓ Row {max_row} detected (pressure: {max_value:.0f})")
            self.detection_label.setStyleSheet(f"color: {ACCENT_GREEN}; font-weight: bold; font-size: 12px;")

            # If in auto-detect mode, suggest this row
            if self.is_monitoring:
                self.row_spinbox.setValue(max_row)
                self.auto_status.setText(f"✓ Detected Row {max_row} - Enter GPIO pin above")
                self.auto_status.setStyleSheet(f"color: {ACCENT_GREEN}; font-weight: bold;")
        else:
            self.detected_row = None
            if not self.is_monitoring:
                self.detection_label.setText("Waiting for press...")
                self.detection_label.setStyleSheet(f"color: {ACCENT_YELLOW}; font-weight: bold; font-size: 12px;")

    def _validate_config(self):
        """Validate the current configuration."""
        # Update ADC configuration from table
        for i in range(2):
            adc_input = self.adc_table.cellWidget(i, 1)
            if isinstance(adc_input, QLineEdit):
                adc_name = adc_input.text().strip()
                if adc_name:
                    self.config.set_adc_channel(i, adc_name)

        # Validate
        issues = self.config.validate()

        if not issues:
            self.validation_text.setHtml(
                f"<span style='color: {ACCENT_GREEN}; font-weight: bold;'>"
                "✓ Configuration is valid!</span>"
            )
        else:
            issue_text = "<br>".join([f"⚠ {issue}" for issue in issues])
            self.validation_text.setHtml(
                f"<span style='color: {ACCENT_RED};'><b>Configuration Issues:</b><br>{issue_text}</span>"
            )

    def _save_config(self):
        """Save configuration to file."""
        # Update ADC config first
        for i in range(2):
            adc_input = self.adc_table.cellWidget(i, 1)
            if isinstance(adc_input, QLineEdit):
                adc_name = adc_input.text().strip()
                if adc_name:
                    self.config.set_adc_channel(i, adc_name)

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Hardware Configuration", "hardware_config.json", "JSON Files (*.json)"
        )

        if filepath:
            try:
                self.config.save(filepath)
                save_default_config(self.config)
                QMessageBox.information(self, "Success",
                                        f"Configuration saved to:\n{filepath}")
                self.config_updated.emit(self.config)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save configuration:\n{e}")

    def _export_header(self):
        """Export configuration as C header file."""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export C Header", "hardware_config.h", "Header Files (*.h)"
        )

        if filepath:
            try:
                self.config.export_c_header(filepath)
                QMessageBox.information(self, "Success",
                                        f"C header exported to:\n{filepath}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export header:\n{e}")
