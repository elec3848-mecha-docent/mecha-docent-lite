"""Lightweight EKF for planar robot localization with velocity states."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

import numpy as np

from ..core.fusion import PoseEstimate
from . import utils


@dataclass
class KalmanTuning:
    process_pos_noise: float = 0.015
    process_yaw_noise: float = 0.06
    process_vel_noise: float = 0.40
    motion_meas_vel_noise: float = 0.20
    motion_meas_wz_noise: float = 0.45
    vision_pos_noise: float = 0.05
    vision_yaw_noise: float = math.radians(7.0)


class PlanarPoseKalmanFilter:
    """EKF state: [x, y, yaw, vx, vy, wz]."""

    def __init__(self, tuning: Optional[KalmanTuning] = None) -> None:
        self.tuning = tuning or KalmanTuning()
        self.x = np.zeros((6, 1), dtype=float)
        self.P = np.eye(6, dtype=float) * 0.25

    def reset(self, pose: PoseEstimate) -> None:
        self.x[:, 0] = 0.0
        self.x[0, 0] = pose.x
        self.x[1, 0] = pose.y
        self.x[2, 0] = pose.yaw
        self.P = np.eye(6, dtype=float) * 0.1

    def predict(self, dt: float) -> None:
        if dt <= 0.0:
            return

        F = np.eye(6, dtype=float)
        F[0, 3] = dt
        F[1, 4] = dt
        F[2, 5] = dt

        self.x = F @ self.x
        self.x[2, 0] = utils.normalize_angle(float(self.x[2, 0]))

        q_pos = self.tuning.process_pos_noise
        q_yaw = self.tuning.process_yaw_noise
        q_vel = self.tuning.process_vel_noise
        Q = np.diag(
            [
                q_pos * dt,
                q_pos * dt,
                q_yaw * dt,
                q_vel * dt,
                q_vel * dt,
                q_vel * dt,
            ]
        )
        self.P = F @ self.P @ F.T + Q

    def update_motion(self, vx: Optional[float], vy: Optional[float], wz: Optional[float]) -> None:
        rows = []
        z_vals = []
        variances = []

        if vx is not None:
            rows.append([0.0, 0.0, 0.0, 1.0, 0.0, 0.0])
            z_vals.append(vx)
            variances.append(self.tuning.motion_meas_vel_noise)

        if vy is not None:
            rows.append([0.0, 0.0, 0.0, 0.0, 1.0, 0.0])
            z_vals.append(vy)
            variances.append(self.tuning.motion_meas_vel_noise)

        if wz is not None:
            rows.append([0.0, 0.0, 0.0, 0.0, 0.0, 1.0])
            z_vals.append(wz)
            variances.append(self.tuning.motion_meas_wz_noise)

        if not rows:
            return

        H = np.asarray(rows, dtype=float)
        z = np.asarray(z_vals, dtype=float).reshape((-1, 1))
        R = np.diag(variances)
        self._update_linear(H, z, R, yaw_row_index=None)

    def update_vision(self, pose: PoseEstimate, confidence: float) -> None:
        c = max(min(float(confidence), 1.0), 0.0)
        conf_scale = max(0.15, 1.0 - 0.8 * c)

        H = np.array(
            [
                [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
            ],
            dtype=float,
        )
        z = np.array([[pose.x], [pose.y], [pose.yaw]], dtype=float)
        R = np.diag(
            [
                (self.tuning.vision_pos_noise * conf_scale) ** 2,
                (self.tuning.vision_pos_noise * conf_scale) ** 2,
                (self.tuning.vision_yaw_noise * conf_scale) ** 2,
            ]
        )
        self._update_linear(H, z, R, yaw_row_index=2)

    def get_pose(self, confidence: float) -> PoseEstimate:
        base_conf = max(min(float(confidence), 1.0), 0.0)
        trace_xy = max(float(self.P[0, 0] + self.P[1, 1]), 1e-6)
        cov_penalty = 1.0 / (1.0 + 5.0 * trace_xy)
        conf = max(0.0, min(1.0, base_conf * cov_penalty))
        return PoseEstimate(
            x=float(self.x[0, 0]),
            y=float(self.x[1, 0]),
            yaw=float(utils.normalize_angle(float(self.x[2, 0]))),
            confidence=conf,
        )

    def _update_linear(self, H: np.ndarray, z: np.ndarray, R: np.ndarray, yaw_row_index: Optional[int]) -> None:
        y = z - (H @ self.x)
        if yaw_row_index is not None:
            y[yaw_row_index, 0] = utils.normalize_angle(float(y[yaw_row_index, 0]))

        S = H @ self.P @ H.T + R
        K = self.P @ H.T @ np.linalg.inv(S)

        self.x = self.x + K @ y
        self.x[2, 0] = utils.normalize_angle(float(self.x[2, 0]))

        I = np.eye(6, dtype=float)
        self.P = (I - K @ H) @ self.P
