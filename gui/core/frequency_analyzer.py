"""
================================================================================
Frequency Analyzer - Palpation Rate Detection
================================================================================

This module analyzes pressure patterns to detect palpation frequency,
helping users maintain consistent palpation technique.

Design Philosophy:
    "Innovation distinguishes between a leader and a follower." - Steve Jobs

The algorithm detects press/release cycles using threshold crossings,
providing real-time feedback on palpation rate in Hz.

Algorithm:
    1. Track maximum pressure over time
    2. Detect rising edge crossings (press events)
    3. Calculate frequency from press intervals
"""

from collections import deque
from typing import Dict


class FrequencyAnalyzer:
    """
    Analyzes palpation frequency from pressure data.

    The analyzer tracks pressure over time and detects palpation events
    (pressure crosses above threshold). Frequency is calculated from
    the time between events.

    Attributes:
        sample_rate: Expected data rate in Hz
        window_size: Number of samples for moving window
        threshold: Pressure threshold for detecting press events

    Example:
        >>> analyzer = FrequencyAnalyzer(sample_rate=25.0)
        >>> for frame in data_stream:
        ...     max_pressure = frame.max()
        ...     freq = analyzer.update(max_pressure, time.time())
        ...     print(f"Palpation rate: {freq:.1f} Hz")
    """

    def __init__(self, sample_rate: float = 25.0, window_size: int = 50):
        """
        Initialize the frequency analyzer.

        Args:
            sample_rate: Expected data rate in Hz (for reference)
            window_size: Number of samples to keep in history
        """
        self.sample_rate = sample_rate
        self.window_size = window_size

        # Rolling history of pressure values
        self.pressure_history = deque(maxlen=window_size)

        # Timestamps of detected press events
        self.press_times = deque(maxlen=20)

        # Threshold for detecting a "press" (above baseline noise)
        self.threshold = 200

        # State tracking for edge detection
        self.was_pressed = False

        # Last calculated frequency
        self.last_frequency = 0.0

    def update(self, max_pressure: int, timestamp: float) -> float:
        """
        Process a new pressure reading and update frequency estimate.

        Args:
            max_pressure: Maximum pressure value from the current frame
            timestamp: Current time in seconds

        Returns:
            Estimated palpation frequency in Hz
        """
        # Add to history
        self.pressure_history.append(max_pressure)

        # Detect state change (press event)
        is_pressed = max_pressure > self.threshold

        # Rising edge detection (transition from not pressed to pressed)
        if is_pressed and not self.was_pressed:
            self.press_times.append(timestamp)

        self.was_pressed = is_pressed

        # Calculate frequency from press intervals
        self._update_frequency()

        return self.last_frequency

    def _update_frequency(self) -> None:
        """Calculate frequency from recorded press times."""
        if len(self.press_times) >= 2:
            # Time span from first to last press
            time_span = self.press_times[-1] - self.press_times[0]

            if time_span > 0:
                # Frequency = (number of intervals) / time span
                # Number of intervals = number of presses - 1
                self.last_frequency = (len(self.press_times) - 1) / time_span

    def get_stats(self) -> Dict[str, float]:
        """
        Get current statistics from the pressure history.

        Returns:
            Dictionary with 'peak', 'trough', and 'frequency' values

        Example:
            >>> stats = analyzer.get_stats()
            >>> print(f"Peak: {stats['peak']}, Freq: {stats['frequency']:.1f} Hz")
        """
        if len(self.pressure_history) < 2:
            return {'peak': 0, 'trough': 0, 'frequency': 0.0}

        data = list(self.pressure_history)
        return {
            'peak': max(data),
            'trough': min(data),
            'frequency': self.last_frequency
        }

    def reset(self) -> None:
        """
        Reset the analyzer state.

        Call this when starting a new recording session or after
        significant time gaps in the data.
        """
        self.pressure_history.clear()
        self.press_times.clear()
        self.was_pressed = False
        self.last_frequency = 0.0

    def set_threshold(self, threshold: int) -> None:
        """
        Adjust the press detection threshold.

        Args:
            threshold: New threshold value (0-4095)

        Lower values detect lighter touches, higher values require
        firmer pressure to register as a press event.
        """
        self.threshold = threshold
