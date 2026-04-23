#include "servo.h"
#include "config.h"

ServoController::ServoController() {}

void ServoController::begin() {
    // Attach and set each servo one by one with a small delay
    camPan.attach(SERVO_CAM_PAN);
    setCameraPan(90);
    delay(200); 

    camTilt.attach(SERVO_CAM_TILT);
    setCameraTilt(90);
    delay(200);

    laserPan.attach(SERVO_LASER_PAN);
    setLaserPan(90);
    delay(200);

    laserTilt.attach(SERVO_LASER_TILT);
    setLaserTilt(90);
    delay(200);
}

void ServoController::setCameraPan(int angle) {
    camPan.write(constrain(angle, 0, 180));
}

void ServoController::setCameraTilt(int angle) {
    camTilt.write(constrain(angle, 0, 180));
}

void ServoController::setLaserPan(int angle) {
    laserPan.write(constrain(angle, 0, 180));
}

void ServoController::setLaserTilt(int angle) {
    laserTilt.write(constrain(angle, 0, 180));
}
