"""
================================================================================
Indicator Widgets - Status and Progress Display
================================================================================

This module provides visual indicators for status, progress, and data
visualization. Each indicator is designed to communicate clearly at a glance.

Design Philosophy:
    "Make it simple. Make it memorable. Make it inviting to look at.
     Make it fun to read." - Leo Burnett

These indicators provide immediate visual feedback without requiring
the user to read text or process numbers.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QRect, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QBrush, QPen, QLinearGradient, QFont

try:
    from ..styles.theme import COLORS, HEATMAP_COLORS
except ImportError:
    from styles.theme import COLORS, HEATMAP_COLORS


class PulsingDot(QWidget):
    """
    A pulsing dot indicator for active status display.

    The dot pulses smoothly to indicate ongoing activity (like recording).
    This creates an organic, living feel that draws attention without
    being distracting.

    Features:
        - Smooth pulsing animation
        - Glowing effect with transparency
        - Configurable color

    Example:
        >>> dot = PulsingDot("#d63031")  # Red dot
        >>> dot.start()  # Begin pulsing
        >>> dot.stop()   # Stop and reset
    """

    def __init__(self, color: str = "#d63031", parent=None):
        """
        Initialize the pulsing dot.

        Args:
            color: The dot color (hex string)
            parent: Parent widget (optional)
        """
        super().__init__(parent)
        self.color = color
        self._pulse = 1.0

        # Fixed size for consistent appearance
        self.setFixedSize(20, 20)

        self._setup_animation()

    def _setup_animation(self) -> None:
        """Initialize the pulse animation."""
        self._pulse_anim = QPropertyAnimation(self, b"pulse")
        self._pulse_anim.setDuration(800)  # Relaxed, not frantic
        self._pulse_anim.setStartValue(0.5)
        self._pulse_anim.setEndValue(1.0)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse_anim.setLoopCount(-1)  # Loop indefinitely

    @pyqtProperty(float)
    def pulse(self) -> float:
        """Get the current pulse value (0.5 to 1.0)."""
        return self._pulse

    @pulse.setter
    def pulse(self, value: float) -> None:
        """Set the pulse value and trigger repaint."""
        self._pulse = value
        self.update()

    def start(self) -> None:
        """Start the pulsing animation."""
        self._pulse_anim.start()

    def stop(self) -> None:
        """Stop the animation and reset to full visibility."""
        self._pulse_anim.stop()
        self._pulse = 1.0
        self.update()

    def paintEvent(self, event) -> None:
        """Paint the pulsing dot with glow effect."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Outer glow (size and opacity vary with pulse)
        color = QColor(self.color)
        color.setAlpha(int(100 * self._pulse))
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)

        # Calculate size based on pulse
        size = 8 + int(6 * self._pulse)
        x = (self.width() - size) // 2
        y = (self.height() - size) // 2
        painter.drawEllipse(x, y, size, size)

        # Center dot (constant size)
        painter.setBrush(QBrush(QColor(self.color)))
        painter.drawEllipse(7, 7, 6, 6)


class ColorLegendWidget(QWidget):
    """
    Vertical color legend for the pressure heatmap.

    Displays the pressure scale from low to high with a gradient bar
    and labels, helping users interpret the heatmap colors.

    Features:
        - Vertical gradient matching heatmap colors
        - Clear "High" and "Low" labels
        - Compact design that doesn't distract from the main view

    Example:
        >>> legend = ColorLegendWidget()
        >>> layout.addWidget(legend)
    """

    def __init__(self, parent=None):
        """
        Initialize the color legend.

        Args:
            parent: Parent widget (optional)
        """
        super().__init__(parent)
        self.setFixedWidth(70)
        self.setMinimumHeight(200)

    def paintEvent(self, event) -> None:
        """Paint the color legend with gradient and labels."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Background
        painter.fillRect(self.rect(), QColor(COLORS['bg_card']))

        # Calculate gradient bar dimensions
        gradient_rect = QRect(10, 40, 20, self.height() - 80)

        # Create vertical gradient (bottom=low, top=high)
        gradient = QLinearGradient(
            0, gradient_rect.bottom(),
            0, gradient_rect.top()
        )

        # Add color stops
        for i, color in enumerate(HEATMAP_COLORS):
            pos = i / (len(HEATMAP_COLORS) - 1)
            gradient.setColorAt(pos, QColor(*color))

        # Draw gradient bar with rounded corners
        painter.setBrush(gradient)
        painter.setPen(QPen(QColor(COLORS['border']), 1))
        painter.drawRoundedRect(gradient_rect, 4, 4)

        # Draw labels
        painter.setPen(QPen(QColor(COLORS['text_dark'])))
        font = QFont("Comic Sans MS", 9)
        painter.setFont(font)

        # Title
        painter.drawText(5, 25, "Pressure")

        # High label (at top of gradient)
        painter.drawText(35, gradient_rect.top() + 12, "High")

        # Low label (at bottom of gradient)
        painter.drawText(35, gradient_rect.bottom() + 4, "Low")
