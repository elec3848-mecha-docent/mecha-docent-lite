"""Localization tracker that combines AprilTag vision with IMU/encoder EKF prediction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import time

from ..filtering import utils
from ..core.fusion import PoseEstimate
from ..filtering.kalman_filter import PlanarPoseKalmanFilter
from ..core.pose_estimator import PoseEstimator, TagDetection
from rpi.serial_communication.serial_bridge import ArduinoMecanumBridge, EncoderTelemetry, ImuTelemetry


MODE_TAG_TRACKING = "tag_tracking"
MODE_TAG_LOST_PREDICT = "tag_lost_predict"
MODE_SEARCH_ROTATE = "search_rotate"


@dataclass
class LocalizationTrackerTuning:
    no_tag_timeout_s: float = 1.2
    imu_vision_yaw_blend: float = 0.25
    min_predict_confidence: float = 0.12
    confidence_decay_per_s: float = 0.25


class LocalizationTracker:
    """Runs localization fusion and exposes fallback mode for controller decisions."""

    def __init__(
        self,
        estimator: PoseEstimator,
        bridge: ArduinoMecanumBridge,
        kf: Optional[PlanarPoseKalmanFilter] = None,
        tuning: Optional[LocalizationTrackerTuning] = None,
    ) -> None:
        self._estimator = estimator
        self._bridge = bridge
        self._kf = kf or PlanarPoseKalmanFilter()
        self._tuning = tuning or LocalizationTrackerTuning()

        self._initialized = False
        self._last_step_s: Optional[float] = None
        self._last_tag_seen_s: Optional[float] = None
        self._last_encoder: Optional[EncoderTelemetry] = None
        self._last_encoder_time_s: Optional[float] = None
        self._last_sensor_request_s: Optional[float] = None

    def step(
        self, frame, now_s: Optional[float] = None
    ) -> Tuple[PoseEstimate, str, Dict[str, float], Dict[int, PoseEstimate], List[TagDetection]]:
        now = now_s if now_s is not None else time.monotonic()

        # Keep heartbeat independent from camera-frame timing jitter.
        self._bridge.send_heartbeat(min_interval_s=0.05)

        if self._last_sensor_request_s is None or (now - self._last_sensor_request_s) >= 0.1:
            self._bridge.request_sensor_snapshot()
            self._last_sensor_request_s = now

        # Harvest available serial frames and use cached telemetry snapshots.
        self._bridge.poll_frames()
        encoder = self._bridge.last_telemetry
        imu = self._bridge.last_imu

        dt = 0.0
        if self._last_step_s is not None:
            dt = max(0.0, now - self._last_step_s)
        self._last_step_s = now

        if dt > 0.0:
            self._kf.predict(dt)

        vx_mps, vy_mps, wz_rad_s = self._compute_motion_measurements(encoder, imu, now)
        self._kf.update_motion(vx=vx_mps, vy=vy_mps, wz=wz_rad_s)

        vision_pose, per_tag_poses, detections = self._estimator.estimate_pose_details(frame)

        vision_conf = float(vision_pose.confidence)
        if detections and vision_conf > 0.0:
            stabilized_pose = self._stabilize_yaw_with_imu(vision_pose, imu)
            self._kf.update_vision(stabilized_pose, confidence=stabilized_pose.confidence)

            if not self._initialized:
                self._kf.reset(stabilized_pose)
                self._initialized = True

            self._last_tag_seen_s = now
            fused_pose = self._kf.get_pose(confidence=max(stabilized_pose.confidence, 0.6))

            # Tracker is the sole correction producer: send every tag-tracking frame.
            self._bridge.send_pose_correction(
                fused_pose.x, fused_pose.y, fused_pose.yaw,
                fused_pose.confidence, wait_ack=False,
            )

            info = {
                "vision_confidence": stabilized_pose.confidence,
                "time_since_last_tag_s": 0.0,
            }
            return fused_pose, MODE_TAG_TRACKING, info, per_tag_poses, detections

        if not self._initialized:
            self._kf.reset(vision_pose)
            self._initialized = True

        time_since_last_tag = 0.0
        if self._last_tag_seen_s is None:
            time_since_last_tag = 1e9
        else:
            time_since_last_tag = max(0.0, now - self._last_tag_seen_s)

        if time_since_last_tag <= self._tuning.no_tag_timeout_s:
            decayed_conf = max(
                self._tuning.min_predict_confidence,
                1.0 - self._tuning.confidence_decay_per_s * time_since_last_tag,
            )
            fused_pose = self._kf.get_pose(confidence=decayed_conf)
            info = {
                "vision_confidence": 0.0,
                "time_since_last_tag_s": time_since_last_tag,
            }
            return fused_pose, MODE_TAG_LOST_PREDICT, info, per_tag_poses, detections

        # After timeout, keep reporting EKF pose but with low confidence; controller
        # can switch to search behavior while localization remains internally consistent.
        fused_pose = self._kf.get_pose(confidence=self._tuning.min_predict_confidence)
        info = {
            "vision_confidence": 0.0,
            "time_since_last_tag_s": time_since_last_tag,
        }
        return fused_pose, MODE_SEARCH_ROTATE, info, per_tag_poses, detections

    def _stabilize_yaw_with_imu(self, vision_pose: PoseEstimate, imu: Optional[ImuTelemetry]) -> PoseEstimate:
        if imu is None or imu.status == 0:
            return vision_pose

        alpha = max(0.0, min(1.0, self._tuning.imu_vision_yaw_blend))
        yaw = utils.normalize_angle((1.0 - alpha) * vision_pose.yaw + alpha * imu.yaw_rad)
        return PoseEstimate(
            x=vision_pose.x,
            y=vision_pose.y,
            yaw=yaw,
            confidence=vision_pose.confidence,
        )

    def _compute_motion_measurements(
        self,
        encoder: Optional[EncoderTelemetry],
        imu: Optional[ImuTelemetry],
        now_s: float,
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        vx_mps: Optional[float] = None
        vy_mps: Optional[float] = None
        wz_rad_s: Optional[float] = None

        if encoder is not None:
            if self._last_encoder is not None and self._last_encoder_time_s is not None:
                dt = max(1e-3, now_s - self._last_encoder_time_s)
                dx = encoder.odom_x_m - self._last_encoder.odom_x_m
                dy = encoder.odom_y_m - self._last_encoder.odom_y_m
                dyaw = utils.normalize_angle(encoder.odom_yaw_rad - self._last_encoder.odom_yaw_rad)

                vx_mps = dx / dt
                vy_mps = dy / dt
                wz_rad_s = dyaw / dt

            self._last_encoder = encoder
            self._last_encoder_time_s = now_s

        if imu is not None and imu.status != 0:
            wz_rad_s = imu.gyro_z_mrad_s / 1000.0

        return vx_mps, vy_mps, wz_rad_s
