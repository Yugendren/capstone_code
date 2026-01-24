"""
================================================================================
Warning Widgets - Alert and Notification Display
================================================================================

This module provides attention-grabbing warning displays for critical
feedback like drift detection during recording.

Design Philosophy:
    "Fail fast, fail often, but always fail forward." - John Maxwell

Warnings should be impossible to miss but not jarring. The bounce
animation creates urgency while remaining friendly.
"""

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QPoint
from PyQt6.QtGui import QFont, QColor

try:
    from ..styles.theme import COLORS, FONT_FAMILY
except ImportError:
    from styles.theme import COLORS, FONT_FAMILY


class DriftWarningWidget(QWidget):
    """
    Animated drift warning with bounce effect.

    Appears when the user moves away from the target landmark during
    recording. The warning bounces in to grab attention and plays
    a system beep.

    Features:
        - Bounce-in animation
        - High-contrast red background
        - Clear messaging
        - System beep audio alert

    Example:
        >>> warning = DriftWarningWidget(parent)
        >>> warning.move(250, 150)  # Position in parent
        >>> warning.show_warning("Move back to L3")
        >>> warning.hide_warning()
    """

    def __init__(self, parent=None):
        """
        Initialize the drift warning widget.

        Args:
            parent: Parent widget (required for positioning)
        """
        super().__init__(parent)

        # Hidden by default
        self.setVisible(False)
        self.setFixedSize(320, 90)

        self._setup_ui()
        self._setup_animation()

    def _setup_ui(self) -> None:
        """Build the warning UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)

        # Main warning text
        self.warning_label = QLabel("Oops! You drifted!")
        self.warning_label.setFont(QFont("Comic Sans MS", 14, QFont.Weight.Bold))
        self.warning_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.warning_label.setStyleSheet(f"color: {COLORS['text_white']};")
        layout.addWidget(self.warning_label)

        # Detail text
        self.detail_label = QLabel("Move back to the target")
        self.detail_label.setFont(QFont("Comic Sans MS", 11))
        self.detail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.detail_label.setStyleSheet("color: rgba(255,255,255,0.8);")
        layout.addWidget(self.detail_label)

        # Widget styling
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {COLORS['danger']};
                border-radius: 20px;
            }}
        """)

        # Red glow shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(30)
        shadow.setColor(QColor(214, 48, 49, 100))
        shadow.setOffset(0, 8)
        self.setGraphicsEffect(shadow)

    def _setup_animation(self) -> None:
        """Initialize the bounce animation."""
        self._bounce_anim = QPropertyAnimation(self, b"pos")
        self._bounce_anim.setDuration(100)
        self._bounce_anim.setEasingCurve(QEasingCurve.Type.OutBounce)

    def show_warning(self, message: str = "Move back to target") -> None:
        """
        Show the warning with a bounce animation.

        Args:
            message: The detail message to display
        """
        self.detail_label.setText(message)
        self.setVisible(True)

        # Animate bouncing in from above
        start_pos = self.pos()
        self._bounce_anim.setStartValue(QPoint(start_pos.x(), start_pos.y() - 20))
        self._bounce_anim.setEndValue(start_pos)
        self._bounce_anim.start()

        # System beep for audio alert
        self._play_beep()

    def hide_warning(self) -> None:
        """Hide the warning widget."""
        self.setVisible(False)

    def _play_beep(self) -> None:
        """Play a system beep sound."""
        # Cross-platform system beep using terminal bell
        print('\a', end='', flush=True)
