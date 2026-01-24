"""
================================================================================
Application Entry Point
================================================================================

This module provides the main entry point for the Physiotherapy Training System.

Usage:
    python -m gui.app

Or:
    from gui.app import main
    main()

Design Philosophy:
    "The people who are crazy enough to think they can change the world
     are the ones who do." - Steve Jobs
"""

import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont

try:
    from .main_window import GridVisualizerWindow
except ImportError:
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


if __name__ == '__main__':
    sys.exit(main())
