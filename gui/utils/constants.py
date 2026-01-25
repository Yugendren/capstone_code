"""
================================================================================
Constants - Application-Wide Configuration Values
================================================================================

This module defines all constants used throughout the physiotherapy training
system. Centralizing these values ensures consistency and simplifies
configuration changes.

Design Philosophy:
    "The details are not the details. They make the design." - Charles Eames

    Every constant here has been carefully chosen to provide the optimal
    user experience while maintaining reliability.
"""

# =============================================================================
# Grid Hardware Configuration
# =============================================================================

# Physical sensor grid dimensions
# The 20x12 grid provides optimal resolution for lumbar spine detection
GRID_ROWS: int = 12
GRID_COLS: int = 20
GRID_TOTAL: int = GRID_ROWS * GRID_COLS  # 240 sensors

# =============================================================================
# Binary Serial Protocol
# =============================================================================

# Synchronization bytes mark the start of each data packet
# Using 0xAA (170) and 0x55 (85) provides a reliable sync pattern
SYNC_BYTE_1: int = 0xAA
SYNC_BYTE_2: int = 0x55

# Packet structure sizes (in bytes)
HEADER_SIZE: int = 2                        # Two sync bytes
PAYLOAD_SIZE: int = GRID_TOTAL * 2          # 16-bit value per sensor
FOOTER_SIZE: int = 4                        # Checksum + padding
PACKET_SIZE: int = HEADER_SIZE + PAYLOAD_SIZE + FOOTER_SIZE

# =============================================================================
# Display and Visualization
# =============================================================================

# Number of data points shown in the waveform history
# 200 points at ~25fps gives approximately 8 seconds of visible history
WAVEFORM_HISTORY_SIZE: int = 200

# =============================================================================
# Recording Configuration
# =============================================================================

# Countdown before recording starts (in seconds)
# 2 seconds gives the user time to prepare without excessive waiting
COUNTDOWN_SECONDS: int = 2

# Video capture frame rate
# 25fps provides smooth playback while keeping file sizes reasonable
RECORDING_FPS: int = 25

# =============================================================================
# ADC (Analog-to-Digital Converter) Range
# =============================================================================

# ADS1220 provides 24-bit resolution, scaled to 16-bit for transmission
# Firmware performs right-shift by 8 bits: 24-bit -> 16-bit
ADC_MIN: int = 0
ADC_MAX: int = 65535  # 2^16 - 1 (16-bit range from scaled ADS1220 values)
