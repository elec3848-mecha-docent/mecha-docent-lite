"""Live AprilTag localization plus serial navigation demo.

Usage:
    python live_navigation_demo.py --port /dev/ttyUSB0

Runtime CLI commands (stdin):
    target <x> <y> <yaw>
    <x> <y> <yaw>
    cancel
    help

Controls:
    q: quit OpenCV window
"""

from __future__ import annotations

import argparse
import logging
import math
import queue
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Tuple

import cv2
import numpy as np

try:
    from picamera2 import Picamera2
except ImportError:
    Picamera2 = None

# Consume the estimator as an external library from the local checkout.
import sys

LIB_ROOT = Path(__file__).parent / "apriltag-pose-estimator"
if str(LIB_ROOT) not in sys.path:
    sys.path.insert(0, str(LIB_ROOT))

from apriltag_pose_estimator import AprilTagMap, CameraCalibration, PoseEstimator
from apriltag_pose_estimator.tag_map import TagDefinition

from serial_bridge import SerialBridge, TargetAckResult

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
    canvas_y = int(round(panel_height - margin_px - (y - min_y) * scale_px_per_m))
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

    min_x -= span_x * TOPVIEW_WORLD_MARGIN_RATIO
    max_x += span_x * TOPVIEW_WORLD_MARGIN_RATIO
    min_y -= span_y * TOPVIEW_WORLD_MARGIN_RATIO
    max_y += span_y * TOPVIEW_WORLD_MARGIN_RATIO

    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)

    drawable_w = max(panel_width - 2 * margin_px, 1)
    drawable_h = max(panel_height - 2 * margin_px, 1)
    scale_px_per_m = min(drawable_w / span_x, drawable_h / span_y)
    if scale_px_per_m <= 0.0:
        scale_px_per_m = 1.0

    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    half_w_m = (panel_width / 2.0 - margin_px) / scale_px_per_m
    half_h_m = (panel_height / 2.0 - margin_px) / scale_px_per_m

    return center_x - half_w_m, center_y - half_h_m, scale_px_per_m


def _draw_detections(frame: np.ndarray, detections: Iterable[Any]) -> None:
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


def _draw_pose_overlay(
    frame: np.ndarray,
    pose: Any,
    detections_count: int,
    target: Optional[Tuple[float, float, float]],
    last_ack: Optional[TargetAckResult],
    status: Optional[dict],
    correction_age_s: float,
) -> None:
    cv2.rectangle(frame, (8, 8), (580, 190), (0, 0, 0), -1)

    yaw_deg = math.degrees(pose.yaw)
    cv2.putText(
        frame,
        f"Pose X={pose.x:.3f}m  Y={pose.y:.3f}m  Yaw={yaw_deg:.1f}deg",
        (16, 34),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.65,
        (255, 255, 255),
        2,
    )

    cv2.putText(
        frame,
        f"Detections={detections_count}  Confidence={pose.confidence:.3f}",
        (16, 62),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.62,
        (255, 255, 255),
        2,
    )

    if target is None:
        target_text = "Target: none"
    else:
        target_text = f"Target: x={target[0]:.2f}, y={target[1]:.2f}, yaw={target[2]:.2f}"
    cv2.putText(
        frame,
        target_text,
        (16, 90),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.56,
        (220, 220, 220),
        1,
    )

    if last_ack is None:
        ack_text = "Last ACK: none"
        ack_color = (180, 180, 180)
    elif last_ack.ok:
        ack_text = f"Last ACK: id={last_ack.command_id}"
        ack_color = (60, 220, 80)
    else:
        ack_text = f"Last NACK: id={last_ack.command_id} reason={last_ack.reason}"
        ack_color = (80, 80, 255)
    cv2.putText(
        frame,
        ack_text,
        (16, 118),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.56,
        ack_color,
        1,
    )

    if status:
        err_xy = float(status.get("err_xy", 0.0))
        err_yaw = float(status.get("err_yaw", 0.0))
        reached = int(status.get("target_reached", 0))
        stale_ms = int(status.get("stale_ms", -1))
        nav_line = (
            f"Arduino err_xy={err_xy:.3f} err_yaw={err_yaw:.3f} "
            f"reached={reached} stale_ms={stale_ms}"
        )
    else:
        nav_line = "Arduino status: waiting"

    cv2.putText(
        frame,
        nav_line,
        (16, 146),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.56,
        (220, 220, 220),
        1,
    )

    cv2.putText(
        frame,
        f"Last pose correction: {correction_age_s:.2f}s ago",
        (16, 174),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.56,
        (220, 220, 220),
        1,
    )


