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

long odomLastEncoderCount[kWheelCount] = {0, 0, 0, 0};
float odomXMeter = 0.0f;
float odomYMeter = 0.0f;
float odomThetaRad = 0.0f;

bool moveToActive = false;
float moveToTargetXMeter = 0.0f;
float moveToTargetYMeter = 0.0f;
float moveToTargetYawRad = 0.0f;

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

float normalizeAngleRad(float angleRad) {
    while (angleRad > PI) {
        angleRad -= 2.0f * PI;
    }
    while (angleRad < -PI) {
        angleRad += 2.0f * PI;
    }
    return angleRad;
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

int getPulsedWheelPwm(int signedPwm) {
    const int direction = signOf(signedPwm);
    if (direction == 0) {
        return 0;
    }

    const int pwmAbs = abs(signedPwm);
    if (MOTOR_MIN_EFFECTIVE_PWM <= 0 || pwmAbs >= MOTOR_MIN_EFFECTIVE_PWM) {
        return signedPwm;
    }

    const unsigned long pulsePeriodMs = MOTOR_LOW_SPEED_PULSE_PERIOD_MS;
    if (pulsePeriodMs == 0) {
        return direction * MOTOR_MIN_EFFECTIVE_PWM;
    }

    const float duty = constrain(
        (float)pwmAbs / (float)MOTOR_MIN_EFFECTIVE_PWM,
        0.0f,
        1.0f);
    unsigned long onTimeMs = (unsigned long)(duty * (float)pulsePeriodMs);
    if (onTimeMs == 0 && pwmAbs > 0) {
        onTimeMs = 1;
    }

    if (onTimeMs >= pulsePeriodMs) {
        return direction * MOTOR_MIN_EFFECTIVE_PWM;
    }

    const unsigned long phaseMs = millis() % pulsePeriodMs;
    if (phaseMs < onTimeMs) {
        return direction * MOTOR_MIN_EFFECTIVE_PWM;
    }
    return 0;
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
        getPulsedWheelPwm(getAppliedWheelPwm(kFrontLeft)));
    writeSignedWheel(
        FRONT_RIGHT_PWM,
        FRONT_RIGHT_BACKWARD,
        FRONT_RIGHT_FORWARD,
        getPulsedWheelPwm(getAppliedWheelPwm(kFrontRight)));
    writeSignedWheel(
        BACK_LEFT_PWM,
        BACK_LEFT_BACKWARD,
        BACK_LEFT_FORWARD,
        getPulsedWheelPwm(getAppliedWheelPwm(kBackLeft)));
    writeSignedWheel(
        BACK_RIGHT_PWM,
        BACK_RIGHT_BACKWARD,
        BACK_RIGHT_FORWARD,
        getPulsedWheelPwm(getAppliedWheelPwm(kBackRight)));
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
        odomLastEncoderCount[i] = 0;
    }
    interrupts();

    odomXMeter = 0.0f;
    odomYMeter = 0.0f;
    odomThetaRad = 0.0f;

    attachInterrupt(digitalPinToInterrupt(FRONT_LEFT_EN_A), frontLeftEncTrig, CHANGE);
    attachInterrupt(digitalPinToInterrupt(FRONT_RIGHT_EN_A), frontRightEncTrig, CHANGE);
    attachInterrupt(digitalPinToInterrupt(BACK_LEFT_EN_A), backLeftEncTrig, CHANGE);
    attachInterrupt(digitalPinToInterrupt(BACK_RIGHT_EN_A), backRightEncTrig, CHANGE);

    stopRobot();
    Serial.println("Motor setup complete.");
}

void move(int vx, int vy, int wz) {
    // +vx is forward, +vy is left, +wz is CCW.
    const int nextTargetPwm[kWheelCount] = {
        clampSignedPwm(vx - vy - wz),
        clampSignedPwm(vx + vy + wz),
        clampSignedPwm(vx + vy - wz),
        clampSignedPwm(vx - vy + wz)};

    bool shouldResetSync = false;
    for (int i = 0; i < kWheelCount; ++i) {
        if (signOf(nextTargetPwm[i]) != signOf(targetPwm[i])) {
            shouldResetSync = true;
        }
        targetPwm[i] = nextTargetPwm[i];
    }

    if (shouldResetSync) {
        for (int i = 0; i < kWheelCount; ++i) {
            syncOffset[i] = 0;
        }
        moveStartMillis = millis();
    }
    applyAllWheelOutputs();
}

