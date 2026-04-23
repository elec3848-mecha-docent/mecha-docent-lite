#include <Arduino.h>

#include "config.h"
#include "laser.h"
#include "servo.h"

namespace {

ServoController gServo;

LaserController gLaser(LASER_PIN);
constexpr bool kLaserConfigured = true;

enum class DemoActionType {
    Point,
    Circle,
};

struct DemoAction {
    DemoActionType type;
    float panOffsetDeg;
    float tiltOffsetDeg;
    float radiusDeg;
    float speedDegPerSec;
    int rotations;
    bool laserOn;
    unsigned long holdAfterMs;
};

const DemoAction kSequence[] = {
    {DemoActionType::Point, 0.0f, 0.0f, 0.0f, 45.0f, 0, true, 500},
    {DemoActionType::Circle, 0.0f, 0.0f, 8.0f, 120.0f, 1, true, 400},
    {DemoActionType::Point, 18.0f, -10.0f, 0.0f, 35.0f, 0, true, 500},
    {DemoActionType::Circle, 18.0f, -10.0f, 6.0f, 180.0f, 2, true, 400},
    {DemoActionType::Point, -20.0f, 12.0f, 0.0f, 55.0f, 0, true, 500},
    {DemoActionType::Circle, -20.0f, 12.0f, 10.0f, 90.0f, 1, true, 500},
    {DemoActionType::Point, 8.0f, 18.0f, 0.0f, 30.0f, 0, false, 700},
};

constexpr size_t kSequenceCount = sizeof(kSequence) / sizeof(kSequence[0]);

size_t gCurrentAction = 0;
bool gActionStarted = false;
bool gActionDone = false;
unsigned long gActionDoneAtMs = 0;

void applyLaserState(bool on) {
    if (on) {
        gLaser.turnOn();
    } else {
        gLaser.turnOff();
    }
}

void printAction(const DemoAction& action) {
    Serial.print("Action ");
    Serial.print(gCurrentAction + 1);
    Serial.print("/");
    Serial.print(kSequenceCount);
    Serial.print(": ");

    if (action.type == DemoActionType::Point) {
        Serial.print("point panOff=");
        Serial.print(action.panOffsetDeg, 1);
        Serial.print(" tiltOff=");
        Serial.print(action.tiltOffsetDeg, 1);
        Serial.print(" speed=");
        Serial.print(action.speedDegPerSec, 1);
        Serial.println(" deg/s");
    } else {
        Serial.print("circle centerPanOff=");
        Serial.print(action.panOffsetDeg, 1);
        Serial.print(" centerTiltOff=");
        Serial.print(action.tiltOffsetDeg, 1);
        Serial.print(" radius=");
        Serial.print(action.radiusDeg, 1);
        Serial.print(" speed=");
        Serial.print(action.speedDegPerSec, 1);
        Serial.print(" deg/s rotations=");
        Serial.println(action.rotations);
    }
}

void startAction(const DemoAction& action) {
    applyLaserState(action.laserOn);
    printAction(action);

    if (action.type == DemoActionType::Point) {
        const bool started = gServo.moveLaserMidpointToDirection(
            action.panOffsetDeg, action.tiltOffsetDeg, action.speedDegPerSec);
        if (!started) {
            Serial.println("Point action rejected: invalid parameters.");
            gActionDone = true;
            gActionDoneAtMs = millis();
        }
        return;
    }

    const bool started = gServo.drawLaserCircleAtDirection(action.panOffsetDeg,
                                                           action.tiltOffsetDeg,
                                                           action.radiusDeg,
                                                           action.speedDegPerSec,
                                                           action.rotations);
    if (!started) {
        Serial.println("Circle action rejected: invalid parameters.");
        gActionDone = true;
        gActionDoneAtMs = millis();
    }
}

void maybeAdvanceSequence() {
    if (!gActionDone) {
        return;
    }

    const DemoAction& action = kSequence[gCurrentAction];
    if (millis() - gActionDoneAtMs < action.holdAfterMs) {
        return;
    }

    gCurrentAction = (gCurrentAction + 1) % kSequenceCount;
    gActionStarted = false;
    gActionDone = false;
}

} // namespace

void setup() {
    Serial.begin(SERIAL_BAUDRATE);
    gServo.begin();

    gLaser.begin();
    gLaser.turnOn();
}

void loop() {
    gServo.update();

    if (!gActionStarted) {
        gActionStarted = true;
        startAction(kSequence[gCurrentAction]);
    }

    if (!gActionDone) {
        const DemoAction& action = kSequence[gCurrentAction];
        if (action.type == DemoActionType::Point && !gServo.isLaserDirectionMoveActive()) {
            gActionDone = true;
            gActionDoneAtMs = millis();
            Serial.println("Point action complete.");
        }

        if (action.type == DemoActionType::Circle && !gServo.isLaserCircleDrawActive()) {
            gActionDone = true;
            gActionDoneAtMs = millis();
            Serial.println("Circle action complete.");
        }
    }

    maybeAdvanceSequence();

    static unsigned long lastHeartbeatMs = 0;
    const unsigned long nowMs = millis();
    if (nowMs - lastHeartbeatMs >= 1000) {
        lastHeartbeatMs = nowMs;
        Serial.print("Demo heartbeat | action=");
        Serial.print(gCurrentAction + 1);
        Serial.print(" | motionActive=");
        Serial.println(gServo.isLaserMotionActive() ? "yes" : "no");
    }

    if (!kLaserConfigured) {
        // Keep compile-time constant consumed without runtime impact.
    }
}
