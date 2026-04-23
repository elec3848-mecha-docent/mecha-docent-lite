/**
 * @file motor.cpp
 * @brief Mecanum-wheel motor driver implementation.
 */
#include "motor.h"
#include "config.h"
#include <Arduino.h>

namespace {

enum WheelIndex {
    kFrontLeft = 0,
    kFrontRight = 1,
    kBackLeft = 2,
    kBackRight = 3,
    kWheelCount = 4,
};

volatile long encoderCount[kWheelCount] = {0, 0, 0, 0};
volatile unsigned long encoderLastMicros[kWheelCount] = {0, 0, 0, 0};
volatile unsigned long encoderDeltaMicros[kWheelCount] = {0, 0, 0, 0};
volatile int lastStateA[kWheelCount] = {LOW, LOW, LOW, LOW};

int targetPwm[kWheelCount] = {0, 0, 0, 0};
int syncOffset[kWheelCount] = {0, 0, 0, 0};
unsigned long moveStartMillis = 0;

int clampSignedPwm(int value) {
    return constrain(value, -255, 255);
}

int signOf(int value) {
    if (value > 0) {
        return 1;
    }
    if (value < 0) {
        return -1;
    }
    return 0;
}

void writeSignedWheel(int pwmPin, int backwardPin, int forwardPin, int signedPwm) {
    const int clamped = clampSignedPwm(signedPwm);
    if (clamped > 0) {
        digitalWrite(backwardPin, LOW);
        digitalWrite(forwardPin, HIGH);
        analogWrite(pwmPin, clamped);
        return;
    }

    if (clamped < 0) {
        digitalWrite(backwardPin, HIGH);
        digitalWrite(forwardPin, LOW);
        analogWrite(pwmPin, -clamped);
        return;
    }

    digitalWrite(backwardPin, LOW);
    digitalWrite(forwardPin, LOW);
    analogWrite(pwmPin, 0);
}

int getAppliedWheelPwm(int wheel) {
    const int direction = signOf(targetPwm[wheel]);
    if (direction == 0) {
        return 0;
    }

    const int targetAbs = abs(targetPwm[wheel]);
    const int correctedAbs = constrain(
        targetAbs + syncOffset[wheel],
        0,
        255);
    return direction * correctedAbs;
}

void applyAllWheelOutputs() {
    writeSignedWheel(
        FRONT_LEFT_PWM,
        FRONT_LEFT_BACKWARD,
        FRONT_LEFT_FORWARD,
        getAppliedWheelPwm(kFrontLeft));
    writeSignedWheel(
        FRONT_RIGHT_PWM,
        FRONT_RIGHT_BACKWARD,
        FRONT_RIGHT_FORWARD,
        getAppliedWheelPwm(kFrontRight));
    writeSignedWheel(
        BACK_LEFT_PWM,
        BACK_LEFT_BACKWARD,
        BACK_LEFT_FORWARD,
        getAppliedWheelPwm(kBackLeft));
    writeSignedWheel(
        BACK_RIGHT_PWM,
        BACK_RIGHT_BACKWARD,
        BACK_RIGHT_FORWARD,
        getAppliedWheelPwm(kBackRight));
}

bool wheelHasFreshRate(
    int wheel,
    unsigned long nowMicros,
    unsigned long lastTickMicros,
    unsigned long deltaMicros) {
    if (targetPwm[wheel] == 0) {
        return false;
    }
    if (deltaMicros == 0) {
        return false;
    }
    const unsigned long age = nowMicros - lastTickMicros;
    return age <= MOTOR_ENCODER_STALE_US;
}

void handleEncoderTick(int wheel, int pinA, int pinB) {
    const unsigned long now = micros();
    encoderDeltaMicros[wheel] = now - encoderLastMicros[wheel];
    encoderLastMicros[wheel] = now;

    const int currentStateA = digitalRead(pinA);
    const int currentStateB = digitalRead(pinB);

    if (currentStateA != lastStateA[wheel]) {
        if (currentStateA == HIGH) {
            encoderCount[wheel] += (currentStateB == LOW) ? 1 : -1;
        } else {
            encoderCount[wheel] += (currentStateB == HIGH) ? 1 : -1;
        }
    }
    lastStateA[wheel] = currentStateA;
}

void frontLeftEncTrig() {
    handleEncoderTick(kFrontLeft, FRONT_LEFT_EN_A, FRONT_LEFT_EN_B);
}

void frontRightEncTrig() {
    handleEncoderTick(kFrontRight, FRONT_RIGHT_EN_A, FRONT_RIGHT_EN_B);
}

void backLeftEncTrig() {
    handleEncoderTick(kBackLeft, BACK_LEFT_EN_A, BACK_LEFT_EN_B);
}

void backRightEncTrig() {
    handleEncoderTick(kBackRight, BACK_RIGHT_EN_A, BACK_RIGHT_EN_B);
}

} // namespace

