#include <Arduino.h>

#include "config.h"
#include "motor.h"

namespace {

void printHelp() {
    Serial.println("Motor test ready. Enter: vx vy wz (range -255..255)");
    Serial.println("Example: 120 -30 45");
    Serial.println("Type 'stop' to disable all motors.");
    Serial.println("Type 'odom_reset' to reset odometry pose.");
    Serial.println("Type 'goto x y yaw' for moveTo in meters/radians.");
    Serial.println("Type 'goto_cancel' to cancel moveTo.");
}

void handleLine(String line) {
    line.trim();

    Serial.print("Received command: ");
    Serial.println(line);

    if (line.length() == 0) {
        return;
    }

    if (line.equalsIgnoreCase("stop")) {
        stopRobot();
        Serial.println("STOP");
        return;
    }

    if (line.equalsIgnoreCase("odom_reset")) {
        resetOdometryPose();
        Serial.println("ODOM RESET");
        return;
    }

    if (line.equalsIgnoreCase("goto_cancel")) {
        cancelMoveTo();
        Serial.println("GOTO CANCELED");
        return;
    }

    int targetX = 0;
    int targetY = 0;
    int targetYaw = 0;
    const int gotoParsed = sscanf(line.c_str(), "goto %d %d %d", &targetX, &targetY, &targetYaw);
    if (gotoParsed == 3) {
        moveTo(targetX/100.0, targetY/100.0, targetYaw/100.0);
        Serial.print("GOTO x=");
        Serial.print(targetX/100.0, 4);
        Serial.print(" y=");
        Serial.print(targetY/100.0, 4);
        Serial.print(" yaw=");
        Serial.println(targetYaw/57.2958, 4);
        return;
    }

    int vx = 0;
    int vy = 0;
    int wz = 0;
    const int parsed = sscanf(line.c_str(), "%d %d %d", &vx, &vy, &wz);
    if (parsed != 3) {
        Serial.println("Invalid command. Use: vx vy wz");
        return;
    }

    vx = constrain(vx, -255, 255);
    vy = constrain(vy, -255, 255);
    wz = constrain(wz, -255, 255);

    move(vx, vy, wz);

    Serial.print("CMD vx=");
    Serial.print(vx);
    Serial.print(" vy=");
    Serial.print(vy);
    Serial.print(" wz=");
    Serial.print(wz);
    Serial.print(" -> FL=");
    Serial.print(getFrontLeftTargetPWM());
    Serial.print(" FR=");
    Serial.print(getFrontRightTargetPWM());
    Serial.print(" BL=");
    Serial.print(getBackLeftTargetPWM());
    Serial.print(" BR=");
    Serial.println(getBackRightTargetPWM());
}

} // namespace

void setup() {
    Serial.begin(SERIAL_BAUDRATE);
    setupMotor();
    printHelp();
}

void loop() {
    if (Serial.available()) {
        String line = Serial.readStringUntil('\n');
        handleLine(line);
    }

    odometryService();
    moveToService();
    motorSyncService();

    static unsigned long lastPrintMs = 0;
    const unsigned long nowMs = millis();
    if (nowMs - lastPrintMs >= 500) {
        lastPrintMs = nowMs;
        Serial.print("ENC fl=");
        Serial.print(getFrontLeftEncoderCount());
        Serial.print(" fr=");
        Serial.print(getFrontRightEncoderCount());
        Serial.print(" bl=");
        Serial.print(getBackLeftEncoderCount());
        Serial.print(" br=");
        Serial.print(getBackRightEncoderCount());
        Serial.print(" | ODOM x=");
        Serial.print(getOdometryXMeters(), 4);
        Serial.print(" y=");
        Serial.print(getOdometryYMeters(), 4);
        Serial.print(" th=");
        Serial.print(getOdometryThetaRad(), 4);
        Serial.print(" | GOTO=");
        Serial.println(isMoveToActive() ? "ACTIVE" : "IDLE");
    }
}
