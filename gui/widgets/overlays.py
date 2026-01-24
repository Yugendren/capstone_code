"""
================================================================================
Overlay Widgets - Heatmap Annotations
================================================================================

This module provides overlay graphics for the pressure heatmap,
including spinal landmark visualization.

Design Philosophy:
    "Good design is as little design as possible." - Dieter Rams

The overlays provide essential anatomical context without cluttering
the visualization. They should enhance understanding, not distract.
"""

import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush

try:
    from ..styles.theme import COLORS
    from ..utils.constants import GRID_ROWS, GRID_COLS
except ImportError:
    from styles.theme import COLORS
    from utils.constants import GRID_ROWS, GRID_COLS


class LandmarkOverlay(pg.GraphicsObject):
    """
    Overlay for displaying spinal landmarks on the heatmap.

    Visualizes calibrated L1-L5 vertebral landmarks with:
        - Center point for estimated location
        - Uncertainty circle showing possible area
        - Spine line connecting landmarks
        - Labels for each vertebra level

    The overlay uses semi-transparent elements to avoid obscuring
    the underlying pressure data.

    Example:
        >>> overlay = LandmarkOverlay()
        >>> plot_widget.addItem(overlay)
        >>> overlay.set_landmarks(landmarks, spine_line)
        >>> overlay.highlight(selected_landmark)
    """

    def __init__(self, parent=None):
        """
        Initialize the landmark overlay.

        Args:
            parent: Parent graphics item (optional)
        """
        super().__init__(parent)
        self.landmarks: list = []
        self.spine_line = None
        self.highlight_landmark = None
        self.uncertainty_radius = 2.5

    def set_landmarks(self, landmarks: list, spine_line=None) -> None:
        """
        Update the displayed landmarks.

        Args:
            landmarks: List of SpinalLandmark objects
            spine_line: SpineLine object for the spine axis (optional)
        """
        self.landmarks = landmarks
        self.spine_line = spine_line
        self.update()

    def highlight(self, landmark) -> None:
        """
        Highlight a specific landmark.

        Args:
            landmark: The SpinalLandmark to highlight, or None to clear
        """
        self.highlight_landmark = landmark
        self.update()

    def boundingRect(self):
        """Return the bounding rectangle for the overlay."""
        return pg.QtCore.QRectF(0, 0, GRID_COLS, GRID_ROWS)

    def paint(self, painter, option, widget) -> None:
        """
        Paint the landmarks and spine line.

        Args:
            painter: QPainter instance
            option: Style options (unused)
            widget: Target widget (unused)
        """
        if not self.landmarks:
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw spine line if available
        if self.spine_line:
            self._draw_spine_line(painter)

        # Draw each landmark
        for landmark in self.landmarks:
            self._draw_landmark(painter, landmark)

    def _draw_spine_line(self, painter: QPainter) -> None:
        """Draw the central spine axis line."""
        pen = QPen(QColor(COLORS['primary']))
        pen.setWidthF(0.2)
        pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)

        # Calculate line endpoints
        y1 = self.spine_line.start_row
        x1 = self.spine_line.get_col_at_row(y1)
        y2 = self.spine_line.end_row
        x2 = self.spine_line.get_col_at_row(y2)

        painter.drawLine(int(x1), int(y1), int(x2), int(y2))

    def _draw_landmark(self, painter: QPainter, landmark) -> None:
        """
        Draw a single landmark with its uncertainty circle.

        Args:
            painter: QPainter instance
            landmark: SpinalLandmark object
        """
        # Check if this landmark is highlighted
        is_highlighted = (
            self.highlight_landmark and
            landmark.level == self.highlight_landmark.level and
            landmark.landmark_type == self.highlight_landmark.landmark_type
        )

        if landmark.landmark_type == 'spinous':
            self._draw_spinous_process(painter, landmark, is_highlighted)
        else:
            self._draw_transverse_process(painter, landmark, is_highlighted)

    def _draw_spinous_process(self, painter: QPainter, landmark, is_highlighted: bool) -> None:
        """
        Draw a spinous process landmark (center of vertebra).

        Includes:
            - Uncertainty circle (area where landmark might be)
            - Center point (estimated exact location)
            - Label (e.g., "L1", "L2")
        """
        # Uncertainty circle
        color = QColor(COLORS['info'])
        color.setAlpha(60)
        painter.setPen(QPen(QColor(COLORS['info']), 0.1))
        painter.setBrush(QBrush(color))

        # Larger radius when highlighted
        radius = self.uncertainty_radius * 1.5 if is_highlighted else self.uncertainty_radius
        painter.drawEllipse(
            pg.QtCore.QPointF(landmark.col, landmark.row),
            radius, radius
        )

        # Center point
        center_color = QColor(COLORS['success']) if is_highlighted else QColor(COLORS['text_white'])
        painter.setPen(QPen(center_color, 0.15))
        painter.setBrush(QBrush(center_color))
        painter.drawEllipse(
            pg.QtCore.QPointF(landmark.col, landmark.row),
            0.4, 0.4
        )

        # Label
        painter.setPen(QPen(QColor(COLORS['text_white'])))
        font = painter.font()
        font.setPointSizeF(2.5)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            pg.QtCore.QPointF(landmark.col + 1, landmark.row + 0.5),
            landmark.level
        )

    def _draw_transverse_process(self, painter: QPainter, landmark, is_highlighted: bool) -> None:
        """
        Draw a transverse process landmark (sides of vertebra).

        These are smaller and less prominent than spinous processes.
        """
        color = QColor(COLORS['warning']) if is_highlighted else QColor(COLORS['info'])
        color.setAlpha(150)
        painter.setPen(QPen(color, 0.08))
        painter.setBrush(QBrush(color))
        painter.drawEllipse(
            pg.QtCore.QPointF(landmark.col, landmark.row),
            0.3, 0.3
        )
