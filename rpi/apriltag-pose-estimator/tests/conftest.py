"""
Pytest fixtures and configuration for tests.
"""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from apriltag_pose_estimator import (
    AprilTagMap,
    CameraCalibration,
)


@pytest.fixture
def sample_calibration():
    """Sample camera calibration."""
    intrinsic = np.array([
        [1300.0, 0.0, 320.0],
        [0.0, 1300.0, 240.0],
        [0.0, 0.0, 1.0]
    ], dtype=np.float64)
    distortion = np.array([0.05, -0.1, 0.0, 0.0, 0.0], dtype=np.float64)
    return CameraCalibration(intrinsic, distortion, 640, 480)


@pytest.fixture
def sample_calibration_yaml(tmp_path):
    """Create a temporary YAML calibration file."""
    yaml_content = """camera_matrix:
  - [1300.0, 0.0, 320.0]
  - [0.0, 1300.0, 240.0]
  - [0.0, 0.0, 1.0]
distortion_coefficients: [0.05, -0.1, 0.0, 0.0, 0.0]
image_width: 640
image_height: 480
"""
    calib_file = tmp_path / "calibration.yaml"
    calib_file.write_text(yaml_content)
    return calib_file


@pytest.fixture
def sample_tag_map():
    """Sample AprilTag map."""
    tag_map = AprilTagMap()
    tag_map.add_tag(tag_id=0, x=0.0, y=0.0, yaw=0.0, size=0.1)
    tag_map.add_tag(tag_id=1, x=1.0, y=0.0, yaw=0.0, size=0.1)
    tag_map.add_tag(tag_id=2, x=0.0, y=1.0, yaw=1.5708, size=0.1)
    return tag_map


@pytest.fixture
def sample_tag_map_json(tmp_path):
    """Create a temporary JSON tag map file."""
    json_content = """{
  "tags": [
    {"tag_id": 0, "x": 0.0, "y": 0.0, "yaw": 0.0, "size": 0.1},
    {"tag_id": 1, "x": 1.0, "y": 0.0, "yaw": 0.0, "size": 0.1},
    {"tag_id": 2, "x": 0.0, "y": 1.0, "yaw": 1.5708, "size": 0.1}
  ]
}
"""
    tag_file = tmp_path / "tags.json"
    tag_file.write_text(json_content)
    return tag_file


@pytest.fixture
def sample_frame():
    """Sample camera frame (640x480 grayscale)."""
    return np.zeros((480, 640), dtype=np.uint8)
