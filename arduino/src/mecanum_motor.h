#ifndef MECANUM_MOTOR_H
#define MECANUM_MOTOR_H

#include "imu_manager.h"

/**
 * @class MecanumMotor
 * @brief Handles kinematic transformation and hardware control for a 4-wheel mecanum base.
 * 
 * Supports translation (X, Y) and rotation (Yaw) simultaneously.
 * Includes optional IMU-based closed-loop trim to ensure straight driving.
 */
class MecanumMotor {
public:
    MecanumMotor();

    /**
     * @brief Initialize hardware pins and IMU.
     * @return true if IMU was successfully initialized (if used).
     */
    bool begin();

    /**
     * @brief Move the robot using normalized velocity components.
     * 
     * @param vx Forward velocity [-1.0, 1.0]
     * @param vy Leftward velocity [-1.0, 1.0] (Mecanum lateral shift)
     * @param wz Angular velocity [-1.0, 1.0] (Counter-clockwise positive)
     */
    void move(float vx, float vy, float wz);

private:
    struct WheelPins {
        uint8_t pwm;
        uint8_t backward;
        uint8_t forward;
    };

    static constexpr int kWheelCount = 4;
    static constexpr int kFl = 0;
    static constexpr int kFr = 1;
    static constexpr int kBl = 2;
    static constexpr int kBr = 3;

    WheelPins _pins[kWheelCount];
    ImuManager _imu;
    bool _initialized;
    bool _imu_ready;
    uint32_t _last_update_us;
    float _last_wz_rad_s;
    int _yaw_side_nudge_pwm;

    void setWheelOutput(int wheel, int signed_pwm);
    void computeNormalizedWheelMix(float vx, float vy, float wz, float out_mix[kWheelCount]);
    int normalizedToPwm(float norm_cmd);
    void updateYawSideNudge(float target_wz_norm, float measured_wz_rad_s, bool moving);
    bool isMoveCommandActive(float vx, float vy, float wz);
    void applyWheelOutputsWithYawNudge(const int base_pwm[kWheelCount]);
};

#endif