void setupMotor() {
    pinMode(FRONT_LEFT_PWM, OUTPUT);
    pinMode(FRONT_LEFT_BACKWARD, OUTPUT);
    pinMode(FRONT_LEFT_FORWARD, OUTPUT);

    pinMode(FRONT_RIGHT_PWM, OUTPUT);
    pinMode(FRONT_RIGHT_BACKWARD, OUTPUT);
    pinMode(FRONT_RIGHT_FORWARD, OUTPUT);

    pinMode(BACK_LEFT_PWM, OUTPUT);
    pinMode(BACK_LEFT_BACKWARD, OUTPUT);
    pinMode(BACK_LEFT_FORWARD, OUTPUT);

    pinMode(BACK_RIGHT_PWM, OUTPUT);
    pinMode(BACK_RIGHT_BACKWARD, OUTPUT);
    pinMode(BACK_RIGHT_FORWARD, OUTPUT);

    pinMode(FRONT_LEFT_EN_A, INPUT);
    pinMode(FRONT_LEFT_EN_B, INPUT);
    pinMode(FRONT_RIGHT_EN_A, INPUT);
    pinMode(FRONT_RIGHT_EN_B, INPUT);
    pinMode(BACK_LEFT_EN_A, INPUT);
    pinMode(BACK_LEFT_EN_B, INPUT);
    pinMode(BACK_RIGHT_EN_A, INPUT);
    pinMode(BACK_RIGHT_EN_B, INPUT);

    const unsigned long now = micros();
    noInterrupts();
    for (int i = 0; i < kWheelCount; ++i) {
        encoderCount[i] = 0;
        encoderLastMicros[i] = now;
        encoderDeltaMicros[i] = 0;
        lastStateA[i] = LOW;
    }
    interrupts();

    attachInterrupt(digitalPinToInterrupt(FRONT_LEFT_EN_A), frontLeftEncTrig, CHANGE);
    attachInterrupt(digitalPinToInterrupt(FRONT_RIGHT_EN_A), frontRightEncTrig, CHANGE);
    attachInterrupt(digitalPinToInterrupt(BACK_LEFT_EN_A), backLeftEncTrig, CHANGE);
    attachInterrupt(digitalPinToInterrupt(BACK_RIGHT_EN_A), backRightEncTrig, CHANGE);

    stopRobot();
    Serial.println("Motor setup complete.");
}

void move(int vx, int vy, int wz) {
    targetPwm[kFrontLeft] = clampSignedPwm(vx - vy + wz);
    targetPwm[kFrontRight] = clampSignedPwm(vx + vy - wz);
    targetPwm[kBackLeft] = clampSignedPwm(vx + vy + wz);
    targetPwm[kBackRight] = clampSignedPwm(vx - vy - wz);

    for (int i = 0; i < kWheelCount; ++i) {
        syncOffset[i] = 0;
    }

    moveStartMillis = millis();
    applyAllWheelOutputs();
}

void stopRobot() {
    for (int i = 0; i < kWheelCount; ++i) {
        targetPwm[i] = 0;
        syncOffset[i] = 0;
    }
    applyAllWheelOutputs();
}

void resetEncoderCounts() {
    noInterrupts();
    for (int i = 0; i < kWheelCount; ++i) {
        encoderCount[i] = 0;
    }
    interrupts();
}

