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

    // Direction offsets are in degrees around midpoint (90, 90).
    bool moveLaserMidpointToDirection(float panOffsetDeg, float tiltOffsetDeg, float speedDegPerSec);
    bool drawLaserCircleAtDirection(float centerPanOffsetDeg,
                                    float centerTiltOffsetDeg,
                                    float radiusDeg,
                                    float angularSpeedDegPerSec,
                                    int rotations);
    void cancelLaserMotion();
    void update();

    bool isLaserDirectionMoveActive() const;
    bool isLaserCircleDrawActive() const;
    bool isLaserMotionActive() const;
    int getCameraPanAngleDeg() const;
    int getCameraTiltAngleDeg() const;
    int getLaserPanAngleDeg() const;
    int getLaserTiltAngleDeg() const;

private:
    Servo camPan;
    Servo camTilt;
    Servo laserPan;
    Servo laserTilt;

    bool servosAttached;
    float currentCameraPanDeg;
    float currentCameraTiltDeg;
    float currentLaserPanDeg;
    float currentLaserTiltDeg;

    bool directionMoveActive;
    float directionTargetPanDeg;
    float directionTargetTiltDeg;
    float directionMoveSpeedDegPerSec;

    bool circleDrawActive;
    float circleCenterPanDeg;
    float circleCenterTiltDeg;
    float circleRadiusDeg;
    float circleAngularSpeedDegPerSec;
    int circleRequestedRotations;
    float circleProgressDeg;

    unsigned long lastMotionUpdateMs;

    void applyLaserAngles(float panDeg, float tiltDeg);
    void cancelDirectionMove();
    void cancelCircleDraw();
};

#endif
