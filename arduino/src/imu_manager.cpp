#include "imu_manager.h"

ImuManager::ImuManager() : mpu(IMU_I2C_ADDR), dmpReady(false), devStatus(0), packetSize(0), fifoCount(0) {
    ypr[0] = 0.0f;
    ypr[1] = 0.0f;
    ypr[2] = 0.0f;
}

bool ImuManager::begin() {
    // Initialize I2C - pins are 20 (SDA) and 21 (SCL) on Arduino Mega
    Wire.begin();
    Wire.setClock(IMU_I2C_CLOCK_HZ);

    Serial.println(F("Initializing I2C devices..."));
    mpu.initialize();

    Serial.println(F("Testing device connections..."));
    if (!mpu.testConnection()) {
        Serial.println(F("MPU6050 connection failed"));
        return false;
    }

    Serial.println(F("Initializing DMP..."));
    devStatus = mpu.dmpInitialize();

    // supply your own gyro offsets here, scaled for min sensitivity
    // These should ideally be calibrated for the specific hardware
    mpu.setXGyroOffset(0);
    mpu.setYGyroOffset(0);
    mpu.setZGyroOffset(0);
    mpu.setZAccelOffset(1688); // 1688 factory default for my test chip

    // make sure it worked (returns 0 if so)
    if (devStatus == 0) {
        // Calibration Time: generate offsets and calibrate our MPU6050
        // This will take a few seconds and the robot should be stationary
        Serial.println(F("Calibrating IMU... Please keep it stationary."));
        mpu.CalibrateAccel(6);
        mpu.CalibrateGyro(6);
        mpu.PrintActiveOffsets();

        // turn on the DMP, now that it's ready
        Serial.println(F("Enabling DMP..."));
        mpu.setDMPEnabled(true);

        dmpReady = true;

        // get expected DMP packet size for later comparison
        packetSize = mpu.dmpGetFIFOPacketSize();
        Serial.print(F("DMP packet size: "));
        Serial.println(packetSize);
    } else {
        // ERROR!
        // 1 = initial memory load failed
        // 2 = DMP configuration updates failed
        // (if it's going to break, usually the code will be 1)
        Serial.print(F("DMP Initialization failed (code "));
        Serial.print(devStatus);
        Serial.println(F(")"));
        return false;
    }

    return true;
}

bool ImuManager::update() {
    if (!dmpReady) {
        return false;
    }

    fifoCount = mpu.getFIFOCount();

    // Recover from FIFO overflow without blocking.
    if (fifoCount == 1024) {
        mpu.resetFIFO();
        return false;
    }

    if (fifoCount < packetSize) {
        return false;
    }

    // Drop older packets and keep only the newest sample.
    while (fifoCount >= (packetSize * 2U)) {
        mpu.getFIFOBytes(fifoBuffer, packetSize);
        fifoCount -= packetSize;
    }

    mpu.getFIFOBytes(fifoBuffer, packetSize);

    // Get Orientation
    mpu.dmpGetQuaternion(&q, fifoBuffer);
    mpu.dmpGetGravity(&gravity, &q);
    mpu.dmpGetYawPitchRoll(ypr, &q, &gravity);

    // Get Linear Acceleration (gravity removed)
    mpu.dmpGetAccel(&aa, fifoBuffer);
    mpu.dmpGetLinearAccel(&aaReal, &aa, &gravity);

    // Get Gyro data
    mpu.dmpGetGyro(gyro, fifoBuffer);

    return true;
}
