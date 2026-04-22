"""
Unit tests for pose_estimator module.
"""

import math

import cv2
import numpy as np
import pytest

from apriltag_pose_estimator import (
    AprilTagMap,
    CameraCalibration,
    PoseEstimate,
    PoseEstimator,
    TagDetection,
)


class TestTagDetection:
    """Tests for TagDetection dataclass."""

    def test_creation(self):
        """Test creating TagDetection."""
        corners = np.array([[0, 0], [100, 0], [100, 100], [0, 100]], dtype=np.float32)
        center = np.array([50, 50], dtype=np.float32)
        det = TagDetection(tag_id=5, corners=corners, center=center, confidence=0.95)
        
        assert det.tag_id == 5
        assert det.corners.shape == (4, 2)
        assert det.confidence == 0.95


class TestPoseEstimator:
    """Tests for PoseEstimator class."""

    def test_init_valid(self, sample_calibration, sample_tag_map):
        """Test initialization."""
        estimator = PoseEstimator(sample_calibration, sample_tag_map)
        assert estimator.calibration is sample_calibration
        assert estimator.tag_map is sample_tag_map

    def test_init_invalid_calibration(self, sample_tag_map):
        """Test initialization fails with invalid calibration."""
        with pytest.raises(ValueError, match="CameraCalibration"):
            PoseEstimator("not_a_calibration", sample_tag_map)

    def test_init_invalid_tag_map(self, sample_calibration):
        """Test initialization fails with invalid tag map."""
        with pytest.raises(ValueError, match="AprilTagMap"):
            PoseEstimator(sample_calibration, "not_a_map")

    def test_detect_tags_empty_frame(self, sample_calibration, sample_tag_map):
        """Test tag detection on empty frame."""
        estimator = PoseEstimator(sample_calibration, sample_tag_map)
        frame = np.zeros((480, 640), dtype=np.uint8)
        detections = estimator.detect_tags(frame)
        
        # Empty frame should have no detections
        assert len(detections) == 0

    def test_detect_tags_color_frame(self, sample_calibration, sample_tag_map):
        """Test tag detection on color frame (should convert to gray)."""
        estimator = PoseEstimator(sample_calibration, sample_tag_map)
        frame = np.zeros((480, 640, 3), dtype=np.uint8)
        detections = estimator.detect_tags(frame)
        
        assert isinstance(detections, list)

    def test_estimate_pose_no_tags(self, sample_calibration, sample_tag_map):
        """Test pose estimation with no tags detected."""
        estimator = PoseEstimator(sample_calibration, sample_tag_map)
        frame = np.zeros((480, 640), dtype=np.uint8)
        
        pose = estimator.estimate_pose(frame)
        
        # Should return last known pose (0, 0, 0) with confidence=0
        assert isinstance(pose, PoseEstimate)
        assert pose.confidence == 0.0

    def test_estimate_pose_returns_pose_estimate(self, sample_calibration):
        """Test that estimate_pose returns PoseEstimate."""
        tag_map = AprilTagMap()
        tag_map.add_tag(0, x=0.0, y=0.0, yaw=0.0, size=0.1)
        
        estimator = PoseEstimator(sample_calibration, tag_map)
        frame = np.zeros((480, 640), dtype=np.uint8)
        
        pose = estimator.estimate_pose(frame)
        assert isinstance(pose, PoseEstimate)
        assert hasattr(pose, "x")
        assert hasattr(pose, "y")
        assert hasattr(pose, "yaw")
        assert hasattr(pose, "confidence")

    def test_set_last_known_pose(self, sample_calibration, sample_tag_map):
        """Test setting last known pose."""
        estimator = PoseEstimator(sample_calibration, sample_tag_map)
        estimator.set_last_known_pose(x=5.0, y=10.0, yaw=1.5)
        
        frame = np.zeros((480, 640), dtype=np.uint8)
        pose = estimator.estimate_pose(frame)
        
        # Should return the set pose (with confidence=0 since no tags detected)
        assert np.isclose(pose.x, 5.0)
        assert np.isclose(pose.y, 10.0)
        assert np.isclose(pose.yaw, 1.5)

    def test_get_tag_3d_corners(self, sample_calibration, sample_tag_map):
        """Test 3D tag corner generation."""
        estimator = PoseEstimator(sample_calibration, sample_tag_map)
        corners_3d = estimator._get_tag_3d_corners(0.1)
        
        assert corners_3d.shape == (4, 3)
        # All corners should have Z=0 (flat on wall)
        assert np.allclose(corners_3d[:, 2], 0.0)
        # Corners should be at ±0.05 in X and Y
        assert np.allclose(np.abs(corners_3d[:, 0]), 0.05)
        assert np.allclose(np.abs(corners_3d[:, 1]), 0.05)

    def test_extract_yaw_from_identity_rotation(self, sample_calibration, sample_tag_map):
        """Test yaw extraction from identity rotation."""
        estimator = PoseEstimator(sample_calibration, sample_tag_map)
        R = np.eye(3)
        yaw = estimator._extract_yaw_from_rotation(R)
        
        assert np.isclose(yaw, 0.0)

    def test_extract_yaw_from_90_degree_rotation(self, sample_calibration, sample_tag_map):
        """Test yaw extraction from 90-degree rotation."""
        estimator = PoseEstimator(sample_calibration, sample_tag_map)
        
        # Create 90-degree rotation around Z axis
        angle = math.pi / 2
        R = np.array([
            [math.cos(angle), -math.sin(angle), 0],
            [math.sin(angle), math.cos(angle), 0],
            [0, 0, 1]
        ], dtype=np.float64)
        
        yaw = estimator._extract_yaw_from_rotation(R)
        assert np.isclose(yaw, math.pi / 2)

    def test_update_last_pose_on_successful_detection(self, sample_calibration, sample_tag_map):
        """Test that successful detection updates last known pose."""
        estimator = PoseEstimator(sample_calibration, sample_tag_map)
        
        # First frame: no detection
        frame_empty = np.zeros((480, 640), dtype=np.uint8)
        pose1 = estimator.estimate_pose(frame_empty)
        
        # Manually set a pose (simulating detection)
        estimator.set_last_known_pose(x=1.0, y=2.0, yaw=0.5)
        
        # Second frame: still no detection, should return the set pose
        pose2 = estimator.estimate_pose(frame_empty)
        assert np.isclose(pose2.x, 1.0)
        assert np.isclose(pose2.y, 2.0)


