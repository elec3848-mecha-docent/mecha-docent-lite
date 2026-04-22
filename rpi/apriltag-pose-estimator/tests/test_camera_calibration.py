"""
Unit tests for camera_calibration module.
"""

import numpy as np
import pytest

from apriltag_pose_estimator import CameraCalibration


class TestCameraCalibration:
    """Tests for CameraCalibration class."""

    def test_init_valid(self, sample_calibration):
        """Test initialization with valid parameters."""
        assert sample_calibration.image_width == 640
        assert sample_calibration.image_height == 480
        assert sample_calibration.intrinsic_matrix.shape == (3, 3)
        assert sample_calibration.distortion_coefficients.shape == (5,)

    def test_init_invalid_intrinsic_shape(self):
        """Test initialization fails with wrong intrinsic shape."""
        bad_intrinsic = np.eye(2)
        distortion = np.zeros(5)
        with pytest.raises(ValueError, match="3×3"):
            CameraCalibration(bad_intrinsic, distortion, 640, 480)

    def test_from_yaml_valid(self, sample_calibration_yaml):
        """Test loading from YAML file."""
        calib = CameraCalibration.from_yaml(str(sample_calibration_yaml))
        assert calib.image_width == 640
        assert calib.image_height == 480
        assert np.isclose(calib.intrinsic_matrix[0, 0], 1300.0)
        assert np.isclose(calib.intrinsic_matrix[1, 1], 1300.0)

    def test_from_yaml_file_not_found(self):
        """Test loading from non-existent file."""
        with pytest.raises(FileNotFoundError):
            CameraCalibration.from_yaml("/nonexistent/path.yaml")

    def test_from_yaml_missing_field(self, tmp_path):
        """Test loading from YAML with missing field."""
        bad_yaml = tmp_path / "bad.yaml"
        bad_yaml.write_text("camera_matrix: [[1, 0, 0], [0, 1, 0], [0, 0, 1]]")
        
        with pytest.raises(ValueError, match="distortion"):
            CameraCalibration.from_yaml(str(bad_yaml))

    def test_to_dict(self, sample_calibration):
        """Test conversion to dictionary."""
        calib_dict = sample_calibration.to_dict()
        assert "intrinsic_matrix" in calib_dict
        assert "distortion_coefficients" in calib_dict
        assert "image_width" in calib_dict
        assert "image_height" in calib_dict
        assert calib_dict["image_width"] == 640

    def test_repr(self, sample_calibration):
        """Test string representation."""
        repr_str = repr(sample_calibration)
        assert "CameraCalibration" in repr_str
        assert "640x480" in repr_str
        assert "1300" in repr_str
