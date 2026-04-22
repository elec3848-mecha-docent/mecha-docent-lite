"""
Camera calibration handling: intrinsics, distortion coefficients, and file I/O.
"""

import argparse
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np
import yaml


class CameraCalibration:
    """
    Represents camera intrinsic calibration parameters.

    Attributes:
        intrinsic_matrix (np.ndarray): 3×3 camera intrinsic matrix K
        distortion_coefficients (np.ndarray): Distortion coefficients (k1, k2, p1, p2, [k3, ...])
        image_width (int): Image width in pixels
        image_height (int): Image height in pixels
    """

    def __init__(
        self,
        intrinsic_matrix: np.ndarray,
        distortion_coefficients: np.ndarray,
        image_width: int,
        image_height: int,
    ):
        """
        Initialize camera calibration.

        Args:
            intrinsic_matrix: 3×3 K matrix (numpy array).
            distortion_coefficients: Distortion coefficients vector.
            image_width: Image width in pixels.
            image_height: Image height in pixels.

        Raises:
            ValueError: If matrices have incorrect shapes.
        """
        if intrinsic_matrix.shape != (3, 3):
            raise ValueError(
                f"Expected 3×3 intrinsic matrix, got {intrinsic_matrix.shape}"
            )

        self.intrinsic_matrix = np.asarray(intrinsic_matrix, dtype=np.float64)
        self.distortion_coefficients = np.asarray(
            distortion_coefficients, dtype=np.float64
        )
        self.image_width = int(image_width)
        self.image_height = int(image_height)

    @classmethod
    def from_yaml(cls, yaml_path: str) -> "CameraCalibration":
        """
        Load camera calibration from a YAML file.

        Expected YAML structure:
        ```
        camera_matrix:
          - [fx, 0, cx]
          - [0, fy, cy]
          - [0, 0, 1]
        distortion_coefficients: [k1, k2, p1, p2, ...]
        image_width: 640
        image_height: 480
        ```

        Args:
            yaml_path: Path to YAML calibration file.

        Returns:
            CameraCalibration instance.

        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If YAML is malformed or missing required fields.
        """
        yaml_path = Path(yaml_path)
        if not yaml_path.exists():
            raise FileNotFoundError(f"Calibration file not found: {yaml_path}")

        with open(yaml_path, "r") as f:
            data = yaml.safe_load(f)

        if data is None:
            raise ValueError("YAML file is empty")

        # Extract required fields
        if "camera_matrix" not in data:
            raise ValueError("Missing 'camera_matrix' in YAML")
        if "distortion_coefficients" not in data:
            raise ValueError("Missing 'distortion_coefficients' in YAML")
        if "image_width" not in data or "image_height" not in data:
            raise ValueError("Missing 'image_width' or 'image_height' in YAML")

        intrinsic_matrix = np.array(data["camera_matrix"], dtype=np.float64)
        distortion_coefficients = np.array(
            data["distortion_coefficients"], dtype=np.float64
        )
        image_width = int(data["image_width"])
        image_height = int(data["image_height"])

        return cls(intrinsic_matrix, distortion_coefficients, image_width, image_height)

    def to_dict(self) -> dict:
        """
        Convert calibration to dictionary (for serialization, logging).

        Returns:
            Dictionary with 'intrinsic_matrix', 'distortion_coefficients', etc.
        """
        return {
            "intrinsic_matrix": self.intrinsic_matrix.tolist(),
            "distortion_coefficients": self.distortion_coefficients.tolist(),
            "image_width": self.image_width,
            "image_height": self.image_height,
        }

    def to_yaml(self, yaml_path: str) -> None:
        """
        Save calibration to a YAML file.

        Args:
            yaml_path: Destination YAML file path.
        """
        data = {
            "camera_matrix": self.intrinsic_matrix.tolist(),
            "distortion_coefficients": self.distortion_coefficients.flatten().tolist(),
            "image_width": self.image_width,
            "image_height": self.image_height,
        }

        yaml_path = Path(yaml_path)
        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        with open(yaml_path, "w") as f:
            yaml.safe_dump(data, f, sort_keys=False)

    @staticmethod
    def _build_chessboard_object_points(
        chessboard_size: Tuple[int, int],
        square_size: float,
    ) -> np.ndarray:
        """
        Build 3D chessboard corner points in board coordinates.

        Args:
            chessboard_size: Number of inner corners as (cols, rows).
            square_size: Physical square size in meters.

        Returns:
            Array of shape (N, 3), where N = cols * rows.
        """
        cols, rows = chessboard_size
        objp = np.zeros((cols * rows, 3), np.float32)
        objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2)
        objp *= square_size
        return objp

    @classmethod
    def calibrate_from_camera(
        cls,
        camera_index: int = 0,
        chessboard_size: Tuple[int, int] = (9, 6),
        square_size: float = 0.024,
        num_images: int = 20,
        output_yaml_path: Optional[str] = None,
        window_name: str = "Camera Calibration",
    ) -> "CameraCalibration":
        """
        Interactively calibrate camera using a live OpenCV stream.

        Controls:
        - SPACE: capture a frame when chessboard is detected
        - Q: quit capture and run calibration if enough samples exist

        Args:
            camera_index: OpenCV camera index.
            chessboard_size: Number of inner corners (cols, rows).
            square_size: Chessboard square size in meters.
            num_images: Number of successful captures to collect.
            output_yaml_path: Optional output path to save calibration YAML.
            window_name: Name of the OpenCV preview window.

        Returns:
            Calibrated CameraCalibration instance.

        Raises:
            RuntimeError: If camera cannot be opened.
            ValueError: If too few valid captures are collected.
        """
        if num_images < 3:
            raise ValueError("num_images must be at least 3")

        objp = cls._build_chessboard_object_points(chessboard_size, square_size)
        object_points: List[np.ndarray] = []
        image_points: List[np.ndarray] = []

        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open camera index {camera_index}")

        image_size: Optional[Tuple[int, int]] = None
        capture_count = 0

        print("Starting interactive calibration capture...")
        print("Press SPACE to capture when chessboard is detected.")
        print("Press Q to finish and calibrate.")

        try:
            while capture_count < num_images:
                ok, frame = cap.read()
                if not ok:
                    continue

                if image_size is None:
                    image_size = (frame.shape[1], frame.shape[0])

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                found, corners = cv2.findChessboardCorners(
                    gray,
                    chessboard_size,
                    flags=cv2.CALIB_CB_ADAPTIVE_THRESH
                    | cv2.CALIB_CB_FAST_CHECK
                    | cv2.CALIB_CB_NORMALIZE_IMAGE,
                )

                preview = frame.copy()
                if found:
                    cv2.drawChessboardCorners(preview, chessboard_size, corners, found)

                status = (
                    f"Captured {capture_count}/{num_images} | "
                    "SPACE: capture  Q: finish"
                )
                cv2.putText(
                    preview,
                    status,
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )

                if not found:
                    cv2.putText(
                        preview,
                        "Chessboard not found",
                        (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 0, 255),
                        2,
                    )

                cv2.imshow(window_name, preview)
                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):
                    break

                if key == ord(" "):
                    if not found:
                        print("Capture skipped: chessboard not detected.")
                        continue

                    refined = cv2.cornerSubPix(
                        gray,
                        corners,
                        winSize=(11, 11),
                        zeroZone=(-1, -1),
                        criteria=(
                            cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER,
                            30,
                            0.001,
                        ),
                    )
                    object_points.append(objp.copy())
                    image_points.append(refined)
                    capture_count += 1
                    print(f"Captured frame {capture_count}/{num_images}")
        finally:
            cap.release()
            cv2.destroyAllWindows()

        if image_size is None or len(image_points) < 3:
            raise ValueError(
                "Insufficient valid captures. Need at least 3 chessboard images."
            )

        rms_error, camera_matrix, distortion, _rvecs, _tvecs = cv2.calibrateCamera(
            object_points,
            image_points,
            image_size,
            None,
            None,
        )

        calibration = cls(
            intrinsic_matrix=camera_matrix,
            distortion_coefficients=distortion,
            image_width=image_size[0],
            image_height=image_size[1],
        )

        print(f"Calibration complete. RMS reprojection error: {rms_error:.4f}")
        if output_yaml_path:
            calibration.to_yaml(output_yaml_path)
            print(f"Saved calibration to: {output_yaml_path}")

        return calibration

    def __repr__(self) -> str:
        return (
            f"CameraCalibration(image={self.image_width}x{self.image_height}, "
            f"fx={self.intrinsic_matrix[0, 0]:.1f}, fy={self.intrinsic_matrix[1, 1]:.1f})"
        )


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Interactive OpenCV camera calibration")
    parser.add_argument("--camera-index", type=int, default=0, help="OpenCV camera index")
    parser.add_argument("--cols", type=int, default=9, help="Chessboard inner corners (columns)")
    parser.add_argument("--rows", type=int, default=6, help="Chessboard inner corners (rows)")
    parser.add_argument(
        "--square-size",
        type=float,
        default=0.024,
        help="Chessboard square size in meters",
    )
    parser.add_argument("--num-images", type=int, default=20, help="Number of captures")
    parser.add_argument(
        "--output",
        type=str,
        default="config/camera_calibration_rpi.yaml",
        help="Output YAML path",
    )
    return parser


def main() -> None:
    args = _build_cli_parser().parse_args()
    CameraCalibration.calibrate_from_camera(
        camera_index=args.camera_index,
        chessboard_size=(args.cols, args.rows),
        square_size=args.square_size,
        num_images=args.num_images,
        output_yaml_path=args.output,
    )


if __name__ == "__main__":
    main()
