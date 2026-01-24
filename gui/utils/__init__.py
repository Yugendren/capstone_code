"""
================================================================================
Utils Package - Core Constants and Utilities
================================================================================

This package contains fundamental constants and utility functions used
throughout the application. Keeping these centralized ensures consistency
and makes the codebase easier to maintain.

Modules:
    constants: Grid dimensions, protocol specs, and timing constants
"""

try:
    from .constants import (
        # Grid dimensions
        GRID_ROWS,
        GRID_COLS,
        GRID_TOTAL,
        # Binary protocol
        SYNC_BYTE_1,
        SYNC_BYTE_2,
        HEADER_SIZE,
        PAYLOAD_SIZE,
        FOOTER_SIZE,
        PACKET_SIZE,
        # Display settings
        WAVEFORM_HISTORY_SIZE,
        COUNTDOWN_SECONDS,
        RECORDING_FPS,
        ADC_MIN,
        ADC_MAX,
    )
except ImportError:
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

__all__ = [
    'GRID_ROWS',
    'GRID_COLS',
    'GRID_TOTAL',
    'SYNC_BYTE_1',
    'SYNC_BYTE_2',
    'HEADER_SIZE',
    'PAYLOAD_SIZE',
    'FOOTER_SIZE',
    'PACKET_SIZE',
    'WAVEFORM_HISTORY_SIZE',
    'COUNTDOWN_SECONDS',
    'RECORDING_FPS',
    'ADC_MIN',
    'ADC_MAX',
]