def _draw_topview_panel(
    panel: np.ndarray,
    all_tags: Mapping[int, TagDefinition],
    detections: Iterable[Any],
    pose: Any,
    target: Optional[Tuple[float, float, float]],
    min_x: float,
    min_y: float,
    scale_px_per_m: float,
) -> None:
    panel_h, panel_w = panel.shape[:2]
    margin_px = 24
    detected_ids = {det.tag_id for det in detections}

    panel[:] = (24, 24, 24)
    cv2.rectangle(panel, (0, 0), (panel_w - 1, panel_h - 1), (60, 60, 60), 1)
    cv2.putText(panel, "Top View", (14, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (230, 230, 230), 2)

    for tag_id, tag in all_tags.items():
        px, py = _world_to_canvas(tag.x, tag.y, min_x, min_y, scale_px_per_m, margin_px, panel_h)
        color = (50, 210, 50) if tag_id in detected_ids else (110, 110, 110)
        thickness = 3 if tag_id in detected_ids else 2

        tag_line_half = 14
        dx = int(round(tag_line_half * math.cos(tag.yaw)))
        dy = int(round(tag_line_half * math.sin(tag.yaw)))
        start_pt = (px - dx, py + dy)
        end_pt = (px + dx, py - dy)
        cv2.arrowedLine(panel, start_pt, end_pt, color, thickness, tipLength=0.35)
        cv2.circle(panel, (px, py), 2, color, -1)
        cv2.putText(panel, str(tag_id), (px + 10, py - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1)

    cam_x, cam_y = _world_to_canvas(pose.x, pose.y, min_x, min_y, scale_px_per_m, margin_px, panel_h)
    cv2.circle(panel, (cam_x, cam_y), 9, (0, 180, 255), -1)

    heading_len = 28
    end_x = int(round(cam_x + heading_len * math.cos(pose.yaw)))
    end_y = int(round(cam_y - heading_len * math.sin(pose.yaw)))
    cv2.arrowedLine(panel, (cam_x, cam_y), (end_x, end_y), (0, 180, 255), 2, tipLength=0.28)

    if target is not None:
        tx, ty = _world_to_canvas(target[0], target[1], min_x, min_y, scale_px_per_m, margin_px, panel_h)
        cv2.circle(panel, (tx, ty), 9, (255, 120, 40), 2)
        target_heading_len = 22
        tx2 = int(round(tx + target_heading_len * math.cos(target[2])))
        ty2 = int(round(ty - target_heading_len * math.sin(target[2])))
        cv2.arrowedLine(panel, (tx, ty), (tx2, ty2), (255, 120, 40), 2, tipLength=0.25)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Live AprilTag + serial navigation demo")
    parser.add_argument("--camera-index", type=int, default=0, help="OpenCV camera index")
    parser.add_argument(
        "--calibration",
        type=Path,
        default=Path("apriltag-pose-estimator/config/camera_calibration_rpi.yaml"),
    )
    parser.add_argument(
        "--tag-map",
        type=Path,
        default=Path("apriltag-pose-estimator/config/tag_map_example.json"),
    )
    parser.add_argument("--window-name", type=str, default="Live Navigation")
    parser.add_argument("--port", type=str, required=True, help="Serial port, e.g. COM6 or /dev/ttyUSB0")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--ack-timeout", type=float, default=2.0)
    parser.add_argument("--correction-rate-hz", type=float, default=15.0)
    parser.add_argument(
        "--picamera2",
        action="store_true",
        help="Use PiCamera2 instead of OpenCV VideoCapture",
    )
    parser.add_argument(
        "--rotate-180",
        action="store_false",
        dest="rotate_180",
        help="Disable 180° frame rotation (enabled by default)",
    )
    parser.set_defaults(rotate_180=True)
    return parser


def _stdin_reader(stop_event: threading.Event, command_queue: queue.Queue[str]) -> None:
    logger.info("CLI ready. Enter: target <x> <y> <yaw>  or: cancel")
    while not stop_event.is_set():
        try:
            line = input().strip()
        except EOFError:
            stop_event.set()
            return

        if not line:
            continue
        command_queue.put(line)


def _parse_target_line(line: str) -> Optional[Tuple[float, float, float]]:
    parts = line.split()
    if len(parts) == 4 and parts[0].lower() == "target":
        try:
            return float(parts[1]), float(parts[2]), float(parts[3])
        except ValueError:
            return None

    if len(parts) == 3:
        try:
            return float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            return None

    return None


def main() -> None:
    args = _build_parser().parse_args()

    if not args.calibration.exists():
        raise FileNotFoundError(f"Calibration file not found: {args.calibration}")
    if not args.tag_map.exists():
        raise FileNotFoundError(f"Tag map file not found: {args.tag_map}")

    calibration = CameraCalibration.from_yaml(str(args.calibration))
    tag_map = AprilTagMap.from_json(str(args.tag_map))
    estimator = PoseEstimator(calibration, tag_map, rotate_180=args.rotate_180)
    all_tags = estimator.tag_map.get_all_tags()

    bridge = SerialBridge(args.port, baudrate=args.baudrate, ack_timeout_s=args.ack_timeout)
    bridge.open()

    if args.picamera2:
        if Picamera2 is None:
            bridge.close()
            raise RuntimeError("picamera2 package is not installed.")
        pc2 = Picamera2()
        pc2.start()
    else:
        cap = cv2.VideoCapture(args.camera_index)
        if not cap.isOpened():
            bridge.close()
            raise RuntimeError(f"Could not open camera index {args.camera_index}")

    command_queue: queue.Queue[str] = queue.Queue()
    stop_event = threading.Event()
    input_thread = threading.Thread(target=_stdin_reader, args=(stop_event, command_queue), daemon=True)
    input_thread.start()

    logger.info("Live navigation started using %s. Press q in video window to quit.", "PiCamera2" if args.picamera2 else "OpenCV")

    current_target: Optional[Tuple[float, float, float]] = None
    last_ack: Optional[TargetAckResult] = None
    correction_period_s = 1.0 / max(args.correction_rate_hz, 1e-3)
    last_correction_sent_ts = 0.0

    try:
        while True:
            if args.picamera2:
                frame = pc2.capture_array()
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            else:
                ok, frame = cap.read()
                if not ok:
                    continue

            if args.rotate_180:
                frame = cv2.rotate(frame, cv2.ROTATE_180)

            pose, _, detections = estimator.estimate_pose_details(frame)

            now = time.time()
            if now - last_correction_sent_ts >= correction_period_s:
                bridge.send_pose_correction(pose.x, pose.y, pose.yaw, pose.confidence)
                last_correction_sent_ts = now

            bridge.poll()

            while True:
                try:
                    command = command_queue.get_nowait()
                except queue.Empty:
                    break

                cmd_lower = command.lower()
                if cmd_lower in {"help", "h", "?"}:
                    logger.info("Commands: target <x> <y> <yaw> | <x> <y> <yaw> | cancel")
                    continue

                if cmd_lower in {"cancel", "stop"}:
                    bridge.send_cancel_target()
                    current_target = None
                    logger.info("Sent cancel_target")
                    continue

                parsed_target = _parse_target_line(command)
                if parsed_target is None:
                    logger.warning("Invalid command: %s", command)
                    continue

                ack = bridge.send_target_and_wait_ack(
                    parsed_target[0],
                    parsed_target[1],
                    parsed_target[2],
                    timeout_s=args.ack_timeout,
                )
                last_ack = ack
                if ack.ok:
                    current_target = parsed_target
                    logger.info("Target accepted id=%d", ack.command_id)
                else:
                    logger.warning("Target rejected id=%d reason=%s", ack.command_id, ack.reason)

            status = bridge.last_status
            _draw_detections(frame, detections)
            _draw_pose_overlay(
                frame,
                pose,
                detections_count=len(detections),
                target=current_target,
                last_ack=last_ack,
                status=status,
                correction_age_s=max(0.0, time.time() - last_correction_sent_ts),
            )

            panel_h = frame.shape[0]
            panel_w = TOPVIEW_WIDTH_PX
            topview = np.zeros((panel_h, panel_w, 3), dtype=frame.dtype)
            min_x, min_y, scale = _compute_topview_transform(all_tags, panel_w, panel_h, margin_px=24)
            _draw_topview_panel(
                topview,
                all_tags,
                detections,
                pose,
                current_target,
                min_x,
                min_y,
                scale,
            )

            composite = cv2.hconcat([frame, topview])
            cv2.imshow(args.window_name, composite)

            if (cv2.waitKey(1) & 0xFF) == ord("q"):
                break
    finally:
        stop_event.set()
        if args.picamera2:
            pc2.stop()
        else:
            cap.release()
        bridge.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
