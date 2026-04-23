#include "servo.h"
#include "config.h"

#include <math.h>

namespace {

} // namespace

ServoController::ServoController()
    : servosAttached(false),
    currentCameraPanDeg(kServoMidDeg),
    currentCameraTiltDeg(kServoMidDeg),
      currentLaserPanDeg(kServoMidDeg),
      currentLaserTiltDeg(kServoMidDeg),
      directionMoveActive(false),
      directionTargetPanDeg(kServoMidDeg),
      directionTargetTiltDeg(kServoMidDeg),
      directionMoveSpeedDegPerSec(0.0f),
      circleDrawActive(false),
      circleCenterPanDeg(kServoMidDeg),
      circleCenterTiltDeg(kServoMidDeg),
      circleRadiusDeg(0.0f),
      circleAngularSpeedDegPerSec(0.0f),
      circleRequestedRotations(0),
      circleProgressDeg(0.0f),
      lastMotionUpdateMs(0) {}

void ServoController::begin() {
    lastMotionUpdateMs = millis();

    camPan.attach(SERVO_CAM_PAN);
    camTilt.attach(SERVO_CAM_TILT);
    laserPan.attach(SERVO_LASER_PAN);
    laserTilt.attach(SERVO_LASER_TILT);
    servosAttached = true;
    setCameraPan(static_cast<int>(kServoMidDeg));
    setCameraTilt(static_cast<int>(kServoMidDeg));
    applyLaserAngles(kServoMidDeg, kServoMidDeg);
}

void ServoController::setCameraPan(int angle) {
    currentCameraPanDeg = constrain(static_cast<float>(angle), kServoMinDeg, kServoMaxDeg);
    if (servosAttached) {
        camPan.write(static_cast<int>(currentCameraPanDeg));
    }
}

void ServoController::setCameraTilt(int angle) {
    currentCameraTiltDeg = constrain(static_cast<float>(angle), kServoMinDeg, kServoMaxDeg);
    if (servosAttached) {
        camTilt.write(static_cast<int>(currentCameraTiltDeg));
    }
}

void ServoController::setLaserPan(int angle) {
    cancelLaserMotion();
    applyLaserAngles(static_cast<float>(angle), currentLaserTiltDeg);
}

void ServoController::setLaserTilt(int angle) {
    cancelLaserMotion();
    applyLaserAngles(currentLaserPanDeg, static_cast<float>(angle));
}

bool ServoController::moveLaserMidpointToDirection(float panOffsetDeg,
                                                   float tiltOffsetDeg,
                                                   float speedDegPerSec) {
    if (speedDegPerSec <= 0.0f) {
        return false;
    }

    cancelCircleDraw();
    directionTargetPanDeg = constrain(kServoMidDeg + panOffsetDeg, kServoMinDeg, kServoMaxDeg);
    directionTargetTiltDeg = constrain(kServoMidDeg + tiltOffsetDeg, kServoMinDeg, kServoMaxDeg);
    directionMoveSpeedDegPerSec = speedDegPerSec;
    directionMoveActive = true;
    lastMotionUpdateMs = millis();
    return true;
}

bool ServoController::drawLaserCircleAtDirection(float centerPanOffsetDeg,
                                                 float centerTiltOffsetDeg,
                                                 float radiusDeg,
                                                 float angularSpeedDegPerSec,
                                                 int rotations) {
    if (radiusDeg <= 0.0f || angularSpeedDegPerSec <= 0.0f || rotations <= 0) {
        return false;
    }

    cancelDirectionMove();
    circleCenterPanDeg = constrain(centerPanOffsetDeg, kServoMinDeg, kServoMaxDeg);
    circleCenterTiltDeg = constrain(centerTiltOffsetDeg, kServoMinDeg, kServoMaxDeg);
    circleRadiusDeg = radiusDeg;
    circleAngularSpeedDegPerSec = angularSpeedDegPerSec;
    circleRequestedRotations = rotations;
    circleProgressDeg = 0.0f;
    circleDrawActive = true;
    lastMotionUpdateMs = millis();
    return true;
}

void ServoController::cancelLaserMotion() {
    cancelDirectionMove();
    cancelCircleDraw();
}

void ServoController::update() {
    if ((!directionMoveActive && !circleDrawActive) || !servosAttached) {
        return;
    }

    const unsigned long nowMs = millis();
    const unsigned long elapsedMs = nowMs - lastMotionUpdateMs;
    if (elapsedMs == 0) {
        return;
    }
    lastMotionUpdateMs = nowMs;
    const float dtSec = elapsedMs / 1000.0f;

    if (directionMoveActive) {
        const float panDelta = directionTargetPanDeg - currentLaserPanDeg;
        const float tiltDelta = directionTargetTiltDeg - currentLaserTiltDeg;
        const float distance = sqrtf((panDelta * panDelta) + (tiltDelta * tiltDelta));

        if (distance <= kDirectionCompletionToleranceDeg) {
            applyLaserAngles(directionTargetPanDeg, directionTargetTiltDeg);
            cancelDirectionMove();
            return;
        }

        const float maxStep = directionMoveSpeedDegPerSec * dtSec;
        if (maxStep >= distance) {
            applyLaserAngles(directionTargetPanDeg, directionTargetTiltDeg);
            cancelDirectionMove();
            return;
        }

        const float stepScale = maxStep / distance;
        applyLaserAngles(currentLaserPanDeg + (panDelta * stepScale),
                         currentLaserTiltDeg + (tiltDelta * stepScale));
        return;
    }

    if (circleDrawActive) {
        circleProgressDeg += circleAngularSpeedDegPerSec * dtSec;

        const float totalTargetDeg = circleRequestedRotations * 360.0f;
        if (circleProgressDeg >= totalTargetDeg) {
            applyLaserAngles(circleCenterPanDeg + circleRadiusDeg, circleCenterTiltDeg);
            cancelCircleDraw();
            return;
        }

        const float thetaRad = radians(circleProgressDeg);
        const float panDeg = circleCenterPanDeg + (circleRadiusDeg * cosf(thetaRad));
        const float tiltDeg = circleCenterTiltDeg + (circleRadiusDeg * sinf(thetaRad));
        applyLaserAngles(panDeg, tiltDeg);
    }
}

bool ServoController::isLaserDirectionMoveActive() const {
    return directionMoveActive;
}

bool ServoController::isLaserCircleDrawActive() const {
    return circleDrawActive;
}

bool ServoController::isLaserMotionActive() const {
    return directionMoveActive || circleDrawActive;
}

int ServoController::getCameraPanAngleDeg() const {
    return static_cast<int>(roundf(currentCameraPanDeg));
}

int ServoController::getCameraTiltAngleDeg() const {
    return static_cast<int>(roundf(currentCameraTiltDeg));
}

int ServoController::getLaserPanAngleDeg() const {
    return static_cast<int>(roundf(currentLaserPanDeg));
}

int ServoController::getLaserTiltAngleDeg() const {
    return static_cast<int>(roundf(currentLaserTiltDeg));
}

void ServoController::applyLaserAngles(float panDeg, float tiltDeg) {
    currentLaserPanDeg = constrain(panDeg, kServoMinDeg, kServoMaxDeg);
    currentLaserTiltDeg = constrain(tiltDeg, kServoMinDeg, kServoMaxDeg);

    if (!servosAttached) {
        return;
    }

    laserPan.write(static_cast<int>(currentLaserPanDeg));
    laserTilt.write(static_cast<int>(currentLaserTiltDeg));
}

void ServoController::cancelDirectionMove() {
    directionMoveActive = false;
}

void ServoController::cancelCircleDraw() {
    circleDrawActive = false;
}
