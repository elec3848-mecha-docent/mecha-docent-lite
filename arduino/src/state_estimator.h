#ifndef STATE_ESTIMATOR_H
#define STATE_ESTIMATOR_H

#include <Arduino.h>
#include "config.h"

/**
 * Planar EKF state estimator for mecanum robot.
 *
 * State:      [x_m, y_m, yaw_rad]
 * Prediction: body-frame commanded velocity transformed to global frame.
 * Correction: direct pose measurement from AprilTag pipeline with
 *             confidence-scaled measurement noise.
 *
 * All matrix operations use float32 3×3 fixed arrays (row-major) — no
 * dynamic allocation, safe on AVR Mega 2560.
 */
class StateEstimator {
public:
    StateEstimator();

    /** Reset to a known pose and reinitialise covariance to a small value. */
    void reset(float x_m, float y_m, float yaw_rad);

    /**
     * Predict state forward using body-frame velocities.
     * Call once per motor control tick.
     *
     * @param vx_body  Forward velocity (m/s, body frame).
     * @param vy_body  Lateral velocity (m/s, body frame, positive = left).
     * @param wz       Yaw rate (rad/s).
     * @param dt_s     Time step (seconds).
     */
    void predict(float vx_body, float vy_body, float wz, float dt_s);

    /**
     * Correct state from an external pose measurement.
     *
     * @param x_m        Measured global X (metres).
     * @param y_m        Measured global Y (metres).
     * @param yaw_rad    Measured global yaw (radians).
     * @param confidence Measurement confidence in [0, 1]. Lower → higher noise.
     */
    void correct(float x_m, float y_m, float yaw_rad, float confidence);

    float getX()   const { return _x; }
    float getY()   const { return _y; }
    float getYaw() const { return _yaw; }

    /**
     * Milliseconds since the last call to correct().
     * Returns UINT32_MAX if correct() has never been called.
     */
    uint32_t getStalenessMs() const;

    bool isInitialized() const { return _initialized; }

private:
    float    _x, _y, _yaw;
    float    _P[9];             // 3×3 covariance, row-major [row*3 + col]
    uint32_t _last_correct_ms;
    bool     _initialized;

    static float _normalize_angle(float a);
    static void  _mat3_mul(const float A[9], const float B[9], float out[9]);
    static bool  _mat3_inv(const float M[9], float out[9]);
};

#endif // STATE_ESTIMATOR_H
