"""
Core pose estimator: detects AprilTags and solves for 2D global robot pose.
"""

import logging
import math
from typing import Any, Dict, List, NamedTuple, Optional, Tuple, cast

import cv2
import numpy as np
from numpy.typing import NDArray

from .camera_calibration import CameraCalibration
from .fusion import PoseEstimate, fuse_poses
from .tag_map import AprilTagMap

logger = logging.getLogger(__name__)


class TagDetection(NamedTuple):
    """
    A detected AprilTag in an image.

    Attributes:
        tag_id (int): Detected tag ID.
        corners (np.ndarray): 4×2 array of corner pixel coordinates.
        center (np.ndarray): 1×2 array of center pixel coordinate.
        confidence (float): Detection confidence in [0, 1].
    """

    tag_id: int
    corners: np.ndarray  # Shape: (4, 2)
    center: np.ndarray  # Shape: (2,)
    confidence: float


class PoseEstimator:
    """
    Estimates 2D robot pose from AprilTag detections.

    For wall-mounted tags:
    - Tags are flat on walls with known global 2D position and orientation
    - Camera is monocular, mounted on robot
    - Solver uses solvePnP to compute camera pose relative to each tag
    - Fuses multiple detections for robust pose estimate
    - Falls back to last known pose if no tags detected

    Attributes:
        calibration (CameraCalibration): Camera intrinsics and distortion.
        tag_map (AprilTagMap): Map of known AprilTag positions.
        _last_pose (PoseEstimate): Last valid pose estimate.
    """

    def __init__(
        self,
        calibration: CameraCalibration,
        tag_map: AprilTagMap,
        tag_height: float = 0.05,
    ):
        """
        Initialize pose estimator.

        Args:
            calibration: Camera calibration (intrinsics, distortion).
            tag_map: Map of known AprilTag positions.
            tag_height: Physical height of AprilTag (meters), used for
                       constructing 3D corners on wall. Tags assumed to be
                       square with side length given in tag_map.

        Raises:
            ValueError: If calibration or tag_map is invalid.
        """
        if not isinstance(calibration, CameraCalibration):
            raise ValueError("calibration must be a CameraCalibration instance")
        if not isinstance(tag_map, AprilTagMap):
            raise ValueError("tag_map must be an AprilTagMap instance")

        self.calibration = calibration
        self.tag_map = tag_map
        self.tag_height = float(tag_height)

        # Initialize with zero pose; no confidence
        self._last_pose = PoseEstimate(x=0.0, y=0.0, yaw=0.0, confidence=0.0)

        # Try to initialize detector (lazy import - fails only at detection time)
        self.detector = None
        self._detector_load_attempted = False

    def detect_tags(self, frame: np.ndarray) -> List[TagDetection]:
        """
        Detect AprilTags in a frame.

        Args:
            frame: Input image (numpy array, typically from OpenCV or camera).
                   Can be grayscale (HxW) or color (HxWx3).
                   Detector expects uint8.

        Returns:
            List of TagDetection objects with id, corners, center, confidence.

        Raises:
            ImportError: If pupil-apriltags library is not installed.
        """
        # Lazy initialization of detector
        if not self._detector_load_attempted:
            try:
                from pupil_apriltags import Detector

                self.detector = Detector(families="tag36h11")
                self._detector_load_attempted = True
            except ImportError:
                raise ImportError(
                    "pupil-apriltags library required. Install with: pip install pupil-apriltags"
                )
        
        if self.detector is None:
            raise ImportError(
                "pupil-apriltags library not available. Install with: pip install pupil-apriltags"
            )

        # Convert to grayscale if needed
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame

        # Ensure uint8
        gray_u8: NDArray[np.uint8] = np.asarray(gray, dtype=np.uint8)

        # Detect
        detections = cast(List[Any], self.detector.detect(gray_u8))

        results = []
        for det in detections:
            # pupil_apriltags detection provides decision_margin as quality metric.
            confidence = max(float(getattr(det, "decision_margin", 0.0)), 0.0)

            results.append(
                TagDetection(
                    tag_id=int(det.tag_id),
                    corners=np.asarray(det.corners, dtype=np.float32),
                    center=np.asarray(det.center, dtype=np.float32),
                    confidence=float(confidence),
                )
            )

        return results

    def _get_tag_3d_corners(self, tag_size: float) -> np.ndarray:
        """
        Get 3D corners of a tag in its local frame.

        For wall-mounted tags, corners are in a plane.

        Args:
            tag_size: Size of tag (side length in meters).

        Returns:
            4×3 array of 3D corner positions in tag frame.
            Corners are:
            - [0]: top-left
            - [1]: top-right
            - [2]: bottom-right
            - [3]: bottom-left
        """
        half_size = tag_size / 2.0

        # Tag is centered at origin in its frame, lying in XY plane
        # Z=0 for flat wall tag, extends vertically in +Y
        corners_3d = np.array(
            [
                [-half_size, half_size, 0],  # top-left
                [half_size, half_size, 0],   # top-right
                [half_size, -half_size, 0],  # bottom-right
                [-half_size, -half_size, 0], # bottom-left
            ],
            dtype=np.float32,
        )
        return corners_3d

    def estimate_single_pose(
        self, detection: TagDetection
    ) -> Optional[PoseEstimate]:
        """
        Estimate 2D robot pose from a single tag detection.

        Uses solvePnP to find camera pose relative to tag, then transforms
        to global frame using tag's known position and orientation.

        Args:
            detection: TagDetection from detect_tags().

        Returns:
            PoseEstimate if successful, None if tag not in map or solvePnP fails.
        """
        tag_id = detection.tag_id
        tag_def = self.tag_map.get_tag(tag_id)

        if tag_def is None:
            logger.warning(f"Tag {tag_id} not in map, skipping")
            return None

        # Get 3D corners in tag frame
        tag_3d = self._get_tag_3d_corners(tag_def.size)

        # Image corners from detection (should be in consistent order)
        img_points = detection.corners.reshape(4, 1, 2).astype(np.float32)

        # Solve PnP: find camera pose relative to tag
        success, rvec, tvec = cv2.solvePnP(
            tag_3d,
            img_points,
            self.calibration.intrinsic_matrix,
            self.calibration.distortion_coefficients,
            useExtrinsicGuess=False,
            flags=cv2.SOLVEPNP_IPPE_SQUARE,  # Optimized for square tags
        )

        if not success:
            logger.warning(f"solvePnP failed for tag {tag_id}")
            return None

        # Convert rotation vector to matrix
        R_cam_tag, _ = cv2.Rodrigues(rvec)

        # At this point:
        # - tvec is camera's position relative to tag (in tag frame)
        # - R_cam_tag is camera's orientation relative to tag

        # We need to invert: get tag's position relative to camera
        # If P_cam = R_cam_tag @ P_tag + tvec_camera_in_tag
        # Then P_tag = R_tag_cam @ (P_cam - tvec_camera_in_tag)
        #            = R_cam_tag.T @ P_cam - R_cam_tag.T @ tvec_camera_in_tag

        R_tag_cam = R_cam_tag.T
        tvec_tag_in_cam = -R_tag_cam @ tvec.flatten()

        # Now we have tag's position in camera frame:
        # For wall-mounted tags in camera frame:
        # - Camera +X: right
        # - Camera +Y: down
        # - Camera +Z: forward (away from camera)

        # For 2D robot pose:
        # - Robot X (forward): corresponds to camera Z
        # - Robot Y (left): corresponds to camera (-X)
        # - Robot Yaw: rotation around vertical axis

        # Tag's position in camera frame (3D)
        tag_x_cam = tvec_tag_in_cam[0]
        tag_y_cam = tvec_tag_in_cam[1]
        tag_z_cam = tvec_tag_in_cam[2]

        # For 2D pose, use X-Z plane (camera's forward and right)
        # This assumes tag is at a known height on wall, and we use
        # the X-Z projection to estimate horizontal robot position

        # Tag global position
        tag_x_global = tag_def.x
        tag_y_global = tag_def.y
        tag_yaw_global = tag_def.yaw

        # Camera position relative to tag (in tag frame, which is global)
        # Need to rotate tvec_tag_in_cam by inverse of tag orientation
        cam_pos_in_tag = self._rotate_camera_pose_to_global(
            tvec_tag_in_cam, R_tag_cam, tag_yaw_global
        )

        # Robot (camera) position in global frame
        robot_x_global = tag_x_global - cam_pos_in_tag[0]
        robot_y_global = tag_y_global - cam_pos_in_tag[1]

        # Robot yaw: combine tag's global yaw with camera's relative rotation
        cam_forward_tag = -R_tag_cam[:, 2]  # camera +Z axis in tag frame
        fwd_x_tag = float(cam_forward_tag[0])
        fwd_z_tag = float(cam_forward_tag[2])

        fwd_x_global = math.cos(tag_yaw_global) * fwd_z_tag + math.sin(tag_yaw_global) * fwd_x_tag
        fwd_y_global = math.sin(tag_yaw_global) * fwd_z_tag - math.cos(tag_yaw_global) * fwd_x_tag

        robot_yaw_global = math.atan2(fwd_y_global, fwd_x_global)

        from . import utils
        robot_yaw_global = utils.normalize_angle(robot_yaw_global)

        # Use detection confidence as pose confidence
        confidence = detection.confidence

        return PoseEstimate(
            x=robot_x_global,
            y=robot_y_global,
            yaw=robot_yaw_global,
            confidence=confidence,
        )

    def _rotate_camera_pose_to_global(
        self, cam_pos_tag_frame: np.ndarray, R_tag_cam: np.ndarray, tag_yaw: float
    ) -> np.ndarray:
        """
        Rotate camera position from tag frame to global frame.

        Args:
            cam_pos_tag_frame: Camera position in tag frame (3D).
            R_tag_cam: Rotation matrix from camera to tag frame.
            tag_yaw: Tag's global yaw orientation.

        Returns:
            3D position in global frame (using 2D projection).
        """
        # Create rotation for tag's yaw (rotation around Z axis in global frame)
        cos_yaw = math.cos(tag_yaw)
        sin_yaw = math.sin(tag_yaw)

        # For wall-mounted tags, the tag frame is aligned with global frame
        # (tag X = global X, tag Y = global Y, tag Z = global Z)
        # Camera is offset in tag frame; rotate by tag yaw to get global offset

        cam_x_tag = cam_pos_tag_frame[0]
        cam_z_tag = cam_pos_tag_frame[2]

        # Rotate to global frame (XY plane)
        cam_x_global = cos_yaw * cam_z_tag + sin_yaw * cam_x_tag
        cam_y_global = sin_yaw * cam_z_tag - cos_yaw * cam_x_tag

        return np.array([cam_x_global, cam_y_global, cam_pos_tag_frame[1]])

    def _extract_yaw_from_rotation(self, R: np.ndarray) -> float:
        """
        Extract 2D yaw rotation from a 3×3 rotation matrix.

        Args:
            R: 3×3 rotation matrix.

        Returns:
            Yaw angle in radians.
        """
        import math
        return -math.atan2(R[0, 2], R[2, 2])

    def estimate_pose_details(
        self, frame: np.ndarray
    ) -> Tuple[PoseEstimate, Dict[int, PoseEstimate], List[TagDetection]]:
        """
        Estimate fused pose and retain individual per-tag pose solutions.

        Args:
            frame: Input image from camera.

        Returns:
            Tuple of:
            - fused PoseEstimate
            - dict mapping detected tag_id to its individual PoseEstimate
            - list of raw TagDetection objects for the frame
        """
        detections = self.detect_tags(frame)

        if not detections:
            return (
                PoseEstimate(
                    x=self._last_pose.x,
                    y=self._last_pose.y,
                    yaw=self._last_pose.yaw,
                    confidence=0.0,
                ),
                {},
                [],
            )

        poses = []
        poses_by_tag_id: Dict[int, PoseEstimate] = {}
        for det in detections:
            pose = self.estimate_single_pose(det)
            if pose is not None:
                poses.append(pose)
                poses_by_tag_id[det.tag_id] = pose

        if not poses:
            return (
                PoseEstimate(
                    x=self._last_pose.x,
                    y=self._last_pose.y,
                    yaw=self._last_pose.yaw,
                    confidence=0.0,
                ),
                {},
                detections,
            )

        fused_pose = fuse_poses(poses)
        self._last_pose = fused_pose

        logger.debug(
            f"Estimated pose from {len(poses)}/{len(detections)} tags: {fused_pose}"
        )
        return fused_pose, poses_by_tag_id, detections

    def estimate_pose(self, frame: np.ndarray) -> PoseEstimate:
        """
        Estimate robot's 2D global pose from a camera frame.

        Main entry point. Detects all AprilTags, estimates pose from each,
        fuses them, and updates last known pose.

        Args:
            frame: Input image from camera.

        Returns:
            PoseEstimate with (x, y, yaw, confidence).
            If no tags detected, returns last known pose with confidence=0.

        Raises:
            ValueError: If pose estimation fails critically.
        """
        fused_pose, _, detections = self.estimate_pose_details(frame)
        if not detections:
            logger.debug(
                "No tags detected, returning last known pose with confidence=0"
            )
        elif fused_pose.confidence == 0.0:
            logger.debug(
                "All tag pose estimations failed, returning last known pose with confidence=0"
            )
        return fused_pose

    def set_last_known_pose(self, x: float, y: float, yaw: float) -> None:
        """
        Manually set the last known pose (useful for initialization).

        Args:
            x: X position.
            y: Y position.
            yaw: Yaw rotation.
        """
        self._last_pose = PoseEstimate(x=x, y=y, yaw=yaw, confidence=1.0)