class TestPoseEstimatorIntegration:
    """Integration tests for PoseEstimator."""

    def test_full_workflow(self, sample_calibration_yaml, sample_tag_map_json, tmp_path):
        """Test full workflow from config files."""
        # This simulates the real-world usage pattern
        calib = CameraCalibration.from_yaml(str(sample_calibration_yaml))
        tags = AprilTagMap.from_json(str(sample_tag_map_json))
        
        estimator = PoseEstimator(calib, tags)
        
        # Process empty frame
        frame = np.zeros((480, 640), dtype=np.uint8)
        pose = estimator.estimate_pose(frame)
        
        assert isinstance(pose, PoseEstimate)
        assert "x" in pose.to_dict()

    def test_multiple_frames_update_last_pose(self, sample_calibration, sample_tag_map):
        """Test that multiple frames maintain last known pose."""
        estimator = PoseEstimator(sample_calibration, sample_tag_map)
        estimator.set_last_known_pose(x=1.0, y=2.0, yaw=0.5)
        
        frame = np.zeros((480, 640), dtype=np.uint8)
        
        # First frame with no detection
        pose1 = estimator.estimate_pose(frame)
        assert pose1.confidence == 0.0
        
        # Second frame should still have access to the last pose
        pose2 = estimator.estimate_pose(frame)
        assert np.isclose(pose2.x, 1.0)
        assert np.isclose(pose2.y, 2.0)
