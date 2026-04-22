"""
Live AprilTag localization demo using a camera feed.

Usage:
    python live_localization_demo.py

Controls:
    q: quit
"""

import argparse
import logging
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Tuple

import cv2
import numpy as np

from apriltag_pose_estimator import AprilTagMap, CameraCalibration, PoseEstimator
from apriltag_pose_estimator.tag_map import TagDefinition


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOPVIEW_WIDTH_PX = 360
TOPVIEW_WORLD_MARGIN_RATIO = 1.0


def _world_to_canvas(
    x: float,
    y: float,
    min_x: float,
    min_y: float,
    scale_px_per_m: float,
    margin_px: int,
    panel_height: int,
) -> Tuple[int, int]:
    canvas_x = int(round(margin_px + (x - min_x) * scale_px_per_m))
    # OpenCV image coordinates increase downward, so world Y is flipped.
    canvas_y = int(
        round(panel_height - margin_px - (y - min_y) * scale_px_per_m)
    )
    return canvas_x, canvas_y


def _compute_topview_transform(
    all_tags: Mapping[int, TagDefinition],
    panel_width: int,
    panel_height: int,
    margin_px: int,
) -> Tuple[float, float, float]:
    if not all_tags:
        return 0.0, 0.0, 1.0

    xs = [tag.x for tag in all_tags.values()]
    ys = [tag.y for tag in all_tags.values()]

    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)

    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)

    # Add 100% world-space padding so the preview includes a full extra
    # map-width/map-height worth of margin around the known tag extents.
    min_x -= span_x * TOPVIEW_WORLD_MARGIN_RATIO
    max_x += span_x * TOPVIEW_WORLD_MARGIN_RATIO
    min_y -= span_y * TOPVIEW_WORLD_MARGIN_RATIO
    max_y += span_y * TOPVIEW_WORLD_MARGIN_RATIO

    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)

    drawable_w = max(panel_width - 2 * margin_px, 1)
    drawable_h = max(panel_height - 2 * margin_px, 1)
    scale_px_per_m = min(drawable_w / span_x, drawable_h / span_y)

    if scale_px_per_m <= 0:
        scale_px_per_m = 1.0

    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    half_w_m = (panel_width / 2.0 - margin_px) / scale_px_per_m
    half_h_m = (panel_height / 2.0 - margin_px) / scale_px_per_m

    return center_x - half_w_m, center_y - half_h_m, scale_px_per_m


