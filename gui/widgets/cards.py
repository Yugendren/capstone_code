"""
================================================================================
Card Widgets - Container Components
================================================================================

Card widgets provide visual grouping for related UI elements.
They feature rounded corners, subtle shadows, and clean typography.

Design Philosophy:
    "Design is a funny word. Some people think design means how it looks.
     But of course, if you dig deeper, it's really how it works." - Steve Jobs

Cards create visual hierarchy and help users understand which elements
belong together without adding cognitive load.
"""

from PyQt6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QLabel, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

try:
    from ..styles.theme import COLORS, FONT_FAMILY
except ImportError:
    from styles.theme import COLORS, FONT_FAMILY


class FriendlyCard(QFrame):
    """
    A card widget with shadow and rounded corners.

    Cards group related content together and provide visual separation
    from the background. They feature:
        - Soft drop shadow for depth
        - Rounded corners (16px radius)
        - Optional title header
        - Clean white background

    Example:
        >>> card = FriendlyCard("Settings")
        >>> card.add_widget(my_button)
        >>> card.add_layout(my_horizontal_layout)
    """

    def __init__(self, title: str = "", parent=None):
        """
        Initialize the card widget.

        Args:
            title: Optional title displayed at the top of the card
            parent: Parent widget (optional)
        """
        super().__init__(parent)
        self.title = title

        self._setup_appearance()
        self._setup_layout()

        if title:
            self._add_title(title)

    def _setup_appearance(self) -> None:
        """Configure the card's visual appearance."""
        # Stylesheet for background and border
        self.setStyleSheet(f"""
            FriendlyCard {{
                background-color: {COLORS['bg_card']};
                border-radius: 16px;
                border: 1px solid {COLORS['border']};
            }}
        """)

        # Drop shadow for depth perception
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 25))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    def _setup_layout(self) -> None:
        """Initialize the internal layout."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(16)

    def _add_title(self, title: str) -> None:
        """Add a title label to the card."""
        title_label = QLabel(title)
        title_label.setFont(QFont("Comic Sans MS", 14, QFont.Weight.Bold))
        title_label.setStyleSheet(
            f"color: {COLORS['text_dark']}; background: transparent; border: none;"
        )
        self.main_layout.addWidget(title_label)

    def add_widget(self, widget: QWidget) -> None:
        """
        Add a widget to the card's layout.

        Args:
            widget: The widget to add
        """
        self.main_layout.addWidget(widget)

    def add_layout(self, layout) -> None:
        """
        Add a layout to the card's layout.

        Args:
            layout: The layout to add (QHBoxLayout, QVBoxLayout, etc.)
        """
        self.main_layout.addLayout(layout)


class StatDisplay(QWidget):
    """
    A compact statistic display widget.

    Displays a numeric value with a label underneath, perfect for
    showing metrics like Peak, Trough, Frequency, etc.

    Features:
        - Large, bold value text
        - Smaller label text below
        - Customizable accent color
        - Subtle border and background

    Example:
        >>> stat = StatDisplay("Peak", "0", "#d63031")
        >>> stat.set_value("2500")
    """

    def __init__(self, label: str, value: str = "0", color: str = None, parent=None):
        """
        Initialize the stat display.

        Args:
            label: The label text (displayed below the value)
            value: Initial value to display
            color: Accent color for the value (defaults to primary)
            parent: Parent widget (optional)
        """
        super().__init__(parent)
        self.color = color or COLORS['primary']

        self._setup_layout()
        self._setup_value_label(value)
        self._setup_text_label(label)
        self._setup_appearance()

    def _setup_layout(self) -> None:
        """Initialize the internal layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout = layout

    def _setup_value_label(self, value: str) -> None:
        """Create and configure the value label."""
        self.value_label = QLabel(value)
        self.value_label.setFont(QFont("Comic Sans MS", 24, QFont.Weight.Bold))
        self.value_label.setStyleSheet(f"color: {self.color};")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self.value_label)

    def _setup_text_label(self, label: str) -> None:
        """Create and configure the text label."""
        label_widget = QLabel(label)
        label_widget.setFont(QFont("Comic Sans MS", 11))
        label_widget.setStyleSheet(f"color: {COLORS['text_light']}; padding: 2px 0px;")
        label_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(label_widget)

    def _setup_appearance(self) -> None:
        """Configure the widget's visual appearance."""
        self.setStyleSheet(f"""
            StatDisplay {{
                background-color: {COLORS['bg_card']};
                border-radius: 12px;
                border: 1px solid {COLORS['border']};
            }}
        """)

    def set_value(self, value: str) -> None:
        """
        Update the displayed value.

        Args:
            value: New value to display
        """
        self.value_label.setText(value)