void stopRobot() {
    moveToActive = false;
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
        odomLastEncoderCount[i] = 0;
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

void odometryService() {
    long counts[kWheelCount] = {0, 0, 0, 0};

    noInterrupts();
    for (int i = 0; i < kWheelCount; ++i) {
        counts[i] = encoderCount[i];
    }
    interrupts();

    const float metersPerTick =
        (ODOM_TICKS_PER_REV > 0.0f) ? (2.0f * PI * ODOM_WHEEL_RADIUS_M) / ODOM_TICKS_PER_REV : 0.0f;
    if (metersPerTick <= 0.0f) {
        return;
    }

    const long deltaFlTicks = counts[kFrontLeft] - odomLastEncoderCount[kFrontLeft];
    const long deltaFrTicks = counts[kFrontRight] - odomLastEncoderCount[kFrontRight];
    const long deltaBlTicks = counts[kBackLeft] - odomLastEncoderCount[kBackLeft];
    const long deltaBrTicks = counts[kBackRight] - odomLastEncoderCount[kBackRight];

    for (int i = 0; i < kWheelCount; ++i) {
        odomLastEncoderCount[i] = counts[i];
    }

    if (deltaFlTicks == 0 && deltaFrTicks == 0 && deltaBlTicks == 0 && deltaBrTicks == 0) {
        return;
    }

    const float sFl = (float)deltaFlTicks * ODOM_ENC_SIGN_FL * metersPerTick;
    const float sFr = (float)deltaFrTicks * ODOM_ENC_SIGN_FR * metersPerTick;
    const float sBl = (float)deltaBlTicks * ODOM_ENC_SIGN_BL * metersPerTick;
    const float sBr = (float)deltaBrTicks * ODOM_ENC_SIGN_BR * metersPerTick;

    const float dXBody = (-sFl + sFr - sBl + sBr) * 0.25f;
    const float dYBody = (sFl + sFr - sBl - sBr) * 0.25f;

    const float kRotArm = ODOM_HALF_LENGTH_M + ODOM_HALF_WIDTH_M;
    const float dTheta =
        (kRotArm > 0.0f) ? ((sFl + sFr + sBl + sBr) / (4.0f * kRotArm)) : 0.0f;

    // Rotate incremental robot-frame motion into world frame using midpoint heading.
    const float midTheta = odomThetaRad + 0.5f * dTheta;
    const float cosMid = cos(midTheta);
    const float sinMid = sin(midTheta);
    const float dXWorld = dXBody * cosMid - dYBody * sinMid;
    const float dYWorld = dXBody * sinMid + dYBody * cosMid;

    odomXMeter += dXWorld;
    odomYMeter += dYWorld;
    odomThetaRad = normalizeAngleRad(odomThetaRad + dTheta);
}

void resetOdometryPose() {
    noInterrupts();
    for (int i = 0; i < kWheelCount; ++i) {
        odomLastEncoderCount[i] = encoderCount[i];
    }
    interrupts();

    odomXMeter = 0.0f;
    odomYMeter = 0.0f;
    odomThetaRad = 0.0f;
}

void getOdometryPose(float &xMeters, float &yMeters, float &thetaRad) {
    xMeters = odomXMeter;
    yMeters = odomYMeter;
    thetaRad = odomThetaRad;
}

float getOdometryXMeters() {
    return odomXMeter;
}

float getOdometryYMeters() {
    return odomYMeter;
}

float getOdometryThetaRad() {
    return odomThetaRad;
}

void moveTo(float targetXMeters, float targetYMeters, float targetYawRad) {
    moveToTargetXMeter = targetXMeters;
    moveToTargetYMeter = targetYMeters;
    moveToTargetYawRad = normalizeAngleRad(targetYawRad);
    moveToActive = true;
}

void moveToService() {
    if (!moveToActive) {
        return;
    }

    float currentX = 0.0f;
    float currentY = 0.0f;
    float currentYaw = 0.0f;
    getOdometryPose(currentX, currentY, currentYaw);

    const float dxWorld = moveToTargetXMeter - currentX;
    const float dyWorld = moveToTargetYMeter - currentY;
    float dyaw = moveToTargetYawRad - currentYaw;
    if (dyaw > 3.14159f) {
        dyaw -= 6.28318f;
    } else if (dyaw < -3.14159f) {
        dyaw += 6.28318f;
    }

    const float posErr = sqrt(dxWorld * dxWorld + dyWorld * dyWorld);
    if (posErr <= MOVETO_POS_TOLERANCE_M && abs(dyaw) <= MOVETO_YAW_TOLERANCE_RAD) {
        moveToActive = false;
        stopRobot();
        return;
    }

    // Convert world-frame XY error to robot frame so vx/vy are body-relative.
    const float cosYaw = cos(currentYaw);
    const float sinYaw = sin(currentYaw);
    const float dxBody = cosYaw * dxWorld + sinYaw * dyWorld;
    const float dyBody = -sinYaw * dxWorld + cosYaw * dyWorld;

    const float combinedErr = max(posErr, abs(dyaw) * MOVETO_YAW_EQUIV_M);

    int speedPwm = MOVETO_SLOW_PWM;
    if (combinedErr > MOVETO_FAST_DISTANCE_M) {
        speedPwm = MOVETO_FAST_PWM;
    } else if (combinedErr > MOVETO_MEDIUM_DISTANCE_M) {
        speedPwm = MOVETO_MEDIUM_PWM;
    }

    const float maxComponent = max(max(abs(dxBody), abs(dyBody)), abs(dyaw));
    if (maxComponent <= 0.0001f || speedPwm <= 0) {
        move(0, 0, 0);
        return;
    }

    const float scale = (float)speedPwm / maxComponent;
    const int vx = clampSignedPwm((int)round(dxBody * scale));
    const int vy = clampSignedPwm((int)round(dyBody * scale));
    const int wz = clampSignedPwm((int)round(dyaw * scale));

    move(vx, vy, wz);
}

bool isMoveToActive() {
    return moveToActive;
}

void cancelMoveTo() {
    stopRobot();
}