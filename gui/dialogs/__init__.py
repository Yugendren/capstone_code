"""
================================================================================
Dialogs Package - Modal Dialog Windows
================================================================================

This package contains modal dialog windows for specialized tasks
like calibration and configuration.

Design Philosophy:
    "Focus is about saying no." - Steve Jobs

Dialogs should have a single, clear purpose. They guide the user
through a specific task and then get out of the way.

Modules:
    calibration_dialog: Spine calibration workflow
"""

try:
    from .calibration_dialog import CalibrationDialog
except ImportError:
    from dialogs.calibration_dialog import CalibrationDialog

__all__ = [
    'CalibrationDialog',
]
