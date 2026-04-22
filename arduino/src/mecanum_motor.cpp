#include "mecanum_motor.h"

#include <Arduino.h>
#include <math.h>

#include "config.h"
#include "imu_manager.h"

namespace {
float clampf(float v, float lo, float hi) {
    if (v < lo) {
        return lo;
    }
    if (v > hi) {
        return hi;
    }
    return v;
}
} // namespace

MecanumMotor::MecanumMotor()
    : _initialized(false),
      _imu_ready(false),
      _last_update_us(0),
      _last_wz_rad_s(0.0f),
      _yaw_side_nudge_pwm(0) {
    
    _pins[kFl] = {FRONT_LEFT_PWM, FRONT_LEFT_BACKWARD, FRONT_LEFT_FORWARD};
    _pins[kFr] = {FRONT_RIGHT_PWM, FRONT_RIGHT_BACKWARD, FRONT_RIGHT_FORWARD};
    _pins[kBl] = {BACK_LEFT_PWM, BACK_LEFT_BACKWARD, BACK_LEFT_FORWARD};
    _pins[kBr] = {BACK_RIGHT_PWM, BACK_RIGHT_BACKWARD, BACK_RIGHT_FORWARD};
}

bool MecanumMotor::begin() {
    if (_initialized) {
        return _imu_ready;
    }

    for (int i = 0; i < kWheelCount; ++i) {
        pinMode(_pins[i].pwm, OUTPUT);
        pinMode(_pins[i].backward, OUTPUT);
        pinMode(_pins[i].forward, OUTPUT);
        setWheelOutput(i, 0);
    }

    _imu_ready = _imu.begin();
    _last_wz_rad_s = 0.0f;
    _yaw_side_nudge_pwm = 0;
    _last_update_us = micros();
    _initialized = true;

    return _imu_ready;
}

void MecanumMotor::move(float vx, float vy, float wz) {
    if (!_initialized) {
        begin();
    }

    const uint32_t now_us = micros();
    const uint32_t elapsed_us = now_us - _last_update_us;
    if (elapsed_us < MOTOR_CONTROL_PERIOD_US) {
        return;
    }

    _last_update_us = now_us;

    float vx_cmd = clampf(vx, -1.0f, 1.0f);
    float vy_cmd = clampf(vy, -1.0f, 1.0f);
    float wz_cmd = clampf(wz, -1.0f, 1.0f);

    float measured_wz_rad_s = _last_wz_rad_s;

    if (USE_IMU_YAW_TRIM && _imu_ready && _imu.update()) {
        measured_wz_rad_s = _imu.getGyroZ();
        _last_wz_rad_s = measured_wz_rad_s;
    }

    float wheel_mix[kWheelCount] = {0.0f, 0.0f, 0.0f, 0.0f};
    computeNormalizedWheelMix(vx_cmd, vy_cmd, wz_cmd, wheel_mix);

    int base_pwm[kWheelCount] = {0, 0, 0, 0};
    for (int i = 0; i < kWheelCount; ++i) {
        base_pwm[i] = normalizedToPwm(wheel_mix[i]);
    }

    if (USE_IMU_YAW_TRIM) {
        updateYawSideNudge(wz_cmd, measured_wz_rad_s, isMoveCommandActive(vx_cmd, vy_cmd, wz_cmd));
    } else {
        _yaw_side_nudge_pwm = 0;
    }

    applyWheelOutputsWithYawNudge(base_pwm);
}

void MecanumMotor::setWheelOutput(int wheel, int signed_pwm) {
    signed_pwm = constrain(signed_pwm, -MOTOR_PWM_MAX, MOTOR_PWM_MAX);

    if (signed_pwm > 0) {
        digitalWrite(_pins[wheel].backward, LOW);
        digitalWrite(_pins[wheel].forward, HIGH);
        analogWrite(_pins[wheel].pwm, signed_pwm);
        return;
    }

    if (signed_pwm < 0) {
        digitalWrite(_pins[wheel].backward, HIGH);
        digitalWrite(_pins[wheel].forward, LOW);
        analogWrite(_pins[wheel].pwm, -signed_pwm);
        return;
    }

    digitalWrite(_pins[wheel].backward, LOW);
    digitalWrite(_pins[wheel].forward, LOW);
    analogWrite(_pins[wheel].pwm, 0);
}

