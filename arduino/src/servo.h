#ifndef SERVO_CONTROL_H
#define SERVO_CONTROL_H

#include <Arduino.h>
#include <Servo.h>

class ServoController {
public:
    ServoController();
    void begin();
    
    // Angles in degrees (0-180)
    void setCameraPan(int angle);
    void setCameraTilt(int angle);
    void setLaserPan(int angle);
    void setLaserTilt(int angle);

private:
    Servo camPan;
    Servo camTilt;
    Servo laserPan;
    Servo laserTilt;
};

#endif
