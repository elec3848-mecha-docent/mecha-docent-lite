"""
Unit tests for utils module.
"""

import math

import numpy as np
import pytest

from apriltag_pose_estimator import utils


class TestAngleNormalization:
    """Tests for angle normalization."""

    def test_normalize_zero(self):
        """Test normalizing zero."""
        assert utils.normalize_angle(0.0) == 0.0

    def test_normalize_pi(self):
        """Test normalizing π."""
        assert np.isclose(utils.normalize_angle(math.pi), math.pi)

    def test_normalize_neg_pi(self):
        """Test normalizing -π."""
        assert np.isclose(utils.normalize_angle(-math.pi), -math.pi)

    def test_normalize_above_pi(self):
        """Test normalizing angle > π."""
        result = utils.normalize_angle(2 * math.pi + 0.1)
        assert -math.pi <= result <= math.pi
        assert np.isclose(result, 0.1)

    def test_normalize_below_neg_pi(self):
        """Test normalizing angle < -π."""
        result = utils.normalize_angle(-2 * math.pi - 0.1)
        assert -math.pi <= result <= math.pi
        assert np.isclose(result, -0.1)

    def test_normalize_multiple_wraps(self):
        """Test normalizing angle with multiple wraps."""
        result = utils.normalize_angle(10 * math.pi)
        assert -math.pi <= result <= math.pi


class TestYawFromRotationMatrix:
    """Tests for extracting yaw from rotation matrix."""

    def test_zero_rotation(self):
        """Test zero rotation (identity matrix)."""
        R = np.eye(3)
        yaw = utils.yaw_from_rotation_matrix(R)
        assert np.isclose(yaw, 0.0)

    def test_90_degree_rotation(self):
        """Test 90-degree rotation."""
        # Rotation matrix for 90 degrees around Z
        angle = math.pi / 2
        R = np.array([
            [math.cos(angle), -math.sin(angle), 0],
            [math.sin(angle), math.cos(angle), 0],
            [0, 0, 1]
        ], dtype=np.float64)
        yaw = utils.yaw_from_rotation_matrix(R)
        assert np.isclose(yaw, math.pi / 2)

    def test_invalid_shape(self):
        """Test that invalid shape raises error."""
        bad_matrix = np.eye(2)
        with pytest.raises(ValueError, match="3×3"):
            utils.yaw_from_rotation_matrix(bad_matrix)

    def test_negative_rotation(self):
        """Test negative rotation."""
        angle = -math.pi / 4
        R = np.array([
            [math.cos(angle), -math.sin(angle), 0],
            [math.sin(angle), math.cos(angle), 0],
            [0, 0, 1]
        ], dtype=np.float64)
        yaw = utils.yaw_from_rotation_matrix(R)
        assert np.isclose(yaw, angle)


class TestAngleDistance:
    """Tests for circular angle distance."""

    def test_same_angle(self):
        """Test distance between same angle."""
        assert utils.angle_distance(0.5, 0.5) == 0.0

    def test_90_degree_distance(self):
        """Test 90-degree distance."""
        dist = utils.angle_distance(0.0, math.pi / 2)
        assert np.isclose(dist, math.pi / 2)

    def test_wraparound_distance(self):
        """Test distance across wraparound."""
        # Should be shortest path
        dist = utils.angle_distance(math.pi - 0.1, -math.pi + 0.1)
        assert dist < 0.3  # Should be small, not 2π


class TestCircularMean:
    """Tests for circular mean of angles."""

    def test_mean_single_angle(self):
        """Test mean of single angle."""
        angles = np.array([0.5])
        mean = utils.circular_mean_angles(angles)
        assert np.isclose(mean, 0.5)

    def test_mean_aligned_angles(self):
        """Test mean of aligned angles."""
        angles = np.array([0.1, 0.2, 0.3])
        mean = utils.circular_mean_angles(angles)
        assert np.isclose(mean, 0.2, atol=0.05)

    def test_weighted_mean(self):
        """Test weighted mean."""
        angles = np.array([0.0, math.pi / 2])
        weights = np.array([0.9, 0.1])
        mean = utils.circular_mean_angles(angles, weights)
        # Should be closer to 0.0 (higher weight)
        assert mean < math.pi / 4

    def test_circular_mean_wraparound(self):
        """Test mean of angles around ±π."""
        # Angles close to π and -π should average near ±π
        angles = np.array([math.pi - 0.1, -math.pi + 0.1])
        mean = utils.circular_mean_angles(angles)
        # Mean should be near ±π
        assert abs(abs(mean) - math.pi) < 0.2

    def test_empty_angles_raises(self):
        """Test that empty array raises error."""
        with pytest.raises(ValueError):
            utils.circular_mean_angles(np.array([]))


class TestPoseToDict:
    """Tests for pose serialization."""

    def test_pose_to_dict(self):
        """Test conversion to dictionary."""
        pose_dict = utils.pose_to_dict(x=1.5, y=2.5, yaw=0.3, confidence=0.95)
        
        assert pose_dict["x"] == 1.5
        assert pose_dict["y"] == 2.5
        assert np.isclose(pose_dict["yaw"], 0.3)
        assert pose_dict["confidence"] == 0.95

    def test_pose_dict_normalizes_yaw(self):
        """Test that yaw is normalized in dict."""
        pose_dict = utils.pose_to_dict(x=0.0, y=0.0, yaw=10*math.pi, confidence=1.0)
        assert -math.pi <= pose_dict["yaw"] <= math.pi
