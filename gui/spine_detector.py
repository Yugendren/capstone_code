"""
================================================================================
Spinal Landmark Detection Module
================================================================================

Detects and tracks L1-L5 vertebrae for physiotherapy training.

Features:
- Spine-line detection from drag calibration gesture
- Automatic L1-L5 segmentation (equal spacing)
- Transverse process estimation (left/right)
- Kalman filter for position refinement
- Palpation feedback zones

Author: Capstone Project
Date: 2026-01-12
================================================================================
"""

import numpy as np
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from collections import deque
import json
from datetime import datetime


# ============================================================================
# Pressure Zones (Velostat-Realistic, 0-15N Range)
# ============================================================================

@dataclass
class PalpationZones:
    """
    ADC thresholds for palpation feedback.
    Based on velostat's 0-15N effective range.
    
    These are STUB values - adjust based on actual sensor calibration.
    """
    MIN_CONTACT: int = 100       # ~0.5N - finger touching
    LIGHT_TOUCH: int = 500       # ~2N - light palpation
    OPTIMAL_MIN: int = 800       # ~3N - good palpation start
    OPTIMAL_MAX: int = 2000      # ~8N - firm palpation
    TOO_HARD: int = 2800         # ~12N - approaching saturation
    SATURATION: int = 3500       # Sensor saturating
    
    @staticmethod
    def get_zone(value: int) -> Tuple[str, str, str]:
        """
        Get zone info for a pressure value.
        
        Returns: (zone_name, color_hex, feedback_message)
        """
        if value < PalpationZones.MIN_CONTACT:
            return ("no_contact", "#666666", "No contact detected")
        elif value < PalpationZones.LIGHT_TOUCH:
            return ("light", "#f9e2af", "Too light - increase pressure")
        elif value < PalpationZones.OPTIMAL_MIN:
            return ("warming", "#fab387", "Getting there - press a bit harder")
        elif value <= PalpationZones.OPTIMAL_MAX:
            return ("optimal", "#a6e3a1", "✓ Good palpation pressure!")
        elif value <= PalpationZones.TOO_HARD:
            return ("firm", "#fab387", "Very firm contact")
        else:
            return ("excessive", "#f38ba8", "⚠ Too hard - reduce pressure")


@dataclass
class SpeedZones:
    """
    Movement speed thresholds (cells per second).
    For scanning/palpation movements, not thrusts.
    """
    STATIONARY: float = 1.0      # Not moving
    SLOW: float = 3.0            # Too slow
    OPTIMAL_MIN: float = 5.0     # Good scanning speed start
    OPTIMAL_MAX: float = 12.0    # Good scanning speed end
    FAST: float = 18.0           # Too fast
    
    @staticmethod
    def get_zone(speed: float) -> Tuple[str, str, str]:
        """Get zone info for movement speed."""
        if speed < SpeedZones.STATIONARY:
            return ("stationary", "#666666", "Hand stationary")
        elif speed < SpeedZones.SLOW:
            return ("slow", "#f9e2af", "Too slow - move more steadily")
        elif speed <= SpeedZones.OPTIMAL_MAX:
            return ("optimal", "#a6e3a1", "✓ Good scanning speed")
        elif speed <= SpeedZones.FAST:
            return ("fast", "#fab387", "Quite fast")
        else:
            return ("too_fast", "#f38ba8", "⚠ Too fast - slow down")


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class SpinalLandmark:
    """A single vertebra landmark."""
    level: str              # "L1", "L2", etc.
    landmark_type: str      # "spinous", "transverse_left", "transverse_right"
    row: float              # Grid row position (0-39)
    col: float              # Grid column position (0-39)
    uncertainty: float = 2.0  # Position uncertainty in cells
    
    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "type": self.landmark_type,
            "row": self.row,
            "col": self.col,
            "uncertainty": self.uncertainty
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> 'SpinalLandmark':
        return cls(
            level=d["level"],
            landmark_type=d["type"],
            row=d["row"],
            col=d["col"],
            uncertainty=d.get("uncertainty", 2.0)
        )


