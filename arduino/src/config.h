#pragma once

#include <Arduino.h>

// Motor driver pins
#define BACK_LEFT_PWM 12
#define BACK_LEFT_BACKWARD 35
#define BACK_LEFT_FORWARD 34
#define BACK_LEFT_EN_A 18
#define BACK_LEFT_EN_B 31

#define BACK_RIGHT_PWM 8
#define BACK_RIGHT_BACKWARD 37
#define BACK_RIGHT_FORWARD 36
#define BACK_RIGHT_EN_A 19
#define BACK_RIGHT_EN_B 38

#define FRONT_LEFT_PWM 9
#define FRONT_LEFT_BACKWARD 42
#define FRONT_LEFT_FORWARD 43
#define FRONT_LEFT_EN_A 3
#define FRONT_LEFT_EN_B 49

#define FRONT_RIGHT_PWM 5
#define FRONT_RIGHT_BACKWARD A4
#define FRONT_RIGHT_FORWARD A5
#define FRONT_RIGHT_EN_A 2
#define FRONT_RIGHT_EN_B A1

// Sync tuning values
const unsigned long MOTOR_SYNC_DELAY_MS = 50;
const unsigned long MOTOR_ENCODER_STALE_US = 250000;
const int MOTOR_SYNC_STEP = 1;
const int MOTOR_SYNC_DEADBAND_US = 40;
const int MOTOR_SYNC_MAX_CORRECTION = 60;
const unsigned long SERIAL_BAUDRATE = 115200;

// Per-wheel encoder direction multipliers.
// With +x forward motion: left wheels count negative, right wheels count positive.
// Flip a sign to -1.0f if a wheel reads inverted on your hardware.

// Wheel odometry constants (metric units).
const float ODOM_WHEEL_RADIUS_M = 0.078f;
const float ODOM_TICKS_PER_REV = 650.0f;
const float ODOM_HALF_LENGTH_M = 0.105f;
const float ODOM_HALF_WIDTH_M = 0.083f;

// Per-wheel encoder direction multipliers.
const float ODOM_ENC_SIGN_FL = 0.505f;
const float ODOM_ENC_SIGN_FR = 0.505f;
const float ODOM_ENC_SIGN_BL = 0.505f;
const float ODOM_ENC_SIGN_BR = 0.505f;

// Low-speed PWM pulse shaping for motors that stall below minimum drive PWM.
const int MOTOR_MIN_EFFECTIVE_PWM = 45;
const unsigned long MOTOR_LOW_SPEED_PULSE_PERIOD_MS = 100;

// moveTo controller tuning.
const float MOVETO_POS_TOLERANCE_M = 0.03f;
const float MOVETO_YAW_TOLERANCE_RAD = 0.08f;

// Error-to-speed bands. If combined error is above FAST distance, use FAST PWM.
// If above MEDIUM distance, use MEDIUM PWM, else use SLOW PWM.
const float MOVETO_FAST_DISTANCE_M = 0.50f;
const float MOVETO_MEDIUM_DISTANCE_M = 0.18f;
const float MOVETO_YAW_EQUIV_M = 1.0f;

const int MOVETO_FAST_PWM = 80;
const int MOVETO_MEDIUM_PWM = 50;
const int MOVETO_SLOW_PWM = 30;
