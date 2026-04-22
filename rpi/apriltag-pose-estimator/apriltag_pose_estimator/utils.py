"""
Utility functions for angle handling, rotation conversions, and serialization.
"""

import math
from typing import Dict, Tuple

import numpy as np


def normalize_angle(angle_rad: float) -> float:
    """
    Normalize angle to [-π, π] range.

    Args:
        angle_rad: Angle in radians.

    Returns:
        Normalized angle in [-π, π].
    """
    while angle_rad > math.pi:
        angle_rad -= 2 * math.pi
    while angle_rad < -math.pi:
        angle_rad += 2 * math.pi
    return angle_rad


def yaw_from_rotation_matrix(R: np.ndarray) -> float:
    """
    Extract 2D yaw rotation from a 3×3 rotation matrix.

    For a rotation matrix representing rotation around Z-axis (yaw),
    the yaw angle θ is: atan2(R[1,0], R[0,0])

    Args:
        R: 3×3 rotation matrix (from cv2.Rodrigues or similar).

    Returns:
        Yaw angle in radians, normalized to [-π, π].

    Raises:
        ValueError: If input is not a 3×3 matrix.
    """
    if R.shape != (3, 3):
        raise ValueError(f"Expected 3×3 rotation matrix, got {R.shape}")

    # Extract yaw from rotation matrix (Z-axis rotation)
    yaw = math.atan2(R[1, 0], R[0, 0])
    return normalize_angle(yaw)


def angle_distance(angle1_rad: float, angle2_rad: float) -> float:
    """
    Compute circular distance between two angles.

    Args:
        angle1_rad: First angle in radians.
        angle2_rad: Second angle in radians.

    Returns:
        Circular distance in radians, in [0, π].
    """
    diff = normalize_angle(angle1_rad - angle2_rad)
    return abs(diff)


def circular_mean_angles(angles: np.ndarray, weights: np.ndarray = None) -> float:
    """
    Compute weighted circular mean of angles.

    Converts angles to unit circle (sin, cos), computes weighted mean,
    then converts back to angle.

    Args:
        angles: 1D array of angles in radians.
        weights: Optional 1D array of weights (normalized internally).
                 If None, uniform weights are used.

    Returns:
        Circular mean angle in radians, normalized to [-π, π].
    """
    if len(angles) == 0:
        raise ValueError("Cannot compute mean of empty angle array")

    if weights is None:
        weights = np.ones(len(angles))

    # Normalize weights
    weights = np.asarray(weights, dtype=float)
    weights = weights / np.sum(weights)

    # Convert to unit circle and compute weighted mean
    sin_weighted = np.sum(weights * np.sin(angles))
    cos_weighted = np.sum(weights * np.cos(angles))

    # Convert back to angle
    mean_angle = math.atan2(sin_weighted, cos_weighted)
    return normalize_angle(mean_angle)


def pose_to_dict(x: float, y: float, yaw: float, confidence: float) -> Dict[str, float]:
    """
    Serialize pose components to a dictionary.

    Args:
        x: X position in meters.
        y: Y position in meters.
        yaw: Yaw rotation in radians.
        confidence: Confidence score in [0, 1].

    Returns:
        Dictionary with keys: 'x', 'y', 'yaw', 'confidence'.
    """
    return {
        "x": float(x),
        "y": float(y),
        "yaw": float(normalize_angle(yaw)),
        "confidence": float(confidence),
    }


def tvec_to_2d_position(
    tvec: np.ndarray, rotation_matrix: np.ndarray
) -> Tuple[float, float]:
    """
    Extract 2D (x, y) position from translation vector in camera frame.

    For tags on walls with a forward-facing camera:
    - Camera +X: right
    - Camera +Y: down
    - Camera +Z: forward (depth)

    Returns the position of the tag relative to camera, projected onto
    a 2D horizontal plane.

    Args:
        tvec: 3×1 translation vector from cv2.solvePnP (camera frame).
        rotation_matrix: 3×3 rotation matrix of tag relative to camera.

    Returns:
        (dx, dy) position of tag relative to camera in camera's XY plane.
    """
    # tvec is [tx, ty, tz] in camera frame
    # For 2D position on floor, use X and Z components
    # (assuming Y is up/down in camera view)
    x = tvec[0, 0]  # Right/left in camera frame
    z = tvec[2, 0]  # Depth in camera frame

    return float(x), float(z)


def rotation_matrix_from_rodrigues(rvec: np.ndarray) -> np.ndarray:
    """
    Convert Rodrigues rotation vector to 3×3 rotation matrix.

    Args:
        rvec: 3×1 or 1×3 Rodrigues rotation vector.

    Returns:
        3×3 rotation matrix.
    """
    R, _ = cv2.Rodrigues(rvec)
    return R


# Note: Import cv2 only when needed to avoid hard dependency during import
def _get_cv2():
    """Lazy import cv2."""
    try:
        import cv2
        return cv2
    except ImportError:
        raise ImportError("opencv-python is required for rotation conversions")


cv2 = _get_cv2() if __name__ != "__main__" else None