def _draw_topview_panel(
    panel: np.ndarray,
    all_tags: Mapping[int, TagDefinition],
    detections: Iterable,
    pose: Any,
    min_x: float,
    min_y: float,
    scale_px_per_m: float,
) -> None:
    panel_h, panel_w = panel.shape[:2]
    margin_px = 24
    detected_ids = {det.tag_id for det in detections}

    panel[:] = (24, 24, 24)
    cv2.rectangle(panel, (0, 0), (panel_w - 1, panel_h - 1), (60, 60, 60), 1)
    cv2.putText(
        panel,
        "Top View",
        (14, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (230, 230, 230),
        2,
    )

    for tag_id, tag in all_tags.items():
        px, py = _world_to_canvas(
            tag.x,
            tag.y,
            min_x,
            min_y,
            scale_px_per_m,
            margin_px,
            panel_h,
        )

        if tag_id in detected_ids:
            color = (50, 210, 50)
            thickness = 3
        else:
            color = (110, 110, 110)
            thickness = 2

        tag_line_half = 14
        dx = int(round(tag_line_half * math.cos(tag.yaw)))
        dy = int(round(tag_line_half * math.sin(tag.yaw)))
        start_pt = (px - dx, py + dy)
        end_pt = (px + dx, py - dy)
        cv2.arrowedLine(panel, start_pt, end_pt, color, thickness, tipLength=0.35)
        cv2.circle(panel, (px, py), 2, color, -1)
        cv2.putText(
            panel,
            str(tag_id),
            (px + 10, py - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (220, 220, 220),
            1,
        )

    cam_x, cam_y = _world_to_canvas(
        pose.x,
        pose.y,
        min_x,
        min_y,
        scale_px_per_m,
        margin_px,
        panel_h,
    )
    stale_pose = pose.confidence <= 0.0
    cam_color = (70, 140, 220) if stale_pose else (0, 180, 255)
    cv2.circle(panel, (cam_x, cam_y), 9, cam_color, -1)

    heading_len = 28
    # In this demo convention, yaw=0 means camera is facing directly at the tag.
    camera_heading = pose.yaw
    end_x = int(round(cam_x + heading_len * math.cos(camera_heading)))
    end_y = int(round(cam_y - heading_len * math.sin(camera_heading)))
    cv2.arrowedLine(panel, (cam_x, cam_y), (end_x, end_y), cam_color, 2, tipLength=0.28)

    cv2.putText(
        panel,
        f"Detected: {len(detected_ids)}/{len(all_tags)}",
        (14, panel_h - 34),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (230, 230, 230),
        1,
    )
    pose_state = "Pose: stale" if stale_pose else "Pose: live"
    cv2.putText(
        panel,
        pose_state,
        (14, panel_h - 12),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        cam_color,
        1,
    )


def _draw_individual_pose_arrows(
    panel: np.ndarray,
    individual_poses: Mapping[int, Any],
    min_x: float,
    min_y: float,
    scale_px_per_m: float,
) -> None:
    panel_h = panel.shape[0]
    margin_px = 24
    overlay = panel.copy()

    for tag_id, pose in individual_poses.items():
        arrow_color = (
            60 + (tag_id * 70) % 160,
            100 + (tag_id * 45) % 120,
            180 + (tag_id * 35) % 70,
        )
        cam_x, cam_y = _world_to_canvas(
            pose.x,
            pose.y,
            min_x,
            min_y,
            scale_px_per_m,
            margin_px,
            panel_h,
        )

        heading_len = 24
        end_x = int(round(cam_x + heading_len * math.cos(pose.yaw)))
        end_y = int(round(cam_y - heading_len * math.sin(pose.yaw)))
        cv2.circle(overlay, (cam_x, cam_y), 6, arrow_color, -1)
        cv2.arrowedLine(
            overlay,
            (cam_x, cam_y),
            (end_x, end_y),
            arrow_color,
            2,
            tipLength=0.28,
        )

    cv2.addWeighted(overlay, 0.35, panel, 0.65, 0.0, dst=panel)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Live AprilTag localization demo")
    parser.add_argument("--camera-index", type=int, default=0, help="OpenCV camera index")
    parser.add_argument(
        "--calibration",
        type=Path,
        default=Path("config/camera_calibration_rpi.yaml"),
        help="Path to camera calibration YAML",
    )
    parser.add_argument(
        "--tag-map",
        type=Path,
        default=Path("config/tag_map_example.json"),
        help="Path to tag map JSON",
    )
    parser.add_argument(
        "--window-name",
        type=str,
        default="Live Localization",
        help="OpenCV display window name",
    )
    return parser


def _draw_detections(frame, detections) -> None:
    for det in detections:
        corners = det.corners.astype(int)
        for i in range(4):
            p1 = tuple(corners[i])
            p2 = tuple(corners[(i + 1) % 4])
            cv2.line(frame, p1, p2, (0, 255, 0), 2)

        center = tuple(det.center.astype(int))
        cv2.circle(frame, center, 4, (0, 255, 255), -1)
        cv2.putText(
            frame,
            f"id={det.tag_id}",
            (center[0] + 8, center[1] - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            2,
        )


def _overlay_pose(frame, x: float, y: float, yaw_rad: float, confidence: float) -> None:
    yaw_deg = math.degrees(yaw_rad)
    cv2.rectangle(frame, (8, 8), (460, 98), (0, 0, 0), -1)
    cv2.putText(
        frame,
        f"Pose X={x:.3f} m  Y={y:.3f} m",
        (16, 34),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
    )
    cv2.putText(
        frame,
        f"Yaw={yaw_rad:.3f} rad ({yaw_deg:.1f} deg)",
        (16, 62),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
    )
    cv2.putText(
        frame,
        f"Confidence={confidence:.3f}",
        (16, 90),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 255, 255),
        2,
    )


def main() -> None:
    args = _build_parser().parse_args()

    if not args.calibration.exists():
        raise FileNotFoundError(f"Calibration file not found: {args.calibration}")
    if not args.tag_map.exists():
        raise FileNotFoundError(f"Tag map file not found: {args.tag_map}")

    calibration = CameraCalibration.from_yaml(str(args.calibration))
    tag_map = AprilTagMap.from_json(str(args.tag_map))
    estimator = PoseEstimator(calibration, tag_map)

    cap = cv2.VideoCapture(args.camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera index {args.camera_index}")

    logger.info("Live localization started.")
    logger.info("Press 'q' to quit.")

    all_tags = estimator.tag_map.get_all_tags()
    if not all_tags:
        logger.warning("Tag map is empty; top-view will only show camera pose.")

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                continue

            # PoseEstimator tracks last known pose internally when tags drop out.
            pose, individual_poses, detections = estimator.estimate_pose_details(frame)

            _draw_detections(frame, detections)
            _overlay_pose(frame, pose.x, pose.y, pose.yaw, pose.confidence)

            cv2.putText(
                frame,
                f"Detected tags: {len(detections)}",
                (16, frame.shape[0] - 16),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 255),
                2,
            )

            panel_h = frame.shape[0]
            panel_w = TOPVIEW_WIDTH_PX
            topview = np.zeros((panel_h, panel_w, 3), dtype=frame.dtype)

            min_x, min_y, scale_px_per_m = _compute_topview_transform(
                all_tags,
                panel_w,
                panel_h,
                margin_px=24,
            )
            _draw_topview_panel(
                topview,
                all_tags,
                detections,
                pose,
                min_x,
                min_y,
                scale_px_per_m,
            )
            _draw_individual_pose_arrows(
                topview,
                individual_poses,
                min_x,
                min_y,
                scale_px_per_m,
            )

            composite = cv2.hconcat([frame, topview])

            cv2.imshow(args.window_name, composite)
            if (cv2.waitKey(1) & 0xFF) == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
