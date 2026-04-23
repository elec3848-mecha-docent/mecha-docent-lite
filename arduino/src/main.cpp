#include <Arduino.h>

#include "config.h"
#include "motor.h"

namespace {

void printHelp() {
    Serial.println("Motor test ready. Enter: vx vy wz (range -255..255)");
    Serial.println("Example: 120 -30 45");
    Serial.println("Type 'stop' to disable all motors.");
}

void handleLine(String line) {
    line.trim();
    if (line.length() == 0) {
        return;
    }

    if (line.equalsIgnoreCase("stop")) {
        stopRobot();
        Serial.println("STOP");
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
        Serial.println(getBackRightEncoderCount());
    }
}
