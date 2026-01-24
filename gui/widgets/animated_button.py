"""
================================================================================
Animated Button Widget
================================================================================

A custom button with smooth press and hover animations that provides
satisfying tactile feedback to users.

Design Philosophy:
    "Details matter, it's worth waiting to get it right." - Steve Jobs

The button responds to user interaction with:
    - Scale animation on press (shrinks slightly)
    - Color transition on hover
    - Subtle shadow for depth

This creates a physical, tangible feel that makes the interface
more engaging and intuitive.
"""

from PyQt6.QtWidgets import QPushButton, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QRect, pyqtProperty
from PyQt6.QtGui import QFont, QColor, QPainter, QBrush, QPen

try:
    from ..styles.theme import COLORS, FONT_FAMILY
except ImportError:
    from styles.theme import COLORS, FONT_FAMILY


class AnimatedButton(QPushButton):
    """
    A button with smooth press and hover animations.

    The button provides visual feedback through:
        - Scale animation on mouse press (0.95x)
        - Background color transition on hover
        - Drop shadow for depth perception

    Attributes:
        color_scheme: The color scheme ('primary', 'success', 'danger', 'secondary')

    Example:
        >>> btn = AnimatedButton("Click Me", "primary")
        >>> btn.clicked.connect(my_handler)
    """

    def __init__(self, text: str, color_scheme: str = "primary", parent=None):
        """
        Initialize the animated button.

        Args:
            text: Button label text
            color_scheme: Color scheme - one of 'primary', 'success', 'danger', 'secondary'
            parent: Parent widget (optional)
        """
        super().__init__(text, parent)

        self.color_scheme = color_scheme
        self._scale = 1.0
        self._bg_color = QColor(COLORS[f'btn_{color_scheme}'])

        self._setup_appearance()
        self._setup_animations()

    def _setup_appearance(self) -> None:
        """Configure the button's visual appearance."""
        # Font
        self.setFont(QFont("Comic Sans MS", 11, QFont.Weight.Bold))

        # Cursor
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Minimum size for touch-friendly interactions
        self.setMinimumHeight(45)

        # Drop shadow for depth
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

        # Apply initial style
        self._update_style()

    def _setup_animations(self) -> None:
        """Initialize the animation objects."""
        # Scale animation for press feedback
        self._scale_anim = QPropertyAnimation(self, b"scale")
        self._scale_anim.setDuration(100)
        self._scale_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Color animation for hover feedback
        self._color_anim = QPropertyAnimation(self, b"bgColor")
        self._color_anim.setDuration(150)
        self._color_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _update_style(self) -> None:
        """Update the button stylesheet based on current color."""
        bg = self._bg_color.name()
        text_color = COLORS['text_white'] if self.color_scheme != 'secondary' else COLORS['text_dark']

        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {text_color};
                border: none;
                border-radius: 12px;
                padding: 12px 24px;
                font-family: {FONT_FAMILY};
                font-weight: bold;
                font-size: 12px;
            }}
        """)

    # =========================================================================
    # Qt Properties for Animation
    # =========================================================================

    @pyqtProperty(float)
    def scale(self) -> float:
        """Get the current scale factor."""
        return self._scale

    @scale.setter
    def scale(self, value: float) -> None:
        """Set the scale factor and trigger repaint."""
        self._scale = value
        self.update()

    @pyqtProperty(QColor)
    def bgColor(self) -> QColor:
        """Get the current background color."""
        return self._bg_color

    @bgColor.setter
    def bgColor(self, value: QColor) -> None:
        """Set the background color and update style."""
        self._bg_color = value
        self._update_style()

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def enterEvent(self, event) -> None:
        """Handle mouse enter - transition to hover color."""
        self._color_anim.stop()
        self._color_anim.setStartValue(self._bg_color)
        self._color_anim.setEndValue(QColor(COLORS[f'btn_{self.color_scheme}_hover']))
        self._color_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        """Handle mouse leave - transition back to base color."""
        self._color_anim.stop()
        self._color_anim.setStartValue(self._bg_color)
        self._color_anim.setEndValue(QColor(COLORS[f'btn_{self.color_scheme}']))
        self._color_anim.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        """Handle mouse press - scale down for tactile feedback."""
        self._scale_anim.stop()
        self._scale_anim.setStartValue(1.0)
        self._scale_anim.setEndValue(0.95)
        self._scale_anim.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        """Handle mouse release - scale back to normal."""
        self._scale_anim.stop()
        self._scale_anim.setStartValue(0.95)
        self._scale_anim.setEndValue(1.0)
        self._scale_anim.start()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event) -> None:
        """
        Custom paint event to apply scale transformation.

        When the button is scaled (during press animation), we need to
        manually handle the painting to apply the transform correctly.
        """
        if self._scale != 1.0:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Calculate scaled dimensions
            w = int(self.width() * self._scale)
            h = int(self.height() * self._scale)
            x = (self.width() - w) // 2
            y = (self.height() - h) // 2

            # Apply transformation
            painter.translate(x, y)
            painter.scale(self._scale, self._scale)

            # Draw background
            painter.setBrush(QBrush(self._bg_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(0, 0, self.width(), self.height(), 12, 12)

            # Draw text
            text_color = COLORS['text_white'] if self.color_scheme != 'secondary' else COLORS['text_dark']
            painter.setPen(QPen(QColor(text_color)))
            painter.setFont(self.font())
            painter.drawText(
                QRect(0, 0, self.width(), self.height()),
                Qt.AlignmentFlag.AlignCenter,
                self.text()
            )
            painter.end()
        else:
            # Use default painting when not scaled
            super().paintEvent(event)

    # =========================================================================
    # Public Methods
    # =========================================================================

    def set_color_scheme(self, scheme: str) -> None:
        """
        Change the button's color scheme.

        Args:
            scheme: New color scheme ('primary', 'success', 'danger', 'secondary')
        """
        self.color_scheme = scheme
        self._bg_color = QColor(COLORS[f'btn_{scheme}'])
        self._update_style()
