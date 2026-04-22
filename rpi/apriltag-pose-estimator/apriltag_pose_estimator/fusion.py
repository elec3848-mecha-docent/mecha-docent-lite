"""
Multi-tag pose fusion: combining multiple tag detections into a single pose estimate.
"""

from dataclasses import dataclass
from typing import List

import numpy as np

from . import utils


@dataclass
class PoseEstimate:
    """
    A 2D pose estimate with confidence.

    Attributes:
        x (float): X position in meters.
        y (float): Y position in meters.
        yaw (float): Yaw rotation in radians (normalized to [-π, π]).
        confidence (float): Confidence score in [0, 1].
    """

    x: float
    y: float
    yaw: float
    confidence: float

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/serialization."""
        return utils.pose_to_dict(self.x, self.y, self.yaw, self.confidence)

    def __post_init__(self):
        """Normalize yaw on initialization."""
        self.yaw = utils.normalize_angle(self.yaw)
        # Clamp confidence to [0, 1]
        self.confidence = float(np.clip(self.confidence, 0.0, 1.0))

    def __repr__(self) -> str:
        return (
            f"PoseEstimate(x={self.x:.3f}, y={self.y:.3f}, "
            f"yaw={self.yaw:.3f}, conf={self.confidence:.3f})"
        )


def fuse_poses(poses: List[PoseEstimate]) -> PoseEstimate:
    """
    Fuse multiple pose estimates into a single estimate via weighted averaging.

    Uses detection confidence as weights. For angles (yaw), uses circular mean
    to handle wraparound correctly.

    Args:
        poses: List of PoseEstimate objects to fuse.

    Returns:
        Fused PoseEstimate.

    Raises:
        ValueError: If poses list is empty.
    """
    if not poses:
        raise ValueError("Cannot fuse empty list of poses")

    if len(poses) == 1:
        return poses[0]

    # Extract confidence weights
    confidences = np.array([p.confidence for p in poses])

    # Normalize weights
    weights = confidences / np.sum(confidences)

    # Weighted average for X, Y
    x_fused = float(np.average([p.x for p in poses], weights=weights))
    y_fused = float(np.average([p.y for p in poses], weights=weights))

    # Circular mean for yaw
    yaws = np.array([p.yaw for p in poses])
    yaw_fused = utils.circular_mean_angles(yaws, weights)

    # Fused confidence: use max confidence (most confident detection)
    # Alternative: could use average or other fusion strategy
    confidence_fused = float(np.max(confidences))

    return PoseEstimate(
        x=x_fused, y=y_fused, yaw=yaw_fused, confidence=confidence_fused
    )


def fuse_poses_with_median(poses: List[PoseEstimate]) -> PoseEstimate:
    """
    Alternative fusion using median instead of mean (more robust to outliers).

    Args:
        poses: List of PoseEstimate objects to fuse.

    Returns:
        Fused PoseEstimate using median.

    Raises:
        ValueError: If poses list is empty.
    """
    if not poses:
        raise ValueError("Cannot fuse empty list of poses")

    if len(poses) == 1:
        return poses[0]

    # Median for X, Y
    x_fused = float(np.median([p.x for p in poses]))
    y_fused = float(np.median([p.y for p in poses]))

    # For yaw, circular median is complex; use weighted mean by confidence
    confidences = np.array([p.confidence for p in poses])
    weights = confidences / np.sum(confidences)
    yaws = np.array([p.yaw for p in poses])
    yaw_fused = utils.circular_mean_angles(yaws, weights)

    # Use max confidence
    confidence_fused = float(np.max(confidences))

    return PoseEstimate(
        x=x_fused, y=y_fused, yaw=yaw_fused, confidence=confidence_fused
    )
