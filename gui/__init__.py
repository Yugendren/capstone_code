"""
================================================================================
GUI Package - Physiotherapy Training System
================================================================================

A super user-friendly interface for the 20x12 piezoelectric force sensing grid.
Designed with animations, clean layout, and the philosophy that simplicity
is the ultimate sophistication.

Package Structure:
    gui/
    ├── __init__.py          # This file - package entry point
    ├── app.py               # Application launcher
    ├── main_window.py       # Main application window
    ├── core/                # Business logic
    │   ├── serial_reader.py     # Hardware communication
    │   ├── frequency_analyzer.py # Palpation analysis
    │   └── screen_recorder.py   # Video capture
    ├── dialogs/             # Modal dialogs
    │   └── calibration_dialog.py
    ├── styles/              # Visual design system
    │   └── theme.py         # Colors, fonts, styles
    ├── utils/               # Constants and utilities
    │   └── constants.py     # Grid dimensions, protocol specs
    └── widgets/             # Custom UI components
        ├── animated_button.py   # Animated buttons
        ├── cards.py            # Container widgets
        ├── indicators.py       # Status indicators
        ├── overlays.py         # Heatmap overlays
        └── warnings.py         # Alert displays

Design Philosophy:
    "Simplicity is the ultimate sophistication." - Leonardo da Vinci
    "Design is not just what it looks like. Design is how it works." - Steve Jobs

The 3Rs:
    - Readability: Clear, documented code with consistent naming
    - Replicability: Modular components that can be reused
    - Reliability: Robust error handling and graceful degradation

Usage:
    # Launch the application
    python -m gui.app

    # Or import and run programmatically
    from gui import main
    main()

Author: Capstone Project
Date: 2026-01-24
"""

__version__ = "2.0.0"
__author__ = "Capstone Project"

try:
    from .app import main
    from .main_window import GridVisualizerWindow
except ImportError:
    from app import main
    from main_window import GridVisualizerWindow

__all__ = [
    'main',
    'GridVisualizerWindow',
]
