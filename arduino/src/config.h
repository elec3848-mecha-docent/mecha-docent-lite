#pragma once

#include <Arduino.h>

// Motor driver pins
#define FRONT_RIGHT_PWM 12
#define FRONT_RIGHT_BACKWARD 34
#define FRONT_RIGHT_FORWARD 35
#define FRONT_RIGHT_EN_A 18
#define FRONT_RIGHT_EN_B 31

#define FRONT_LEFT_PWM 8
#define FRONT_LEFT_BACKWARD 36
#define FRONT_LEFT_FORWARD 37
#define FRONT_LEFT_EN_A 19
#define FRONT_LEFT_EN_B 38

#define BACK_RIGHT_PWM 9
#define BACK_RIGHT_BACKWARD 43
#define BACK_RIGHT_FORWARD 42
#define BACK_RIGHT_EN_A 3
#define BACK_RIGHT_EN_B 49

#define BACK_LEFT_PWM 5
#define BACK_LEFT_BACKWARD A5
#define BACK_LEFT_FORWARD A4
#define BACK_LEFT_EN_A 2
#define BACK_LEFT_EN_B A1

// Sync tuning values
const unsigned long MOTOR_SYNC_DELAY_MS = 50;
const unsigned long MOTOR_ENCODER_STALE_US = 250000;
const int MOTOR_SYNC_STEP = 1;
const int MOTOR_SYNC_DEADBAND_US = 40;
const int MOTOR_SYNC_MAX_CORRECTION = 60;
const unsigned long SERIAL_BAUDRATE = 115200;
