"""
================================================================================
Core Package - Business Logic and Data Processing
================================================================================

This package contains the core functionality of the application:
serial communication, data analysis, and recording capabilities.

Design Philosophy:
    "The people who are crazy enough to think they can change the world
     are the ones who do." - Steve Jobs

These modules handle the critical data pipeline that makes real-time
biofeedback possible. They're designed for reliability and efficiency.

Modules:
    serial_reader: Serial port communication with STM32
    frequency_analyzer: Palpation frequency detection
    screen_recorder: Video capture of the GUI
"""

try:
    from .serial_reader import SerialReader
    from .frequency_analyzer import FrequencyAnalyzer
    from .screen_recorder import ScreenRecorder, RECORDING_AVAILABLE
except ImportError:
    from core.serial_reader import SerialReader
    from core.frequency_analyzer import FrequencyAnalyzer
    from core.screen_recorder import ScreenRecorder, RECORDING_AVAILABLE

__all__ = [
    'SerialReader',
    'FrequencyAnalyzer',
    'ScreenRecorder',
    'RECORDING_AVAILABLE',
]
