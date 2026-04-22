#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// IMU
constexpr uint8_t IMU_I2C_ADDR = 0x68;
constexpr uint32_t IMU_I2C_CLOCK_HZ = 400000UL;

// Control timing
constexpr uint32_t SERIAL_BAUD_RATE = 115200UL;
constexpr uint32_t SERIAL_TIMEOUT_MS = 1000UL;
constexpr uint32_t IMU_CONTROL_HZ = 100UL;
constexpr uint32_t IMU_CONTROL_PERIOD_US = 1000000UL / IMU_CONTROL_HZ;
constexpr uint32_t MOTOR_CONTROL_HZ = 50UL;
constexpr uint32_t MOTOR_CONTROL_PERIOD_US = 1000000UL / MOTOR_CONTROL_HZ;

// Simplified normalized control (vx/vy/wz each in [-1.0, 1.0])
constexpr float COMMAND_DEADBAND = 0.02f;
constexpr int MOTOR_PWM_MIN_ACTIVE = 36;
constexpr int MOTOR_PWM_MAX = 255;

// IMU yaw-rate nudging constants
constexpr bool USE_IMU_YAW_TRIM = false;
constexpr float YAW_RATE_NORM_RAD_S = 2.60f;
constexpr float YAW_RATE_ERROR_DEADBAND = 0.03f;
constexpr int YAW_NUDGE_PWM_STEP = 2;
constexpr int YAW_NUDGE_PWM_DECAY_STEP = 1;
constexpr int YAW_NUDGE_PWM_MAX = 70;

// test_tuning constants
constexpr int TUNING_SWEEP_PWM_START = 0;
constexpr int TUNING_SWEEP_PWM_END = 120;
constexpr int TUNING_SWEEP_PWM_STEP = 2;
constexpr uint32_t TUNING_SWEEP_HOLD_MS = 1200UL;
constexpr long TUNING_MOVEMENT_TICK_THRESHOLD = 8;

// DRIVE MOTOR PINS
// Front Right
constexpr uint8_t FRONT_RIGHT_PWM = 5;
constexpr uint8_t FRONT_RIGHT_FORWARD = A5;
constexpr uint8_t FRONT_RIGHT_BACKWARD = A4;
constexpr uint8_t FRONT_RIGHT_EN_A = 2;
constexpr uint8_t FRONT_RIGHT_EN_B = A1;

// Front Left
constexpr uint8_t FRONT_LEFT_PWM = 9;
constexpr uint8_t FRONT_LEFT_FORWARD = 43;
constexpr uint8_t FRONT_LEFT_BACKWARD = 42;
constexpr uint8_t FRONT_LEFT_EN_A = 49;
constexpr uint8_t FRONT_LEFT_EN_B = 3;

// Back Right
constexpr uint8_t BACK_RIGHT_PWM = 8;
constexpr uint8_t BACK_RIGHT_FORWARD = 36;
constexpr uint8_t BACK_RIGHT_BACKWARD = 37;
constexpr uint8_t BACK_RIGHT_EN_A = 19;
constexpr uint8_t BACK_RIGHT_EN_B = 38;

// Back Left
constexpr uint8_t BACK_LEFT_PWM = 12;
constexpr uint8_t BACK_LEFT_FORWARD = 34;
constexpr uint8_t BACK_LEFT_BACKWARD = 35;
constexpr uint8_t BACK_LEFT_EN_A = 31;
constexpr uint8_t BACK_LEFT_EN_B = 18;

// SERVO MOTOR PINS
constexpr uint8_t SERVO_CAM_PAN = 25;
constexpr uint8_t SERVO_CAM_TILT = 28;
constexpr uint8_t SERVO_LASER_PAN = 29;
constexpr uint8_t SERVO_LASER_TILT = 30;

// LASER PIN
constexpr uint8_t LASER_PIN = A10;

#endif