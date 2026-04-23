/**
 * @file motor.h
 * @brief Mecanum-wheel motor driver and quadrature encoder interface.
 */
#pragma once
#include <Arduino.h>

// Initialize motor GPIO and attach quadrature encoder interrupts.
void setupMotor();

// Command robot motion directly as signed PWM components in range [-255, 255].
void move(int vx, int vy, int wz);

// Set a non-blocking target pose in meters/radians.
void moveTo(float targetXMeters, float targetYMeters, float targetYawRad);

// Service active moveTo command. Call once per loop.
void moveToService();

// Query/cancel moveTo state.
bool isMoveToActive();
void cancelMoveTo();

// Immediately cut power to all four wheels.
void stopRobot();

// Reset all four encoder tick counters to zero (interrupt-safe).
void resetEncoderCounts();

// Return the mean encoder count across all four wheels (signed).
long getAverageEncoderCount();

// Return the mean of the absolute encoder counts across all four wheels.
long getAverageAbsoluteEncoderCount();

// Individual raw encoder counts (useful for debugging and display).
long getFrontLeftEncoderCount();
long getFrontRightEncoderCount();
long getBackLeftEncoderCount();
long getBackRightEncoderCount();

// Formula target wheel PWMs before sync correction (signed, [-255, 255]).
int getFrontLeftTargetPWM();
int getFrontRightTargetPWM();
int getBackLeftTargetPWM();
int getBackRightTargetPWM();

// Adjust per-wheel PWM values to match expected encoder-rate ratios.
void motorSyncService();

// Update integrated odometry from encoder deltas.
void odometryService();

// Reset odometry pose estimate to origin.
void resetOdometryPose();

// Read integrated odometry pose in meters/radians.
void getOdometryPose(float &xMeters, float &yMeters, float &thetaRad);

// Convenience odometry component getters.
float getOdometryXMeters();
float getOdometryYMeters();
float getOdometryThetaRad();