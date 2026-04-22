#ifndef LASER_CONTROL_H
#define LASER_CONTROL_H

#include <Arduino.h>

class LaserController {
public:
    LaserController(uint8_t pin);
    void begin();
    void turnOn();
    void turnOff();
    void toggle();
    bool isOn() const;

private:
    uint8_t laserPin;
    bool laserState;
};

#endif