@dataclass
class SpineLine:
    """
    Detected spine midline from calibration drag.
    Represented as a polynomial fit through detected points.
    """
    start_row: int          # Top of spine region
    end_row: int            # Bottom of spine region
    coefficients: Tuple[float, float]  # (slope, intercept) for line
    
    def get_col_at_row(self, row: int) -> float:
        """Get column position at given row using polynomial."""
        return self.coefficients[0] * row + self.coefficients[1]
    
    def get_landmarks(self, lateral_offset: int = 6) -> List[SpinalLandmark]:
        """
        Generate all 15 landmarks (5 spinous + 10 transverse).
        
        Args:
            lateral_offset: Cells to left/right for transverse processes
                           Default 6 cells = ~30mm at 5mm/cell
        Returns:
            List of 15 SpinalLandmark objects
        """
        landmarks = []
        total_rows = self.end_row - self.start_row
        
        for i, level in enumerate(['L1', 'L2', 'L3', 'L4', 'L5']):
            # Position: divide into 5 segments, place at center of each
            # L1 at 10%, L2 at 30%, L3 at 50%, L4 at 70%, L5 at 90%
            row = self.start_row + int(total_rows * (0.1 + i * 0.2))
            col = self.get_col_at_row(row)
            
            # Spinous process (midline)
            landmarks.append(SpinalLandmark(
                level=level,
                landmark_type='spinous',
                row=row,
                col=col
            ))
            
            # Transverse process - left
            landmarks.append(SpinalLandmark(
                level=level,
                landmark_type='transverse_left',
                row=row,
                col=col - lateral_offset
            ))
            
            # Transverse process - right
            landmarks.append(SpinalLandmark(
                level=level,
                landmark_type='transverse_right',
                row=row,
                col=col + lateral_offset
            ))
        
        return landmarks
    
    def to_dict(self) -> dict:
        return {
            "start_row": self.start_row,
            "end_row": self.end_row,
            "coefficients": list(self.coefficients)
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> 'SpineLine':
        return cls(
            start_row=d["start_row"],
            end_row=d["end_row"],
            coefficients=tuple(d["coefficients"])
        )


@dataclass
class SpineCalibration:
    """Complete calibration data for a session."""
    spine_line: Optional[SpineLine] = None
    landmarks: List[SpinalLandmark] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: str = ""
    
    @property
    def is_calibrated(self) -> bool:
        return self.spine_line is not None and len(self.landmarks) == 15
    
    def to_json(self) -> str:
        return json.dumps({
            "spine_line": self.spine_line.to_dict() if self.spine_line else None,
            "landmarks": [lm.to_dict() for lm in self.landmarks],
            "created_at": self.created_at,
            "notes": self.notes
        }, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'SpineCalibration':
        d = json.loads(json_str)
        return cls(
            spine_line=SpineLine.from_dict(d["spine_line"]) if d["spine_line"] else None,
            landmarks=[SpinalLandmark.from_dict(lm) for lm in d["landmarks"]],
            created_at=d.get("created_at", ""),
            notes=d.get("notes", "")
        )


# ============================================================================
# Spine Detector
# ============================================================================

class SpineDetector:
    """
    Main class for detecting spine line and landmarks.
    
    Usage:
        detector = SpineDetector()
        
        # During calibration drag:
        for frame in pressure_frames:
            detector.add_calibration_frame(frame)
        
        # Finalize calibration:
        success = detector.finalize_calibration()
        
        # Access landmarks:
        if detector.calibration.is_calibrated:
            for landmark in detector.calibration.landmarks:
                print(f"{landmark.level}: ({landmark.row}, {landmark.col})")
    """
    
    # Calibration parameters
    MIN_CALIBRATION_FRAMES = 20
    MIN_CALIBRATION_PRESSURE = 300  # ADC threshold for valid press
    MIN_SPINE_LENGTH_ROWS = 15      # Minimum rows detected
    
    def __init__(self):
        self.calibration = SpineCalibration()
        self._calibration_frames: List[np.ndarray] = []
        self._is_calibrating = False
        
        # Kalman filters for each landmark (initialized after calibration)
        self._kalman_filters: dict = {}
    
    def start_calibration(self):
        """Begin calibration mode."""
        self._calibration_frames = []
        self._is_calibrating = True
        self.calibration = SpineCalibration()
    
    def add_calibration_frame(self, frame: np.ndarray):
        """
        Add a pressure frame during calibration drag.
        Call this for each frame while user drags finger along spine.
        """
        if self._is_calibrating:
            self._calibration_frames.append(frame.copy())
    
    def finalize_calibration(self) -> Tuple[bool, str]:
        """
        Finalize calibration and detect spine line.
        
        Returns:
            (success, message)
        """
        self._is_calibrating = False
        
        if len(self._calibration_frames) < self.MIN_CALIBRATION_FRAMES:
            return (False, f"Not enough frames ({len(self._calibration_frames)} < {self.MIN_CALIBRATION_FRAMES})")
        
        # Detect spine line from pressure trail
        spine_line = self._detect_spine_line()
        
        if spine_line is None:
            return (False, "Could not detect spine line - try again with more pressure")
        
        if (spine_line.end_row - spine_line.start_row) < self.MIN_SPINE_LENGTH_ROWS:
            return (False, "Spine line too short - drag from top to bottom")
        
        # Generate landmarks
        self.calibration.spine_line = spine_line
        self.calibration.landmarks = spine_line.get_landmarks()
        self.calibration.created_at = datetime.now().isoformat()
        
        # Initialize Kalman filters for each landmark
        self._init_kalman_filters()
        
        return (True, f"Calibration complete! Detected L1-L5 across rows {spine_line.start_row}-{spine_line.end_row}")
    
    def _detect_spine_line(self) -> Optional[SpineLine]:
        """
        Detect spine midline from pressure trail in calibration frames.
        
        Algorithm:
        1. For each row, find weighted centroid of pressure
        2. Collect points with significant pressure
        3. Fit line through points using least squares
        """
        # Combine all frames - take maximum at each cell
        combined = np.zeros_like(self._calibration_frames[0], dtype=float)
        for frame in self._calibration_frames:
            combined = np.maximum(combined, frame)
        
        # For each row, find column centroid weighted by pressure
        trail_points = []
        for row in range(combined.shape[0]):
            row_values = combined[row, :]
            
            if np.max(row_values) > self.MIN_CALIBRATION_PRESSURE:
                # Weighted centroid
                total_weight = np.sum(row_values)
                if total_weight > 0:
                    col_centroid = np.sum(np.arange(len(row_values)) * row_values) / total_weight
                    trail_points.append((row, col_centroid))
        
        if len(trail_points) < 10:
            return None
        
        # Extract arrays
        rows = np.array([p[0] for p in trail_points])
        cols = np.array([p[1] for p in trail_points])
        
        # Fit line: col = slope * row + intercept
        coefficients = np.polyfit(rows, cols, deg=1)
        
        return SpineLine(
            start_row=int(np.min(rows)),
            end_row=int(np.max(rows)),
            coefficients=(float(coefficients[0]), float(coefficients[1]))
        )
    
    def _init_kalman_filters(self):
        """Initialize Kalman filter for each landmark."""
        self._kalman_filters = {}
        for lm in self.calibration.landmarks:
            key = f"{lm.level}_{lm.landmark_type}"
            self._kalman_filters[key] = LandmarkKalman(
                initial_pos=(lm.row, lm.col),
                initial_uncertainty=lm.uncertainty
            )
    
    def update_landmark_estimate(self, level: str, landmark_type: str, 
                                  measured_row: float, measured_col: float):
        """
        Update a landmark's position estimate using Kalman filter.
        Call this when user presses near a known landmark.
        """
        key = f"{level}_{landmark_type}"
        if key in self._kalman_filters:
            kf = self._kalman_filters[key]
            new_pos, uncertainty = kf.update(np.array([measured_row, measured_col]))
            
            # Update landmark in calibration
            for lm in self.calibration.landmarks:
                if lm.level == level and lm.landmark_type == landmark_type:
                    lm.row = new_pos[0]
                    lm.col = new_pos[1]
                    lm.uncertainty = (uncertainty[0] + uncertainty[1]) / 2
                    break
    
    def find_nearest_landmark(self, row: float, col: float) -> Tuple[Optional[SpinalLandmark], float]:
        """
        Find the landmark nearest to a position.
        
        Returns:
            (landmark, distance) or (None, inf) if not calibrated
        """
        if not self.calibration.is_calibrated:
            return (None, float('inf'))
        
        nearest = None
        min_dist = float('inf')
        
        for lm in self.calibration.landmarks:
            dist = np.sqrt((lm.row - row)**2 + (lm.col - col)**2)
            if dist < min_dist:
                min_dist = dist
                nearest = lm
        
        return (nearest, min_dist)
    
    def get_technique_feedback(self, row: float, col: float, pressure: int) -> dict:
        """
        Get comprehensive feedback for a press location/pressure.
        
        Returns dict with:
            - nearest_landmark: SpinalLandmark or None
            - distance_to_landmark: float (cells)
            - on_target: bool (within 3 cells)
            - pressure_zone: Tuple from PalpationZones
            - feedback: str (human-readable)
        """
        landmark, distance = self.find_nearest_landmark(row, col)
        pressure_zone = PalpationZones.get_zone(pressure)
        on_target = distance <= 3.0
        
        if landmark is None:
            feedback = "No calibration - please calibrate first"
        elif on_target:
            feedback = f"✓ On target: {landmark.level} ({landmark.landmark_type})"
        else:
            # Calculate direction
            dr = landmark.row - row
            dc = landmark.col - col
            
            directions = []
            if abs(dr) > 1:
                directions.append("up" if dr < 0 else "down")
            if abs(dc) > 1:
                directions.append("left" if dc < 0 else "right")
            
            direction_str = " and ".join(directions) if directions else ""
            feedback = f"Move {direction_str} toward {landmark.level}"
        
        return {
            "nearest_landmark": landmark,
            "distance_to_landmark": distance,
            "on_target": on_target,
            "pressure_zone": pressure_zone,
            "feedback": feedback
        }
    
    def save_calibration(self, filepath: str):
        """Save calibration to JSON file."""
        with open(filepath, 'w') as f:
            f.write(self.calibration.to_json())
    
    def load_calibration(self, filepath: str) -> bool:
        """Load calibration from JSON file."""
        try:
            with open(filepath, 'r') as f:
                self.calibration = SpineCalibration.from_json(f.read())
            if self.calibration.is_calibrated:
                self._init_kalman_filters()
            return True
        except Exception as e:
            print(f"Error loading calibration: {e}")
            return False


# ============================================================================
# Kalman Filter for Landmark Position
# ============================================================================

class LandmarkKalman:
    """
    Simple 2D Kalman filter for landmark position estimation.
    
    State: [row, col]
    Observation: [row, col] from new press
    """
    
    def __init__(self, initial_pos: Tuple[float, float], 
                 initial_uncertainty: float = 5.0):
        """
        Initialize filter.
        
        Args:
            initial_pos: (row, col) initial position
            initial_uncertainty: Initial position uncertainty in cells
        """
        self.x = np.array(initial_pos, dtype=float)
        self.P = np.eye(2) * initial_uncertainty**2  # Covariance
        
        # Process noise - landmarks are static, so very small
        self.Q = np.eye(2) * 0.01
        
        # Measurement noise - depends on sensor accuracy
        self.R = np.eye(2) * 2.0
        
        # Count of updates
        self.update_count = 0
    
    def predict(self):
        """Prediction step - for stationary landmarks, just adds process noise."""
        self.P = self.P + self.Q
    
    def update(self, measurement: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Update step with new observation.
        
        Args:
            measurement: [row, col] observed position
            
        Returns:
            (new_position, uncertainty_stddev)
        """
        self.predict()
        
        # Adaptive R: reduce measurement noise as we get more updates
        adaptive_R = self.R * max(0.5, 0.95 ** self.update_count)
        
        # Kalman gain
        S = self.P + adaptive_R
        K = self.P @ np.linalg.inv(S)
        
        # Innovation
        y = measurement - self.x
        
        # Update state
        self.x = self.x + K @ y
        
        # Update covariance
        self.P = (np.eye(2) - K) @ self.P
        
        self.update_count += 1
        
        return self.x.copy(), np.sqrt(np.diag(self.P))


# ============================================================================
# Pressure/Speed Tracker
# ============================================================================

class MovementTracker:
    """
    Tracks pressure centroid movement for speed calculation.
    """
    
    def __init__(self, history_size: int = 10):
        self.history_size = history_size
        self._positions = deque(maxlen=history_size)
        self._timestamps = deque(maxlen=history_size)
    
    def update(self, frame: np.ndarray, timestamp: float) -> Tuple[Optional[Tuple[float, float]], float]:
        """
        Update with new frame.
        
        Args:
            frame: Pressure grid data
            timestamp: Time in seconds
            
        Returns:
            (centroid_position, speed_cells_per_second)
        """
        # Find centroid of pressure
        total = np.sum(frame)
        if total < 100:  # No significant pressure
            return (None, 0.0)
        
        # Weighted centroid
        rows, cols = np.indices(frame.shape)
        row_centroid = np.sum(rows * frame) / total
        col_centroid = np.sum(cols * frame) / total
        
        pos = (row_centroid, col_centroid)
        
        self._positions.append(pos)
        self._timestamps.append(timestamp)
        
        # Calculate speed
        if len(self._positions) >= 2:
            p1 = self._positions[0]
            p2 = self._positions[-1]
            t1 = self._timestamps[0]
            t2 = self._timestamps[-1]
            
            dt = t2 - t1
            if dt > 0.01:
                distance = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
                speed = distance / dt
                return (pos, speed)
        
        return (pos, 0.0)
    
    def get_speed_feedback(self) -> Tuple[str, str, str]:
        """Get current speed zone feedback."""
        if len(self._positions) < 2:
            return SpeedZones.get_zone(0)
        
        p1 = self._positions[-2]
        p2 = self._positions[-1]
        t1 = self._timestamps[-2]
        t2 = self._timestamps[-1]
        
        dt = t2 - t1
        if dt > 0.001:
            distance = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
            speed = distance / dt
            return SpeedZones.get_zone(speed)
        
        return SpeedZones.get_zone(0)
