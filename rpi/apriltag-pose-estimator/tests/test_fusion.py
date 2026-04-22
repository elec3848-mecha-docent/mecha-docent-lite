"""
Unit tests for fusion module.
"""

import math

import numpy as np
import pytest

from apriltag_pose_estimator import (
    PoseEstimate,
    fuse_poses,
    fuse_poses_with_median,
)


class TestPoseEstimate:
    """Tests for PoseEstimate dataclass."""

    def test_creation(self):
        """Test creating PoseEstimate."""
        pose = PoseEstimate(x=1.0, y=2.0, yaw=0.5, confidence=0.95)
        assert pose.x == 1.0
        assert pose.y == 2.0
        assert pose.yaw == 0.5
        assert pose.confidence == 0.95

    def test_yaw_normalization(self):
        """Test that yaw is normalized on creation."""
        pose = PoseEstimate(x=0.0, y=0.0, yaw=10*math.pi, confidence=1.0)
        assert -math.pi <= pose.yaw <= math.pi

    def test_confidence_clamping(self):
        """Test that confidence is clamped to [0, 1]."""
        pose_low = PoseEstimate(x=0.0, y=0.0, yaw=0.0, confidence=-0.5)
        assert pose_low.confidence == 0.0
        
        pose_high = PoseEstimate(x=0.0, y=0.0, yaw=0.0, confidence=1.5)
        assert pose_high.confidence == 1.0

    def test_to_dict(self):
        """Test conversion to dictionary."""
        pose = PoseEstimate(x=1.5, y=2.5, yaw=0.3, confidence=0.8)
        pose_dict = pose.to_dict()
        
        assert "x" in pose_dict
        assert "y" in pose_dict
        assert "yaw" in pose_dict
        assert "confidence" in pose_dict
        assert pose_dict["x"] == 1.5

    def test_repr(self):
        """Test string representation."""
        pose = PoseEstimate(x=1.0, y=2.0, yaw=0.5, confidence=0.9)
        repr_str = repr(pose)
        assert "PoseEstimate" in repr_str
        assert "1.000" in repr_str


class TestFusePoses:
    """Tests for pose fusion with averaging."""

    def test_fuse_single_pose(self):
        """Test fusing single pose returns that pose."""
        pose = PoseEstimate(x=1.0, y=2.0, yaw=0.5, confidence=0.8)
        result = fuse_poses([pose])
        assert result.x == pose.x
        assert result.y == pose.y
        assert result.yaw == pose.yaw

    def test_fuse_two_identical_poses(self):
        """Test fusing identical poses."""
        pose1 = PoseEstimate(x=1.0, y=2.0, yaw=0.5, confidence=0.8)
        pose2 = PoseEstimate(x=1.0, y=2.0, yaw=0.5, confidence=0.8)
        result = fuse_poses([pose1, pose2])
        
        assert result.x == 1.0
        assert result.y == 2.0
        assert np.isclose(result.yaw, 0.5)

    def test_fuse_two_different_poses(self):
        """Test fusing different poses with equal weight."""
        pose1 = PoseEstimate(x=0.0, y=0.0, yaw=0.0, confidence=0.8)
        pose2 = PoseEstimate(x=2.0, y=2.0, yaw=0.0, confidence=0.8)
        result = fuse_poses([pose1, pose2])
        
        # Should be average
        assert result.x == 1.0
        assert result.y == 1.0

    def test_fuse_weighted_by_confidence(self):
        """Test that fusion uses confidence as weight."""
        # Pose 1 is at origin with high confidence
        pose1 = PoseEstimate(x=0.0, y=0.0, yaw=0.0, confidence=0.9)
        # Pose 2 is at (10, 10) with low confidence
        pose2 = PoseEstimate(x=10.0, y=10.0, yaw=0.0, confidence=0.1)
        
        result = fuse_poses([pose1, pose2])
        
        # Result should be much closer to pose1
        assert result.x < 2.0
        assert result.y < 2.0

    def test_fuse_yaw_circular_mean(self):
        """Test that yaw uses circular mean."""
        # Poses at opposite ends of angle spectrum
        pose1 = PoseEstimate(x=0.0, y=0.0, yaw=math.pi - 0.1, confidence=0.5)
        pose2 = PoseEstimate(x=0.0, y=0.0, yaw=-math.pi + 0.1, confidence=0.5)
        
        result = fuse_poses([pose1, pose2])
        
        # Mean should be near ±π (not 0)
        assert abs(abs(result.yaw) - math.pi) < 0.3

    def test_fuse_confidence_is_max(self):
        """Test that fused confidence is max of inputs."""
        pose1 = PoseEstimate(x=0.0, y=0.0, yaw=0.0, confidence=0.6)
        pose2 = PoseEstimate(x=0.0, y=0.0, yaw=0.0, confidence=0.9)
        pose3 = PoseEstimate(x=0.0, y=0.0, yaw=0.0, confidence=0.7)
        
        result = fuse_poses([pose1, pose2, pose3])
        assert result.confidence == 0.9

    def test_fuse_empty_raises(self):
        """Test that empty pose list raises error."""
        with pytest.raises(ValueError):
            fuse_poses([])

    def test_fuse_three_poses(self):
        """Test fusing three poses."""
        pose1 = PoseEstimate(x=0.0, y=0.0, yaw=0.0, confidence=0.9)
        pose2 = PoseEstimate(x=1.0, y=1.0, yaw=0.1, confidence=0.5)
        pose3 = PoseEstimate(x=2.0, y=2.0, yaw=0.2, confidence=0.5)
        
        result = fuse_poses([pose1, pose2, pose3])
        
        # Result should be weighted toward pose1 (highest confidence)
        assert result.x < 1.5
        assert result.y < 1.5


class TestFusePosesMedian:
    """Tests for pose fusion with median."""

    def test_fuse_median_single_pose(self):
        """Test median fusion with single pose."""
        pose = PoseEstimate(x=1.0, y=2.0, yaw=0.5, confidence=0.8)
        result = fuse_poses_with_median([pose])
        assert result.x == pose.x

    def test_fuse_median_robustness(self):
        """Test that median is robust to outliers."""
        # Two poses at origin, one far outlier
        pose1 = PoseEstimate(x=0.0, y=0.0, yaw=0.0, confidence=0.8)
        pose2 = PoseEstimate(x=0.1, y=0.1, yaw=0.0, confidence=0.8)
        pose_outlier = PoseEstimate(x=100.0, y=100.0, yaw=0.0, confidence=0.1)
        
        result = fuse_poses_with_median([pose1, pose2, pose_outlier])
        
        # Median should ignore the outlier, be closer to 0 than average
        assert result.x < 30.0
        assert result.y < 30.0
