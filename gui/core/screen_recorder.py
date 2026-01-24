"""
================================================================================
Screen Recorder - Video Capture
================================================================================

This module provides screen recording capability for capturing GUI sessions
as video files. Useful for reviewing technique or training documentation.

Design Philosophy:
    "Stay hungry, stay foolish." - Steve Jobs

Recording provides valuable feedback for learning and review.
The implementation captures frames efficiently to minimize impact
on the main application's performance.

Dependencies:
    - opencv-python (cv2): Video encoding
    - mss: Fast screen capture
    - Pillow: Image processing

Note:
    These dependencies are optional. The module gracefully handles
    their absence and provides a flag to check availability.
"""

import time
from typing import Optional

import numpy as np
from PyQt6.QtCore import QThread, pyqtSignal

try:
    from ..utils.constants import RECORDING_FPS
except ImportError:
    from utils.constants import RECORDING_FPS

# Optional imports - recording may not be available
try:
    import cv2
    import mss
    from PIL import Image
    RECORDING_AVAILABLE = True
except ImportError:
    cv2 = None
    mss = None
    Image = None
    RECORDING_AVAILABLE = False


class ScreenRecorder(QThread):
    """
    Background thread for screen recording.

    Captures the specified screen region at the configured frame rate
    and saves to an MP4 video file.

    Signals:
        recording_complete: Emitted with file path when recording finishes
        error_occurred: Emitted with error message on failure

    Example:
        >>> if RECORDING_AVAILABLE:
        ...     region = {'left': 0, 'top': 0, 'width': 800, 'height': 600}
        ...     recorder = ScreenRecorder('output.mp4', region)
        ...     recorder.start()
        ...     # Later...
        ...     recorder.stop()
    """

    # Signals for thread-safe communication
    recording_complete = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, output_path: str, region: dict, fps: int = RECORDING_FPS):
        """
        Initialize the screen recorder.

        Args:
            output_path: Path for the output MP4 file
            region: Screen region dict with 'left', 'top', 'width', 'height'
            fps: Target frame rate (default 25)
        """
        super().__init__()
        self.output_path = output_path
        self.region = region
        self.fps = fps
        self.running = False
        self.frames: list = []

    def run(self) -> None:
        """
        Main recording loop - capture frames until stopped.

        Frames are stored in memory during recording, then encoded
        to video when stop() is called. This approach ensures
        consistent frame timing.
        """
        if not RECORDING_AVAILABLE:
            self.error_occurred.emit("Recording libraries not available")
            return

        try:
            self._capture_loop()
            self._encode_video()
        except Exception as e:
            self.error_occurred.emit(str(e))

    def _capture_loop(self) -> None:
        """Capture frames from the screen at the target frame rate."""
        self.running = True
        sct = mss.mss()

        # Calculate frame interval
        frame_interval = 1.0 / self.fps

        while self.running:
            frame_start = time.time()

            # Capture screenshot
            screenshot = sct.grab(self.region)
            frame = np.array(screenshot)

            # Convert BGRA to BGR for OpenCV
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            self.frames.append(frame)

            # Maintain frame rate
            elapsed = time.time() - frame_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    def _encode_video(self) -> None:
        """Encode captured frames to MP4 video."""
        if not self.frames:
            return

        # Get dimensions from first frame
        height, width = self.frames[0].shape[:2]

        # Initialize video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(self.output_path, fourcc, self.fps, (width, height))

        # Write all frames
        for frame in self.frames:
            out.write(frame)

        out.release()
        self.recording_complete.emit(self.output_path)

    def stop(self) -> None:
        """
        Stop recording and save the video.

        This method signals the capture loop to stop and waits for
        the video encoding to complete.
        """
        self.running = False
        self.wait(2000)  # Wait up to 2 seconds for encoding

    def get_frame_count(self) -> int:
        """
        Get the current number of captured frames.

        Returns:
            Number of frames captured so far
        """
        return len(self.frames)

    def get_duration(self) -> float:
        """
        Get the estimated recording duration.

        Returns:
            Duration in seconds based on frame count and fps
        """
        return len(self.frames) / self.fps if self.fps > 0 else 0.0