void MecanumMotor::computeNormalizedWheelMix(float vx, float vy, float wz, float out_mix[kWheelCount]) {
    out_mix[kFl] = vx - vy + wz;
    out_mix[kFr] = vx + vy - wz;
    out_mix[kBl] = vx + vy + wz;
    out_mix[kBr] = vx - vy - wz;

    float max_abs = 1.0f;
    for (int i = 0; i < kWheelCount; ++i) {
        const float abs_val = fabsf(out_mix[i]);
        if (abs_val > max_abs) {
            max_abs = abs_val;
        }
    }

    for (int i = 0; i < kWheelCount; ++i) {
        out_mix[i] /= max_abs;
    }
}

int MecanumMotor::normalizedToPwm(float norm_cmd) {
    const float mag = fabsf(norm_cmd);
    if (mag < COMMAND_DEADBAND) {
        return 0;
    }

    const float pwm_span = static_cast<float>(MOTOR_PWM_MAX - MOTOR_PWM_MIN_ACTIVE);
    int pwm = static_cast<int>(roundf(MOTOR_PWM_MIN_ACTIVE + (mag * pwm_span)));
    pwm = constrain(pwm, MOTOR_PWM_MIN_ACTIVE, MOTOR_PWM_MAX);

    return (norm_cmd >= 0.0f) ? pwm : -pwm;
}

void MecanumMotor::updateYawSideNudge(float target_wz_norm, float measured_wz_rad_s, bool moving) {
    if (!moving || !_imu_ready) {
        _yaw_side_nudge_pwm = 0;
        return;
    }

    const float measured_wz_norm = clampf(measured_wz_rad_s / YAW_RATE_NORM_RAD_S, -1.0f, 1.0f);
    const float yaw_error = target_wz_norm - measured_wz_norm;

    if (yaw_error > YAW_RATE_ERROR_DEADBAND) {
        _yaw_side_nudge_pwm -= YAW_NUDGE_PWM_STEP;
    } else if (yaw_error < -YAW_RATE_ERROR_DEADBAND) {
        _yaw_side_nudge_pwm += YAW_NUDGE_PWM_STEP;
    } else if (_yaw_side_nudge_pwm > 0) {
        _yaw_side_nudge_pwm -= YAW_NUDGE_PWM_DECAY_STEP;
    } else if (_yaw_side_nudge_pwm < 0) {
        _yaw_side_nudge_pwm += YAW_NUDGE_PWM_DECAY_STEP;
    }

    _yaw_side_nudge_pwm = constrain(_yaw_side_nudge_pwm, -YAW_NUDGE_PWM_MAX, YAW_NUDGE_PWM_MAX);
}

bool MecanumMotor::isMoveCommandActive(float vx, float vy, float wz) {
    return fabsf(vx) >= COMMAND_DEADBAND || fabsf(vy) >= COMMAND_DEADBAND || fabsf(wz) >= COMMAND_DEADBAND;
}

void MecanumMotor::applyWheelOutputsWithYawNudge(const int base_pwm[kWheelCount]) {
    int final_pwm[kWheelCount] = {
        base_pwm[kFl] - _yaw_side_nudge_pwm,
        base_pwm[kFr] + _yaw_side_nudge_pwm,
        base_pwm[kBl] - _yaw_side_nudge_pwm,
        base_pwm[kBr] + _yaw_side_nudge_pwm,
    };

    for (int i = 0; i < kWheelCount; ++i) {
        final_pwm[i] = constrain(final_pwm[i], -MOTOR_PWM_MAX, MOTOR_PWM_MAX);
        setWheelOutput(i, final_pwm[i]);
    }
}