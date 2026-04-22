"""
Example: Basic usage of AprilTag pose estimator.

This script demonstrates how to:
1. Load camera calibration from YAML
2. Load tag map from JSON
3. Initialize PoseEstimator
4. Estimate pose from a camera frame
"""

import logging
import sys
from pathlib import Path

import cv2
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from apriltag_pose_estimator import (
    AprilTagMap,
    CameraCalibration,
    PoseEstimator,
)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Run example pose estimation."""
    
    # Load camera calibration
    config_dir = Path(__file__).parent / "config"
    calib_path = config_dir / "camera_calibration_rpi.yaml"
    
    if not calib_path.exists():
        logger.error(f"Calibration file not found: {calib_path}")
        return
    
    logger.info(f"Loading camera calibration from {calib_path}")
    calibration = CameraCalibration.from_yaml(str(calib_path))
    logger.info(f"Camera: {calibration}")
    
    # Load tag map
    tag_map_path = config_dir / "tag_map_example.json"
    
    if not tag_map_path.exists():
        logger.error(f"Tag map file not found: {tag_map_path}")
        return
    
    logger.info(f"Loading tag map from {tag_map_path}")
    tag_map = AprilTagMap.from_json(str(tag_map_path))
    logger.info(f"Loaded {len(tag_map)} tags")
    
    # Initialize estimator
    estimator = PoseEstimator(calibration, tag_map)
    logger.info("PoseEstimator initialized")
    
    # Example 1: Create a synthetic frame (all black)
    # In real usage, this would come from cv2.VideoCapture() or similar
    logger.info("\n--- Example 1: No tags detected ---")
    frame_empty = np.zeros((480, 640, 3), dtype=np.uint8)
    pose = estimator.estimate_pose(frame_empty)
    logger.info(f"Estimated pose: {pose}")
    logger.info(f"  X={pose.x:.3f}, Y={pose.y:.3f}, Yaw={pose.yaw:.3f}, Confidence={pose.confidence:.3f}")
    
    # Example 2: Set a known pose manually
    logger.info("\n--- Example 2: Set initial pose manually ---")
    estimator.set_last_known_pose(x=1.0, y=0.5, yaw=0.0)
    logger.info("Set last known pose to (1.0, 0.5, 0.0)")
    
    # Next frame with no tags should return the set pose with confidence=0
    pose = estimator.estimate_pose(frame_empty)
    logger.info(f"Estimated pose (should match set pose): {pose}")
    
    # Example 3: Load a frame from file (if available)
    logger.info("\n--- Example 3: Attempt to load frame from file ---")
    test_image_paths = [
        Path("test_image.jpg"),
        Path("test.png"),
        Path("frame.jpg"),
    ]
    
    frame_loaded = None
    for img_path in test_image_paths:
        if img_path.exists():
            logger.info(f"Loading image: {img_path}")
            frame_loaded = cv2.imread(str(img_path))
            if frame_loaded is not None:
                logger.info(f"Image shape: {frame_loaded.shape}")
                break
    
    if frame_loaded is not None:
        pose = estimator.estimate_pose(frame_loaded)
        logger.info(f"Estimated pose from loaded image: {pose}")
    else:
        logger.info("No test image found. (This is expected for this example.)")
    
    # Example 4: Show available tags
    logger.info("\n--- Example 4: Tags in map ---")
    all_tags = tag_map.get_all_tags()
    for tag_id, tag_def in all_tags.items():
        logger.info(
            f"  Tag {tag_id}: pos=({tag_def.x:.2f}, {tag_def.y:.2f}), "
            f"yaw={tag_def.yaw:.3f}, size={tag_def.size:.3f}m"
        )
    
    # Example 5: Access calibration details
    logger.info("\n--- Example 5: Camera calibration details ---")
    calib_dict = calibration.to_dict()
    logger.info(f"  Camera matrix K:\n{np.array(calib_dict['intrinsic_matrix'])}")
    logger.info(f"  Distortion: {calib_dict['distortion_coefficients']}")
    
    logger.info("\nExample completed!")


if __name__ == "__main__":
    main()
