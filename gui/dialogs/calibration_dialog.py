"""
================================================================================
Calibration Dialog - Spine Calibration Workflow
================================================================================

This module provides a friendly dialog for calibrating spinal landmarks.
The user drags their finger along the patient's spine while the system
records the pressure pattern to identify the vertebral column.

Design Philosophy:
    "Design is not just what it looks like and feels like.
     Design is how it works." - Steve Jobs

The dialog guides users through calibration with clear instructions,
visual feedback, and encouraging messages.
"""

import numpy as np
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor

try:
    from ..styles.theme import COLORS, FONT_FAMILY
    from ..widgets.animated_button import AnimatedButton
except ImportError:
    from styles.theme import COLORS, FONT_FAMILY
    from widgets.animated_button import AnimatedButton

from spine_detector import SpineDetector


class CalibrationDialog(QDialog):
    """
    Friendly calibration dialog for spine detection.

    The dialog guides users through the calibration process:
        1. Position the mat on the patient's back
        2. Press "Start Recording"
        3. Drag finger along the spine from top to bottom
        4. Press "Stop Recording"
        5. System processes and identifies L1-L5 landmarks

    Signals:
        calibration_complete: Emitted with SpineDetector when calibration succeeds

    Example:
        >>> dialog = CalibrationDialog(parent)
        >>> dialog.calibration_complete.connect(self.on_calibration_done)
        >>> dialog.show()
    """

    # Signal emitted when calibration completes successfully
    calibration_complete = pyqtSignal(object)

    def __init__(self, parent=None):
        """
        Initialize the calibration dialog.

        Args:
            parent: Parent widget (optional)
        """
        super().__init__(parent)
        self.setWindowTitle("Spine Calibration")
        self.setMinimumSize(500, 350)
        self.setModal(True)

        # Spine detection engine
        self.detector = SpineDetector()

        # State tracking
        self._is_recording = False
        self._frame_count = 0

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the dialog's user interface."""
        self._apply_styling()

        layout = QVBoxLayout(self)
        layout.setSpacing(24)
        layout.setContentsMargins(40, 40, 40, 40)

        # Title
        layout.addWidget(self._create_title())

        # Instructions
        layout.addWidget(self._create_instructions())

        # Progress bar
        self.progress_bar = self._create_progress_bar()
        layout.addWidget(self.progress_bar)

        # Status label
        self.status_label = self._create_status_label()
        layout.addWidget(self.status_label)

        layout.addStretch()

        # Buttons
        layout.addLayout(self._create_buttons())

    def _apply_styling(self) -> None:
        """Apply stylesheet to the dialog."""
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {COLORS['bg_main']};
            }}
            QLabel {{
                font-family: {FONT_FAMILY};
                color: {COLORS['text_dark']};
            }}
        """)

    def _create_title(self) -> QLabel:
        """Create the title label."""
        title = QLabel("Let's Calibrate!")
        title.setFont(QFont("Comic Sans MS", 24, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {COLORS['primary']};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return title

    def _create_instructions(self) -> QLabel:
        """Create the instructions label."""
        instructions = QLabel(
            "Place the mat on the patient's back.\n"
            "Press Start, then drag your finger\n"
            "along the spine from top to bottom!"
        )
        instructions.setFont(QFont("Comic Sans MS", 12))
        instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instructions.setStyleSheet(f"color: {COLORS['text_light']};")
        return instructions

    def _create_progress_bar(self) -> QProgressBar:
        """Create the progress indicator."""
        progress = QProgressBar()
        progress.setRange(0, 100)
        progress.setValue(0)
        progress.setTextVisible(False)
        progress.setFixedHeight(12)
        progress.setStyleSheet(f"""
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
        return progress

    def _create_status_label(self) -> QLabel:
        """Create the status message label."""
        status = QLabel("Ready when you are!")
        status.setFont(QFont("Comic Sans MS", 11, QFont.Weight.Bold))
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status.setStyleSheet(f"color: {COLORS['warning']};")
        return status

    def _create_buttons(self) -> QHBoxLayout:
        """Create the action buttons."""
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(16)

        # Record button
        self.record_btn = AnimatedButton("Start Recording", "success")
        self.record_btn.clicked.connect(self._toggle_recording)
        btn_layout.addWidget(self.record_btn)

        # Cancel button
        self.cancel_btn = AnimatedButton("Cancel", "secondary")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        return btn_layout

    def _toggle_recording(self) -> None:
        """Handle record button clicks."""
        if self._is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        """Begin recording calibration frames."""
        self._is_recording = True
        self._frame_count = 0

        # Start detector calibration
        self.detector.start_calibration()

        # Update UI
        self.record_btn.setText("Stop Recording")
        self.record_btn.set_color_scheme("danger")

        self.status_label.setText("Recording... Drag along the spine!")
        self.status_label.setStyleSheet(f"color: {COLORS['success']};")

    def _stop_recording(self) -> None:
        """Stop recording and process calibration."""
        self._is_recording = False

        # Update button
        self.record_btn.setText("Start Recording")
        self.record_btn.set_color_scheme("success")

        # Finalize calibration
        success, message = self.detector.finalize_calibration()

        if success:
            self._on_calibration_success()
        else:
            self._on_calibration_failure(message)

    def _on_calibration_success(self) -> None:
        """Handle successful calibration."""
        self.status_label.setText("Awesome! Calibration complete!")
        self.status_label.setStyleSheet(f"color: {COLORS['success']};")
        self.progress_bar.setValue(100)

        # Auto-close after showing success message
        QTimer.singleShot(1500, self._accept_calibration)

    def _on_calibration_failure(self, message: str) -> None:
        """Handle failed calibration."""
        self.status_label.setText(f"Oops! {message}")
        self.status_label.setStyleSheet(f"color: {COLORS['danger']};")
        self.progress_bar.setValue(0)

    def _accept_calibration(self) -> None:
        """Emit success signal and close dialog."""
        self.calibration_complete.emit(self.detector)
        self.accept()

    def add_frame(self, frame: np.ndarray) -> None:
        """
        Add a pressure frame during calibration recording.

        This method should be called by the parent window whenever
        new sensor data is received while calibration is active.

        Args:
            frame: 20x12 numpy array of pressure values
        """
        if self._is_recording:
            self.detector.add_calibration_frame(frame)
            self._frame_count += 1

            # Update progress (aim for ~50 frames)
            progress = min(100, int(self._frame_count / 50 * 100))
            self.progress_bar.setValue(progress)

    @property
    def is_recording(self) -> bool:
        """Check if calibration recording is active."""
        return self._is_recording
