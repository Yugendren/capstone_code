"""
================================================================================
Serial Reader - Hardware Communication
================================================================================

This module handles communication with the STM32 microcontroller via
serial port. It reads binary packets containing the 20x12 pressure grid data.

Design Philosophy:
    "Real artists ship." - Steve Jobs

This module is the critical link between hardware and software. It must
be rock-solid, handling timing variations, packet corruption, and
connection issues gracefully.

Binary Protocol:
    [0xAA][0x55][480 bytes payload][2 bytes checksum][2 bytes padding]

    - Sync bytes: 0xAA 0x55 mark packet start
    - Payload: 240 x 16-bit values (little-endian)
    - Checksum: Sum of payload bytes & 0xFFFF
"""

import struct
import time
from typing import Optional

import numpy as np
import serial
from PyQt6.QtCore import QThread, pyqtSignal

try:
    from ..utils.constants import (
        GRID_ROWS, GRID_COLS, GRID_TOTAL,
        SYNC_BYTE_1, SYNC_BYTE_2,
        HEADER_SIZE, PAYLOAD_SIZE, PACKET_SIZE
    )
except ImportError:
    from utils.constants import (
        GRID_ROWS, GRID_COLS, GRID_TOTAL,
        SYNC_BYTE_1, SYNC_BYTE_2,
        HEADER_SIZE, PAYLOAD_SIZE, PACKET_SIZE
    )


class SerialReader(QThread):
    """
    Background thread for reading serial data from the sensor grid.

    This thread continuously reads from the serial port, parses binary
    packets, validates checksums, and emits the processed grid data.

    Signals:
        data_received: Emitted with numpy array when valid data is received
        error_occurred: Emitted with error message string on failure

    Example:
        >>> reader = SerialReader('/dev/ttyUSB0', 115200)
        >>> reader.data_received.connect(self.handle_data)
        >>> reader.error_occurred.connect(self.handle_error)
        >>> reader.start()
        >>> # Later...
        >>> reader.stop()
    """

    # Signals for thread-safe communication
    data_received = pyqtSignal(np.ndarray)
    error_occurred = pyqtSignal(str)

    def __init__(self, port: str, baudrate: int = 115200, grid_rows: int = None, grid_cols: int = None):
        """
        Initialize the serial reader.

        Args:
            port: Serial port path (e.g., '/dev/ttyUSB0', 'COM3')
            baudrate: Communication speed (default 115200)
            grid_rows: Number of rows in grid (uses config default if None)
            grid_cols: Number of columns in grid (uses config default if None)
        """
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.running = False
        self.serial: Optional[serial.Serial] = None

        # Use provided grid dimensions or fall back to constants
        self.grid_rows = grid_rows if grid_rows is not None else GRID_ROWS
        self.grid_cols = grid_cols if grid_cols is not None else GRID_COLS
        self.grid_total = self.grid_rows * self.grid_cols

        # Calculate packet sizes based on grid dimensions
        self.payload_size = self.grid_total * 2  # 2 bytes per cell (16-bit values)
        self.packet_size = HEADER_SIZE + self.payload_size + 4  # header + payload + footer

    def run(self) -> None:
        """
        Main thread loop - continuously read and parse serial data.

        This method runs in a separate thread and handles:
            1. Serial port connection
            2. Byte stream buffering
            3. Sync byte detection
            4. Packet parsing and validation
            5. Data emission via signals
        """
        try:
            self._connect()
            self._read_loop()
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            self._disconnect()

    def _connect(self) -> None:
        """Establish serial connection."""
        self.serial = serial.Serial(self.port, self.baudrate, timeout=1)
        self.running = True

    def _disconnect(self) -> None:
        """Close serial connection if open."""
        if self.serial and self.serial.is_open:
            self.serial.close()

    def _read_loop(self) -> None:
        """Main read loop - process incoming bytes."""
        buffer = bytearray()

        while self.running:
            # Read available bytes
            if self.serial.in_waiting:
                buffer.extend(self.serial.read(self.serial.in_waiting))

            # Process complete packets
            while len(buffer) >= self.packet_size:
                packet = self._extract_packet(buffer)
                if packet is None:
                    break  # Need more data

                buffer = buffer[len(packet):]  # Remove processed bytes

                # Parse and validate packet
                grid_data = self._parse_packet(packet)
                if grid_data is not None:
                    self.data_received.emit(grid_data)

            # Small sleep to prevent CPU spinning
            time.sleep(0.001)

    def _extract_packet(self, buffer: bytearray) -> Optional[bytearray]:
        """
        Find and extract a complete packet from the buffer.

        Args:
            buffer: The byte buffer to search

        Returns:
            The packet bytes if found, None otherwise
        """
        # Search for sync bytes
        sync_idx = self._find_sync(buffer)

        if sync_idx == -1:
            # No sync found, keep only last byte (might be start of sync)
            del buffer[:-1]
            return None

        if sync_idx > 0:
            # Discard bytes before sync
            del buffer[:sync_idx]

        if len(buffer) < self.packet_size:
            return None  # Incomplete packet

        return buffer[:self.packet_size]

    def _find_sync(self, buffer: bytearray) -> int:
        """
        Find sync byte sequence in buffer.

        Args:
            buffer: The byte buffer to search

        Returns:
            Index of sync sequence, or -1 if not found
        """
        for i in range(len(buffer) - 1):
            if buffer[i] == SYNC_BYTE_1 and buffer[i + 1] == SYNC_BYTE_2:
                return i
        return -1

    def _parse_packet(self, packet: bytearray) -> Optional[np.ndarray]:
        """
        Parse and validate a binary packet.

        Args:
            packet: Complete packet bytes

        Returns:
            Grid data as numpy array, or None if invalid
        """
        # Extract payload
        payload = packet[HEADER_SIZE:HEADER_SIZE + self.payload_size]

        # Validate checksum
        expected_checksum = struct.unpack('<H',
            packet[HEADER_SIZE + self.payload_size:HEADER_SIZE + self.payload_size + 2]
        )[0]
        actual_checksum = sum(payload) & 0xFFFF

        if expected_checksum != actual_checksum:
            return None  # Corrupted packet

        # Unpack sensor values (little-endian 16-bit unsigned)
        values = struct.unpack(f'<{self.grid_total}H', payload)

        # Reshape to grid
        grid_data = np.array(values, dtype=np.uint16).reshape(self.grid_rows, self.grid_cols)
        return grid_data

    def stop(self) -> None:
        """
        Stop the reader thread gracefully.

        This method signals the thread to stop and waits for it to finish.
        """
        self.running = False
        self.wait(1000)  # Wait up to 1 second for thread to finish
