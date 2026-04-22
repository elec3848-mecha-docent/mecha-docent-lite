#include "laser_control.h"

LaserController::LaserController(uint8_t pin) : laserPin(pin), laserState(false) {}

void LaserController::begin() {
    pinMode(laserPin, OUTPUT);
    turnOff();
}

void LaserController::turnOn() {
    digitalWrite(laserPin, HIGH);
    laserState = true;
}

void LaserController::turnOff() {
    digitalWrite(laserPin, LOW);
    laserState = false;
}

void LaserController::toggle() {
    if (laserState) {
        turnOff();
    } else {
        turnOn();
    }
}

bool LaserController::isOn() const {
    return laserState;
}