long getAverageEncoderCount() {
    noInterrupts();
    const long total = encoderCount[kFrontLeft] + encoderCount[kFrontRight] +
                       encoderCount[kBackLeft] + encoderCount[kBackRight];
    interrupts();
    return total / 4;
}

long getAverageAbsoluteEncoderCount() {
    noInterrupts();
    const long fl = encoderCount[kFrontLeft];
    const long fr = encoderCount[kFrontRight];
    const long bl = encoderCount[kBackLeft];
    const long br = encoderCount[kBackRight];
    interrupts();
    return (abs(fl) + abs(fr) + abs(bl) + abs(br)) / 4;
}

long getFrontLeftEncoderCount() {
    noInterrupts();
    const long value = encoderCount[kFrontLeft];
    interrupts();
    return value;
}

long getFrontRightEncoderCount() {
    noInterrupts();
    const long value = encoderCount[kFrontRight];
    interrupts();
    return value;
}

long getBackLeftEncoderCount() {
    noInterrupts();
    const long value = encoderCount[kBackLeft];
    interrupts();
    return value;
}

long getBackRightEncoderCount() {
    noInterrupts();
    const long value = encoderCount[kBackRight];
    interrupts();
    return value;
}

int getFrontLeftTargetPWM() {
    return targetPwm[kFrontLeft];
}

int getFrontRightTargetPWM() {
    return targetPwm[kFrontRight];
}

int getBackLeftTargetPWM() {
    return targetPwm[kBackLeft];
}

int getBackRightTargetPWM() {
    return targetPwm[kBackRight];
}

void motorSyncService() {
    if (millis() - moveStartMillis < MOTOR_SYNC_DELAY_MS) {
        return;
    }

    unsigned long deltaMicros[kWheelCount] = {0, 0, 0, 0};
    unsigned long lastMicros[kWheelCount] = {0, 0, 0, 0};

    noInterrupts();
    for (int i = 0; i < kWheelCount; ++i) {
        deltaMicros[i] = encoderDeltaMicros[i];
        lastMicros[i] = encoderLastMicros[i];
    }
    interrupts();

    const unsigned long nowMicros = micros();
    int referenceWheel = -1;
    for (int i = 0; i < kWheelCount; ++i) {
        if (targetPwm[i] != 0 &&
            wheelHasFreshRate(i, nowMicros, lastMicros[i], deltaMicros[i])) {
            referenceWheel = i;
            break;
        }
    }

    if (referenceWheel < 0) {
        return;
    }

    const int referenceExpectedAbs = abs(targetPwm[referenceWheel]);
    const unsigned long referenceMeasuredUs = deltaMicros[referenceWheel];
    if (referenceExpectedAbs == 0 || referenceMeasuredUs == 0) {
        return;
    }

    for (int i = 0; i < kWheelCount; ++i) {
        if (i == referenceWheel) {
            continue;
        }

        const int expectedAbs = abs(targetPwm[i]);
        if (expectedAbs == 0 ||
            !wheelHasFreshRate(i, nowMicros, lastMicros[i], deltaMicros[i])) {
            syncOffset[i] = 0;
            continue;
        }

        const unsigned long targetIntervalUs =
            (referenceMeasuredUs * referenceExpectedAbs) / expectedAbs;
        const long intervalErrorUs = (long)deltaMicros[i] - (long)targetIntervalUs;

        if (intervalErrorUs > MOTOR_SYNC_DEADBAND_US) {
            syncOffset[i] = constrain(
                syncOffset[i] + MOTOR_SYNC_STEP,
                -MOTOR_SYNC_MAX_CORRECTION,
                MOTOR_SYNC_MAX_CORRECTION);
        } else if (intervalErrorUs < -MOTOR_SYNC_DEADBAND_US) {
            syncOffset[i] = constrain(
                syncOffset[i] - MOTOR_SYNC_STEP,
                -MOTOR_SYNC_MAX_CORRECTION,
                MOTOR_SYNC_MAX_CORRECTION);
        }
    }

    applyAllWheelOutputs();
}