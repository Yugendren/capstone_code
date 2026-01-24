#!/usr/bin/env python3
"""
================================================================================
20x12 Piezoelectric Force Sensing Grid - Main Entry Point
================================================================================

Physiotherapy Training System - Super user-friendly interface with smooth
animations and clear layout.

This file serves as the backward-compatible entry point. The implementation
has been refactored into modular packages for better organization:

    gui/
    ├── core/         - Business logic (serial, analysis, recording)
    ├── dialogs/      - Modal dialog windows
    ├── styles/       - Visual design system (colors, fonts)
    ├── utils/        - Constants and utilities
    └── widgets/      - Custom UI components

Usage:
    cd gui && python grid_gui.py

Or from project root:
    python -m gui.app

Design Philosophy:
    "Simplicity is the ultimate sophistication." - Leonardo da Vinci
    "Design is not just what it looks like. Design is how it works." - Steve Jobs

Author: Capstone Project
Date: 2026-01-24
================================================================================
"""

import sys
import os

# Add the gui directory to path for local imports when running directly
if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

# =============================================================================
# Re-export everything for backward compatibility
# =============================================================================

# Constants
from utils.constants import (
    GRID_ROWS,
    GRID_COLS,
    GRID_TOTAL,
    SYNC_BYTE_1,
    SYNC_BYTE_2,
    HEADER_SIZE,
    PAYLOAD_SIZE,
    FOOTER_SIZE,
    PACKET_SIZE,
    WAVEFORM_HISTORY_SIZE,
    COUNTDOWN_SECONDS,
    RECORDING_FPS,
    ADC_MIN,
    ADC_MAX,
)

# Styles
from styles.theme import (
    COLORS,
    HEATMAP_COLORS,
    FONT_FAMILY,
)

# Widgets
from widgets import (
    AnimatedButton,
    FriendlyCard,
    StatDisplay,
    PulsingDot,
    ColorLegendWidget,
    LandmarkOverlay,
    DriftWarningWidget,
)

# Core components
from core import (
    SerialReader,
    FrequencyAnalyzer,
    ScreenRecorder,
    RECORDING_AVAILABLE,
)

# Dialogs
from dialogs import CalibrationDialog

# Main window
from main_window import GridVisualizerWindow


def main() -> int:
    """
    Launch the physiotherapy training application.

    Returns:
        Exit code (0 for success)

    Example:
        >>> import sys
        >>> sys.exit(main())
    """
    # Create application
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    # Set global font
    app.setFont(QFont("Comic Sans MS", 10))

    # Create and show main window
    window = GridVisualizerWindow()
    window.show()

    # Run event loop
    return app.exec()


# =============================================================================
# Direct execution entry point
# =============================================================================

if __name__ == '__main__':
    sys.exit(main())
