/**
 * @file config.h
 * @brief Central hardware configuration for the MechaDocent-Lite Arduino firmware.
 *
 * All pin assignments, odometry constants, and motion-tuning parameters are
 * collected here so that hardware changes require edits in only one place.
 *
 * Pin groups
 * ----------
 * - Motor driver: PWM, direction, and quadrature encoder pins for four
 *   mecanum wheels (back-left, back-right, front-left, front-right).
 * - Servos: camera pan (25), camera tilt (28), laser pan (29), laser tilt (30).
 * - Laser: A10 (digital output).
 *
 * Odometry constants
 * ------------------
 * - WHEEL_RADIUS_M      : 0.078 m
 * - TICKS_PER_REV       : 650 encoder ticks per wheel revolution
 * - HALF_WHEELBASE_M    : 0.105 m  (half the wheel-to-wheel length)
 * - HALF_TRACKWIDTH_M   : 0.083 m  (half the wheel-to-wheel width)
 *
 * Motion tuning
 * -------------
 * - MOTOR_SYNC_DEADBAND_US  : 40 µs  (encoder pulse tolerance before correction)
 * - MOTOR_SYNC_MAX_CORR     : 60     (max PWM correction per sync cycle)
 * - MOVETO_POS_TOLERANCE_M  : 0.03 m
 * - MOVETO_YAW_TOLERANCE_RAD: 0.08 rad
 * - Speed bands (PWM): FAST=80, MEDIUM=50, SLOW=30
 */
#pragma once

#include <Arduino.h>

// Motor driver pins
constexpr uint8_t BACK_LEFT_PWM = 12;
constexpr uint8_t BACK_LEFT_BACKWARD = 35;
constexpr uint8_t BACK_LEFT_FORWARD = 34;
constexpr uint8_t BACK_LEFT_EN_A = 18;
constexpr uint8_t BACK_LEFT_EN_B = 31;

constexpr uint8_t BACK_RIGHT_PWM = 8;
constexpr uint8_t BACK_RIGHT_BACKWARD = 37;
constexpr uint8_t BACK_RIGHT_FORWARD = 36;
constexpr uint8_t BACK_RIGHT_EN_A = 19;
constexpr uint8_t BACK_RIGHT_EN_B = 38;

constexpr uint8_t FRONT_LEFT_PWM = 9;
constexpr uint8_t FRONT_LEFT_BACKWARD = 42;
constexpr uint8_t FRONT_LEFT_FORWARD = 43;
constexpr uint8_t FRONT_LEFT_EN_A = 3;
constexpr uint8_t FRONT_LEFT_EN_B = 49;

constexpr uint8_t FRONT_RIGHT_PWM = 5;
constexpr uint8_t FRONT_RIGHT_BACKWARD = A4;
constexpr uint8_t FRONT_RIGHT_FORWARD = A5;
constexpr uint8_t FRONT_RIGHT_EN_A = 2;
constexpr uint8_t FRONT_RIGHT_EN_B = A1;

// Servo motor pins
constexpr uint8_t SERVO_CAM_PAN = 25;
constexpr uint8_t SERVO_CAM_TILT = 28;
constexpr uint8_t SERVO_LASER_PAN = 29;
constexpr uint8_t SERVO_LASER_TILT = 30;

// Laser pin
constexpr uint8_t LASER_PIN = A10;

// Sync tuning values
constexpr unsigned long MOTOR_SYNC_DELAY_MS = 50;
constexpr unsigned long MOTOR_ENCODER_STALE_US = 250000;
constexpr int MOTOR_SYNC_STEP = 1;
constexpr int MOTOR_SYNC_DEADBAND_US = 40;
constexpr int MOTOR_SYNC_MAX_CORRECTION = 60;
constexpr unsigned long SERIAL_BAUDRATE = 115200;

// Per-wheel encoder direction multipliers.
// With +x forward motion: left wheels count negative, right wheels count positive.
// Flip a sign to -1.0f if a wheel reads inverted on your hardware.

// Wheel odometry constants (metric units).
constexpr float ODOM_WHEEL_RADIUS_M = 0.078f;
constexpr float ODOM_TICKS_PER_REV = 650.0f;
constexpr float ODOM_HALF_LENGTH_M = 0.105f;
constexpr float ODOM_HALF_WIDTH_M = 0.083f;

// Per-wheel encoder direction multipliers.
constexpr float ODOM_ENC_SIGN_FL = 0.505f;
constexpr float ODOM_ENC_SIGN_FR = 0.505f;
constexpr float ODOM_ENC_SIGN_BL = 0.505f;
constexpr float ODOM_ENC_SIGN_BR = 0.505f;

// Low-speed PWM pulse shaping for motors that stall below minimum drive PWM.
constexpr int MOTOR_MIN_EFFECTIVE_PWM = 45;
constexpr unsigned long MOTOR_LOW_SPEED_PULSE_PERIOD_MS = 100;

// moveTo controller tuning.
constexpr float MOVETO_POS_TOLERANCE_M = 0.03f;
constexpr float MOVETO_YAW_TOLERANCE_RAD = 0.08f;

// Error-to-speed bands. If combined error is above FAST distance, use FAST PWM.
// If above MEDIUM distance, use MEDIUM PWM, else use SLOW PWM.
constexpr float MOVETO_FAST_DISTANCE_M = 0.50f;
constexpr float MOVETO_MEDIUM_DISTANCE_M = 0.18f;
constexpr float MOVETO_YAW_EQUIV_M = 1.0f;

constexpr int MOVETO_FAST_PWM = 80;
constexpr int MOVETO_MEDIUM_PWM = 50;
constexpr int MOVETO_SLOW_PWM = 30;

constexpr float kServoMinDeg = 0.0f;
constexpr float kServoMaxDeg = 180.0f;
constexpr float kServoMidDeg = 90.0f;
constexpr float kDirectionCompletionToleranceDeg = 0.5f;