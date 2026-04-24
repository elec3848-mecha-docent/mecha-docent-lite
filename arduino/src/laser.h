/**
 * @file laser.h
 * @brief Simple on/off wrapper for the laser module.
 *
 * :class:`LaserController` drives a laser diode module via a single digital
 * output pin (default: A10, declared in config.h).  State is cached
 * internally so :func:`isOn()` never needs to read back the pin.
 */
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
