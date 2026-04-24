/**
 * @file main.cpp
 * @brief Serial command parser and dispatcher for the MechaDocent-Lite robot.
 *
 * Listens on the USB serial port at 115200 baud for newline-terminated ASCII
 * commands and dispatches them to the motor, servo, and laser controllers.
 *
 * Supported commands
 * ------------------
 * | Command            | Arguments                        | Description                            |
 * |--------------------|----------------------------------|----------------------------------------|
 * | `vx vy wz`         | int int int  (−255..255)         | Direct mecanum velocity                |
 * | `goto`             | x*100  y*100  yaw*57.2958 (int)  | Move to pose (cm-int / decideg-int)    |
 * | `odom_reset`       | —                                | Zero odometry                          |
 * | `goto_cancel`      | —                                | Cancel active moveTo                   |
 * | `stop`             | —                                | Hard stop all motors                   |
 * | `servo_cam`        | pan tilt  (0..180)               | Set camera servo angles                |
 * | `servo_laser`      | pan tilt  (0..180)               | Set laser servo angles                 |
 * | `laser_dir`        | panOff tiltOff speed             | Smooth laser move at deg/s             |
 * | `laser_circle`     | pan tilt radius rotations        | Draw laser circle (speed = 720 deg/s)  |
 * | `laser_on/off`     | —                                | Laser power                            |
 * | `laser_cancel`     | —                                | Cancel laser animation                 |
 *
 * Status replies
 * --------------
 * The firmware emits periodic status lines that the Raspberry Pi can poll:
 * - `POSE=x,y,yaw`   — odometry pose
 * - `GOTO=MOVING`    — moveTo in progress
 * - `GOTO=IDLE`      — moveTo complete
 * - `ENC=fl,fr,bl,br`— raw encoder counts
 */
#include <Arduino.h>

#include "config.h"
#include "laser.h"
#include "motor.h"
#include "servo.h"

namespace {

ServoController gServo;
LaserController gLaser(LASER_PIN);
constexpr float kLaserCircleSpeedDegPerSec = 720.0f;

void printHelp() {
    Serial.println("Motor serial protocol ready. Enter: vx vy wz (range -255..255)");
    Serial.println("Example: 120 -30 45");
    Serial.println("Type 'stop' to disable all motors.");
    Serial.println("Type 'odom_reset' to reset odometry pose.");
    Serial.println("Type 'goto x y yaw' for moveTo in meters/radians (scaled by 100).");
    Serial.println("Type 'goto_cancel' to cancel moveTo.");
    Serial.println("Type 'servo_cam pan tilt' to set camera servos (0..180).");
    Serial.println("Type 'servo_laser pan tilt' to set laser servos (0..180).");
    Serial.println("Type 'laser_dir panOff tiltOff speed' to move laser midpoint in deg/s.");
    Serial.println("Type 'laser_circle pan tilt radius rotations' (absolute 0..180, speed fixed at 720 deg/s).");
    Serial.println("Type 'laser_cancel', 'laser_on', or 'laser_off'.");
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

    if (line.equalsIgnoreCase("laser_cancel")) {
        gServo.cancelLaserMotion();
        Serial.println("LASER MOTION CANCELED");
        return;
    }

    if (line.equalsIgnoreCase("laser_on")) {
        gLaser.turnOn();
        Serial.println("LASER ON");
        return;
    }

    if (line.equalsIgnoreCase("laser_off")) {
        gLaser.turnOff();
        Serial.println("LASER OFF");
        return;
    }

    int panDeg = 0;
    int tiltDeg = 0;
    const int cameraServoParsed = sscanf(line.c_str(), "servo_cam %d %d", &panDeg, &tiltDeg);
    if (cameraServoParsed == 2) {
        gServo.setCameraPan(panDeg);
        gServo.setCameraTilt(tiltDeg);
        Serial.print("SERVO_CAM pan=");
        Serial.print(gServo.getCameraPanAngleDeg());
        Serial.print(" tilt=");
        Serial.println(gServo.getCameraTiltAngleDeg());
        return;
    }

    const int laserServoParsed = sscanf(line.c_str(), "servo_laser %d %d", &panDeg, &tiltDeg);
    if (laserServoParsed == 2) {
        gServo.setLaserPan(panDeg);
        gServo.setLaserTilt(tiltDeg);
        Serial.print("SERVO_LASER pan=");
        Serial.print(gServo.getLaserPanAngleDeg());
        Serial.print(" tilt=");
        Serial.println(gServo.getLaserTiltAngleDeg());
        return;
    }

    int panOffsetDeg = 0;
    int tiltOffsetDeg = 0;
    int speedDegPerSec = 0;
    const int laserDirectionParsed = sscanf(
        line.c_str(), "laser_dir %d %d %d", &panOffsetDeg, &tiltOffsetDeg, &speedDegPerSec);
    if (laserDirectionParsed == 3) {
        if (gServo.moveLaserMidpointToDirection(panOffsetDeg, tiltOffsetDeg, speedDegPerSec)) {
            Serial.print("LASER_DIR panOff=");
            Serial.print(panOffsetDeg);
            Serial.print(" tiltOff=");
            Serial.print(tiltOffsetDeg);
            Serial.print(" speed=");
            Serial.println(speedDegPerSec);
        } else {
            Serial.println("LASER_DIR REJECTED");
        }
        return;
    }

    int radiusDeg = 0;
    int rotations = 0;
    const int laserCircleParsed = sscanf(
        line.c_str(), "laser_circle %d %d %d %d", &panOffsetDeg, &tiltOffsetDeg, &radiusDeg, &rotations);
    if (laserCircleParsed == 4) {
        if (gServo.drawLaserCircleAtDirection(
                panOffsetDeg, tiltOffsetDeg, radiusDeg, kLaserCircleSpeedDegPerSec, rotations)) {
            Serial.print("LASER_CIRCLE panOff=");
            Serial.print(panOffsetDeg);
            Serial.print(" tiltOff=");
            Serial.print(tiltOffsetDeg);
            Serial.print(" radius=");
            Serial.print(radiusDeg);
            Serial.print(" rotations=");
            Serial.print(rotations);
            Serial.print(" speed=");
            Serial.println(kLaserCircleSpeedDegPerSec);
        } else {
            Serial.println("LASER_CIRCLE REJECTED");
        }
        return;
    }

    int targetX = 0;
    int targetY = 0;
    int targetYaw = 0;
    const int gotoParsed = sscanf(line.c_str(), "goto %d %d %d", &targetX, &targetY, &targetYaw);
    if (gotoParsed == 3) {
        moveTo(targetX / 100.0f, targetY / 100.0f, targetYaw / 57.2958f);
        Serial.print("GOTO x=");
        Serial.print(targetX / 100.0f, 4);
        Serial.print(" y=");
        Serial.print(targetY / 100.0f, 4);
        Serial.print(" yaw=");
        Serial.println(targetYaw / 57.2958f, 4);
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
    gServo.begin();
    gLaser.begin();
    gLaser.turnOff();
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
    gServo.update();

    static unsigned long lastPrintMs = 0;
    const unsigned long nowMs = millis();
    if (nowMs - lastPrintMs >= 500) {
        lastPrintMs = nowMs;
        Serial.print("SERVO cam_pan=");
        Serial.print(gServo.getCameraPanAngleDeg());
        Serial.print(" cam_tilt=");
        Serial.print(gServo.getCameraTiltAngleDeg());
        Serial.print(" laser_pan=");
        Serial.print(gServo.getLaserPanAngleDeg());
        Serial.print(" laser_tilt=");
        Serial.print(gServo.getLaserTiltAngleDeg());
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
