#include <Arduino.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

#include "config.h"
#include "laser_control.h"
#include "mecanum_motor.h"
#include "servo_control.h"
#include "state_estimator.h"

namespace {
MecanumMotor g_motors;
StateEstimator g_estimator;
ServoController g_servos;
LaserController g_laser(LASER_PIN);

struct TargetState {
    bool active;
    bool reached;
    uint32_t id;
    uint32_t last_command_ms;
    float x;
    float y;
    float yaw;
};

TargetState g_target = {false, false, 0U, 0U, 0.0f, 0.0f, 0.0f};

float g_cmd_vx = 0.0f;
float g_cmd_vy = 0.0f;
float g_cmd_wz = 0.0f;
float g_last_xy_err = 0.0f;
float g_last_yaw_err = 0.0f;

uint8_t g_reached_hold_count = 0U;
uint32_t g_burst_cycle_start_ms = 0U;

uint32_t g_last_status_ms = 0U;
uint32_t g_last_predict_us = 0U;

char g_serial_line[SERIAL_LINE_BUFFER_SIZE];
size_t g_serial_len = 0U;

float clampf(float value, float lo, float hi) {
    if (value < lo) return lo;
    if (value > hi) return hi;
    return value;
}

float normalizeAngle(float angle) {
    while (angle > PI) angle -= 2.0f * PI;
    while (angle < -PI) angle += 2.0f * PI;
    return angle;
}

float signf_nonzero(float v) {
    return (v >= 0.0f) ? 1.0f : -1.0f;
}

bool poseIsFreshForNavigation() {
    const uint32_t stale_ms = g_estimator.getStalenessMs();
    return !(stale_ms == UINT32_MAX || stale_ms > POSE_CORRECTION_STALE_MS);
}

bool burstIsOn(uint32_t now_ms) {
    const uint32_t cycle_ms = NAV_BURST_ON_MS + NAV_BURST_OFF_MS;
    if (cycle_ms == 0U) return false;
    const uint32_t phase = (now_ms - g_burst_cycle_start_ms) % cycle_ms;
    return phase < NAV_BURST_ON_MS;
}

const char* findJsonValueStart(const char* line, const char* key) {
    const char* key_pos = strstr(line, key);
    if (key_pos == nullptr) return nullptr;

    const char* colon_pos = strchr(key_pos, ':');
    if (colon_pos == nullptr) return nullptr;

    const char* value_pos = colon_pos + 1;
    while (*value_pos == ' ' || *value_pos == '\t') ++value_pos;
    return value_pos;
}

bool extractJsonString(const char* line, const char* key, char* out, size_t out_size) {
    const char* value_pos = findJsonValueStart(line, key);
    if (value_pos == nullptr || *value_pos != '"') return false;

    ++value_pos;
    const char* end_quote = strchr(value_pos, '"');
    if (end_quote == nullptr) return false;

    const size_t len = static_cast<size_t>(end_quote - value_pos);
    if (len >= out_size) return false;

    memcpy(out, value_pos, len);
    out[len] = '\0';
    return true;
}

bool extractJsonFloat(const char* line, const char* key, float* out) {
    const char* value_pos = findJsonValueStart(line, key);
    if (value_pos == nullptr) return false;

    char token[24];
    size_t idx = 0;
    while (*value_pos != '\0' && *value_pos != ',' && *value_pos != '}' && idx < sizeof(token) - 1) {
        token[idx++] = *value_pos;
        ++value_pos;
    }
    token[idx] = '\0';

    if (idx == 0) return false;

    *out = static_cast<float>(atof(token));
    return isfinite(*out);
}

bool extractJsonUInt(const char* line, const char* key, uint32_t* out) {
    const char* value_pos = findJsonValueStart(line, key);
    if (value_pos == nullptr) return false;

    char token[16];
    size_t idx = 0;
    while (*value_pos != '\0' && *value_pos != ',' && *value_pos != '}' && idx < sizeof(token) - 1) {
        token[idx++] = *value_pos;
        ++value_pos;
    }
    token[idx] = '\0';

    if (idx == 0) return false;

    const long parsed = atol(token);
    if (parsed < 0) return false;

    *out = static_cast<uint32_t>(parsed);
    return true;
}

bool parseSimpleTargetLine(const char* line, float* x, float* y, float* yaw_deg) {
    if (line == nullptr) return false;

    char buffer[96];
    strncpy(buffer, line, sizeof(buffer) - 1);
    buffer[sizeof(buffer) - 1] = '\0';

    char* token = strtok(buffer, " ,\t");
    if (!token) return false;
    *x = atof(token);

    token = strtok(nullptr, " ,\t");
    if (!token) return false;
    *y = atof(token);

    token = strtok(nullptr, " ,\t");
    if (!token) return false;
    *yaw_deg = atof(token);

    return true;
}

void sendAck(uint32_t id) {
    Serial.print("{\"type\":\"ack\",\"id\":");
    Serial.print(id);
    Serial.println("}");
}

void sendNack(uint32_t id, const char* reason) {
    Serial.print("{\"type\":\"nack\",\"id\":");
    Serial.print(id);
    Serial.print(",\"reason\":\"");
    Serial.print(reason);
    Serial.println("\"}");
}

void publishStatus() {
    const uint32_t stale_ms = g_estimator.getStalenessMs();

    Serial.print("{\"type\":\"status\"");
    Serial.print(",\"x\":");
    Serial.print(g_estimator.getX(), 4);
    Serial.print(",\"y\":");
    Serial.print(g_estimator.getY(), 4);
    Serial.print(",\"yaw\":");
    Serial.print(g_estimator.getYaw(), 4);
    Serial.print(",\"vx_cmd\":");
    Serial.print(g_cmd_vx, 4);
    Serial.print(",\"vy_cmd\":");
    Serial.print(g_cmd_vy, 4);
    Serial.print(",\"wz_cmd\":");
    Serial.print(g_cmd_wz, 4);
    Serial.print(",\"target_active\":");
    Serial.print(g_target.active ? 1 : 0);
    Serial.print(",\"target_id\":");
    Serial.print(g_target.id);
    Serial.print(",\"target_reached\":");
    Serial.print(g_target.reached ? 1 : 0);
    Serial.print(",\"err_xy\":");
    Serial.print(g_last_xy_err, 4);
    Serial.print(",\"err_yaw\":");
    Serial.print(g_last_yaw_err, 4);
    Serial.print(",\"stale_ms\":");
    if (stale_ms == UINT32_MAX) {
        Serial.print(-1);
    } else {
        Serial.print(stale_ms);
    }
    Serial.print(",\"pose_stale\":");
    Serial.print((stale_ms > POSE_CORRECTION_STALE_MS) ? 1 : 0);
    Serial.println("}");
}

void handleTargetCommand(const char* line) {
    uint32_t id = 0U;
    float x = 0.0f;
    float y = 0.0f;
    float yaw = 0.0f;

    if (!extractJsonUInt(line, "\"id\"", &id)) {
        sendNack(0U, "missing_id");
        return;
    }

    if (!extractJsonFloat(line, "\"x\"", &x) ||
        !extractJsonFloat(line, "\"y\"", &y) ||
        !extractJsonFloat(line, "\"yaw\"", &yaw)) {
        sendNack(id, "missing_target_fields");
        return;
    }

    g_target.active = true;
    g_target.reached = false;
    g_target.id = id;
    g_target.last_command_ms = millis();
    g_target.x = x;
    g_target.y = y;
    g_target.yaw = normalizeAngle(yaw);

    g_reached_hold_count = 0U;
    g_burst_cycle_start_ms = millis();

    sendAck(id);
}

void handlePoseCorrection(const char* line) {
    float x = 0.0f;
    float y = 0.0f;
    float yaw = 0.0f;
    float confidence = 0.0f;

    if (!extractJsonFloat(line, "\"x\"", &x) ||
        !extractJsonFloat(line, "\"y\"", &y) ||
        !extractJsonFloat(line, "\"yaw\"", &yaw) ||
        !extractJsonFloat(line, "\"confidence\"", &confidence)) {
        return;
    }

    const float clamped_conf = clampf(confidence, 0.0f, 1.0f);
    if (clamped_conf <= 0.0f) return;

    g_estimator.correct(x, y, normalizeAngle(yaw), clamped_conf);
}

void handleCancelCommand() {
    g_target.active = false;
    g_target.reached = false;
    g_cmd_vx = 0.0f;
    g_cmd_vy = 0.0f;
    g_cmd_wz = 0.0f;
    g_reached_hold_count = 0U;
    g_burst_cycle_start_ms = millis();
}

void acceptSimpleTarget(float x, float y, float yaw_deg) {
    g_target.active = true;
    g_target.reached = false;
    g_target.id++;
    g_target.last_command_ms = millis();
    g_target.x = x;
    g_target.y = y;
    g_target.yaw = normalizeAngle(yaw_deg * PI / 180.0f);

    g_reached_hold_count = 0U;
    g_burst_cycle_start_ms = millis();

    Serial.print("{\"type\":\"ack\",\"id\":");
    Serial.print(g_target.id);
    Serial.print(",\"mode\":\"simple\",\"x\":");
    Serial.print(g_target.x, 4);
    Serial.print(",\"y\":");
    Serial.print(g_target.y, 4);
    Serial.print(",\"yaw_deg\":");
    Serial.print(yaw_deg, 2);
    Serial.println("}");
}

void dispatchLine(const char* line) {
    if (line == nullptr || line[0] == '\0') return;

    // JSON mode
    if (line[0] == '{') {
        char type[24];
        if (!extractJsonString(line, "\"type\"", type, sizeof(type))) return;

        if (strcmp(type, "target") == 0) {
            handleTargetCommand(line);
            return;
        }

        if (strcmp(type, "pose_correction") == 0) {
            handlePoseCorrection(line);
            return;
        }

        if (strcmp(type, "cancel_target") == 0) {
            handleCancelCommand();
            return;
        }

        if (strcmp(type, "ping") == 0) {
            Serial.println("{\"type\":\"pong\"}");
            return;
        }

        return;
    }

    // Simple mode:
    //   1.9 -0.4 0
    float x = 0.0f;
    float y = 0.0f;
    float yaw_deg = 0.0f;
    if (parseSimpleTargetLine(line, &x, &y, &yaw_deg)) {
        acceptSimpleTarget(x, y, yaw_deg);
        return;
    }

    // Optional simple cancel
    if (strcmp(line, "cancel") == 0) {
        handleCancelCommand();
        Serial.println("{\"type\":\"cancelled\"}");
        return;
    }

    Serial.println("{\"type\":\"nack\",\"reason\":\"unknown_command\"}");
}

void processSerialInput() {
    while (Serial.available() > 0) {
        const char ch = static_cast<char>(Serial.read());

        if (ch == '\n' || ch == '\r') {
            if (g_serial_len > 0) {
                g_serial_line[g_serial_len] = '\0';
                dispatchLine(g_serial_line);
                g_serial_len = 0U;
            }
            continue;
        }

        if (g_serial_len >= SERIAL_LINE_BUFFER_SIZE - 1) {
            g_serial_len = 0U;
            continue;
        }

        g_serial_line[g_serial_len++] = ch;
    }
}

void updateNavigator() {
    if (!g_target.active) {
        g_cmd_vx = 0.0f;
        g_cmd_vy = 0.0f;
        g_cmd_wz = 0.0f;
        g_last_xy_err = 0.0f;
        g_last_yaw_err = 0.0f;
        g_reached_hold_count = 0U;
        g_burst_cycle_start_ms = millis();
        return;
    }

    const uint32_t now_ms = millis();

    if ((now_ms - g_target.last_command_ms) > TARGET_COMMAND_TIMEOUT_MS) {
        g_target.active = false;
        g_target.reached = false;
        g_cmd_vx = 0.0f;
        g_cmd_vy = 0.0f;
        g_cmd_wz = 0.0f;
        g_reached_hold_count = 0U;
        g_burst_cycle_start_ms = now_ms;
        Serial.println("{\"type\":\"target_timeout\"}");
        return;
    }

    if (!poseIsFreshForNavigation()) {
        g_cmd_vx = 0.0f;
        g_cmd_vy = 0.0f;
        g_cmd_wz = 0.0f;
        g_target.reached = false;
        g_reached_hold_count = 0U;
        g_burst_cycle_start_ms = now_ms;
        return;
    }

    const float x = g_estimator.getX();
    const float y = g_estimator.getY();
    const float yaw = g_estimator.getYaw();

    const float dx_world = g_target.x - x;
    const float dy_world = g_target.y - y;

    g_last_xy_err = sqrtf(dx_world * dx_world + dy_world * dy_world);
    g_last_yaw_err = normalizeAngle(g_target.yaw - yaw);

    if (g_last_xy_err <= NAV_TARGET_XY_TOL_M &&
        fabsf(g_last_yaw_err) <= NAV_TARGET_YAW_TOL_RAD) {
        g_reached_hold_count++;
        g_cmd_vx = 0.0f;
        g_cmd_vy = 0.0f;
        g_cmd_wz = 0.0f;

        if (g_reached_hold_count >= NAV_REACHED_HOLD_CYCLES) {
            if (!g_target.reached) {
                g_target.reached = true;
                Serial.print("{\"type\":\"reached\",\"id\":");
                Serial.print(g_target.id);
                Serial.print(",\"x\":");
                Serial.print(g_estimator.getX(), 4);
                Serial.print(",\"y\":");
                Serial.print(g_estimator.getY(), 4);
                Serial.print(",\"yaw\":");
                Serial.print(g_estimator.getYaw(), 4);
                Serial.println("}");
            }
        }
        return;
    }

    g_target.reached = false;
    g_reached_hold_count = 0U;

    const float cy = cosf(yaw);
    const float sy = sinf(yaw);

    const float err_x_body = cy * dx_world + sy * dy_world;
    const float err_y_body = -sy * dx_world + cy * dy_world;

    const bool in_xy_burst_zone = g_last_xy_err <= NAV_BURST_XY_RADIUS_M;
    const bool in_yaw_burst_zone = fabsf(g_last_yaw_err) <= NAV_BURST_YAW_RADIUS_RAD;

    if (in_xy_burst_zone || in_yaw_burst_zone) {
        if (g_burst_cycle_start_ms == 0U) {
            g_burst_cycle_start_ms = now_ms;
        }

        if (!burstIsOn(now_ms)) {
            g_cmd_vx = 0.0f;
            g_cmd_vy = 0.0f;
            g_cmd_wz = 0.0f;
            return;
        }

        if (fabsf(g_last_yaw_err) > NAV_TARGET_YAW_TOL_RAD) {
            g_cmd_vx = 0.0f;
            g_cmd_vy = 0.0f;
            g_cmd_wz = signf_nonzero(g_last_yaw_err) * NAV_BURST_WZ_NORM;
            return;
        }

        if (fabsf(err_x_body) > NAV_TARGET_XY_TOL_M) {
            g_cmd_vx = signf_nonzero(err_x_body) * NAV_BURST_VXY_NORM * 0.5f;
            g_cmd_vy = 0.0f;
            g_cmd_wz = 0.0f;
            return;
        }

        if (fabsf(err_y_body) > NAV_TARGET_XY_TOL_M) {
            g_cmd_vx = 0.0f;
            g_cmd_vy = signf_nonzero(err_y_body) * NAV_BURST_VXY_NORM * 0.5f;
            g_cmd_wz = 0.0f;
            return;
        }

        g_cmd_vx = 0.0f;
        g_cmd_vy = 0.0f;
        g_cmd_wz = 0.0f;
        return;
    }

    g_burst_cycle_start_ms = now_ms;

    g_cmd_vx = clampf(NAV_POSITION_KP * err_x_body, -NAV_MAX_VXY_NORM, NAV_MAX_VXY_NORM);
    g_cmd_vy = clampf(NAV_POSITION_KP * err_y_body, -NAV_MAX_VXY_NORM, NAV_MAX_VXY_NORM);
    g_cmd_wz = clampf(NAV_YAW_KP * g_last_yaw_err, -NAV_MAX_WZ_NORM, NAV_MAX_WZ_NORM);
}

void updatePredictor() {
    const uint32_t now_us = micros();
    if (g_last_predict_us == 0U) {
        g_last_predict_us = now_us;
        return;
    }

    const uint32_t dt_us = now_us - g_last_predict_us;
    g_last_predict_us = now_us;

    const float dt_s = static_cast<float>(dt_us) / 1000000.0f;
    g_estimator.predict(
        g_cmd_vx * NORM_TO_MPS,
        g_cmd_vy * NORM_TO_MPS,
        g_cmd_wz * NORM_TO_RAD_S,
        dt_s);
}

void maybePublishStatus() {
    const uint32_t now_ms = millis();
    if ((now_ms - g_last_status_ms) < STATUS_PUBLISH_PERIOD_MS) {
        return;
    }
    g_last_status_ms = now_ms;
    publishStatus();
}

} // namespace

void setup() {
    Serial.begin(SERIAL_BAUD_RATE);
    Serial.setTimeout(SERIAL_TIMEOUT_MS);

    g_motors.begin();
    g_servos.begin();
    g_laser.begin();
    g_estimator.reset(0.0f, 0.0f, 0.0f);
    g_burst_cycle_start_ms = millis();

    Serial.println("{\"type\":\"boot\",\"status\":\"ready\"}");
    Serial.println("{\"type\":\"info\",\"msg\":\"Send target as: x y yawDeg   example: 1.9 -0.4 0\"}");
}

void loop() {
    processSerialInput();
    updateNavigator();
    updatePredictor();
    g_motors.move(g_cmd_vx, g_cmd_vy, g_cmd_wz);
    maybePublishStatus();
}
