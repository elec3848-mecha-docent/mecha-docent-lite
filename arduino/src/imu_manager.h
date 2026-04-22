#ifndef IMU_MANAGER_H
#define IMU_MANAGER_H

#include <Arduino.h>
#include <I2Cdev.h>
#include <MPU6050_6Axis_MotionApps20.h>
#include <Wire.h>
#include "config.h"

/**
 * @brief Manages the MPU6050 IMU using the internal Digital Motion Processor (DMP).
 * 
 * Provides 100Hz orientation (Yaw/Pitch/Roll) and raw/real acceleration data.
 * Offloading fusion to the DMP saves significant CPU cycles on the ATmega2560.
 */
class ImuManager {
public:
    ImuManager();

    /**
     * @brief Initializes I2C, MPU6050, and DMP.
     * @return true if initialization was successful.
     */
    bool begin();

    /**
     * @brief Updates the IMU state by reading from the DMP FIFO.
     * Should be called frequently (at least as fast as the DMP output rate, e.g., 100Hz).
     * @return true if new data was read.
     */
    bool update();

    // Orientation (Radians)
    float getYaw() const { return ypr[0]; }
    float getPitch() const { return ypr[1]; }
    float getRoll() const { return ypr[2]; }

    // Acceleration (m/s^2) - Linear acceleration (gravity removed)
    float getAccelX() const { return aaReal.x * (9.80665f / 8192.0f); } // Assuming ±4g range for DMP
    float getAccelY() const { return aaReal.y * (9.80665f / 8192.0f); }
    float getAccelZ() const { return aaReal.z * (9.80665f / 8192.0f); }

    // Angular Velocity (rad/s)
    float getGyroX() const { return gyro[0] * (PI / 180.0f / 131.0f); } // Assuming ±250 deg/s
    float getGyroY() const { return gyro[1] * (PI / 180.0f / 131.0f); }
    float getGyroZ() const { return gyro[2] * (PI / 180.0f / 131.0f); }

    bool isReady() const { return dmpReady; }

private:
    MPU6050 mpu;

    bool dmpReady;           // set true if DMP init was successful
    uint8_t mpuIntStatus;   // holds actual interrupt status byte from MPU
    uint8_t devStatus;      // return status after each device operation (0 = success, !0 = error)
    uint16_t packetSize;    // expected DMP packet size (default is 42 bytes)
    uint16_t fifoCount;     // count of all bytes currently in FIFO
    uint8_t fifoBuffer[64]; // FIFO storage buffer

    // Orientation/Motion vars
    Quaternion q;           // [w, x, y, z]         quaternion container
    VectorInt16 aa;         // [x, y, z]            accel sensor measurements
    VectorInt16 aaReal;     // [x, y, z]            gravity-compensated accel sensor measurements
    VectorFloat gravity;    // [x, y, z]            gravity vector
    float ypr[3];           // [yaw, pitch, roll]   yaw/pitch/roll container and gravity vector
    int16_t gyro[3];        // [x, y, z]            raw gyro values
};

#endif // IMU_MANAGER_H
