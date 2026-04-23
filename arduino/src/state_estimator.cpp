#include "state_estimator.h"
#include <math.h>

// ---- Tuning constants ----
// Process noise per second (position and yaw grow with commanded motion).
static constexpr float kQxy  = 0.01f;   // m^2 / s
static constexpr float kQyaw = 0.05f;   // rad^2 / s

// Base measurement noise (divided by confidence at correction time).
// These assume AprilTag corrections have ~2 cm / ~5 deg 1-sigma error at
// full confidence.  Raise kRxy / kRyaw if corrections are noisier.
static constexpr float kRxy  = 0.0005f;
static constexpr float kRyaw = 0.0030f;

// ---- Constructor ----

StateEstimator::StateEstimator()
    : _x(0.0f), _y(0.0f), _yaw(0.0f),
      _last_correct_ms(0), _initialized(false)
{
    for (int i = 0; i < 9; ++i) _P[i] = 0.0f;
    _P[0] = 1.0f; _P[4] = 1.0f; _P[8] = 1.0f;  // large initial uncertainty
}

// ---- Public API ----

void StateEstimator::reset(float x_m, float y_m, float yaw_rad) {
    _x   = x_m;
    _y   = y_m;
    _yaw = _normalize_angle(yaw_rad);
    for (int i = 0; i < 9; ++i) _P[i] = 0.0f;
    _P[0] = 0.01f; _P[4] = 0.01f; _P[8] = 0.01f;  // tight reset covariance
    _last_correct_ms = millis();
    _initialized = true;
}

void StateEstimator::predict(float vx_body, float vy_body, float wz, float dt_s) {
    if (dt_s <= 0.0f || dt_s > 0.5f) return;   // guard unreasonable dt

    const float cy = cosf(_yaw);
    const float sy = sinf(_yaw);

    // State propagation (global frame).
    _x   += (vx_body * cy - vy_body * sy) * dt_s;
    _y   += (vx_body * sy + vy_body * cy) * dt_s;
    _yaw  = _normalize_angle(_yaw + wz * dt_s);

    // Jacobian of state transition w.r.t. state (F):
    //   df_x  / dyaw = -(vx*sin + vy*cos) * dt
    //   df_y  / dyaw =  (vx*cos - vy*sin) * dt
    const float f02 = -(vx_body * sy + vy_body * cy) * dt_s;
    const float f12 =  (vx_body * cy - vy_body * sy) * dt_s;

    const float F[9] = {
        1.0f, 0.0f, f02,
        0.0f, 1.0f, f12,
        0.0f, 0.0f, 1.0f,
    };

    // P = F * P * F^T + Q
    float FP[9];
    _mat3_mul(F, _P, FP);

    const float Ft[9] = {
        F[0], F[3], F[6],
        F[1], F[4], F[7],
        F[2], F[5], F[8],
    };
    float FPFt[9];
    _mat3_mul(FP, Ft, FPFt);

    // Add diagonal process noise scaled by dt.
    const float q_xy  = kQxy  * dt_s;
    const float q_yaw = kQyaw * dt_s;
    FPFt[0] += q_xy;
    FPFt[4] += q_xy;
    FPFt[8] += q_yaw;

    for (int i = 0; i < 9; ++i) _P[i] = FPFt[i];
}

void StateEstimator::correct(float x_m, float y_m, float yaw_rad, float confidence) {
    if (confidence <= 0.0f) return;
    const float c = (confidence > 1.0f) ? 1.0f : confidence;

    // Measurement noise R = R_base / confidence (high confidence → tight noise).
    const float r_xy  = kRxy  / c;
    const float r_yaw = kRyaw / c;

    // S = P + R  (H = I, so S = H*P*H^T + R = P + R)
    float S[9];
    for (int i = 0; i < 9; ++i) S[i] = _P[i];
    S[0] += r_xy;
    S[4] += r_xy;
    S[8] += r_yaw;

    float Sinv[9];
    if (!_mat3_inv(S, Sinv)) return;    // singular matrix — skip update

    // K = P * S^-1
    float K[9];
    _mat3_mul(_P, Sinv, K);

    // Innovation: y = measurement - state (with yaw wrap)
    const float inn0 = x_m   - _x;
    const float inn1 = y_m   - _y;
    const float inn2 = _normalize_angle(yaw_rad - _yaw);

    // State update: state += K * innovation
    _x   += K[0]*inn0 + K[1]*inn1 + K[2]*inn2;
    _y   += K[3]*inn0 + K[4]*inn1 + K[5]*inn2;
    _yaw  = _normalize_angle(_yaw + K[6]*inn0 + K[7]*inn1 + K[8]*inn2);

    // Covariance update: P = (I - K) * P
    const float IK[9] = {
        1.0f - K[0], -K[1],        -K[2],
        -K[3],        1.0f - K[4], -K[5],
        -K[6],       -K[7],         1.0f - K[8],
    };
    float Pnew[9];
    _mat3_mul(IK, _P, Pnew);
    for (int i = 0; i < 9; ++i) _P[i] = Pnew[i];

    _last_correct_ms = millis();
    _initialized     = true;
}

uint32_t StateEstimator::getStalenessMs() const {
    if (!_initialized) return UINT32_MAX;
    const uint32_t now = millis();
    return (now >= _last_correct_ms) ? (now - _last_correct_ms) : UINT32_MAX;
}

// ---- Private helpers ----

float StateEstimator::_normalize_angle(float a) {
    while (a >  PI) a -= 2.0f * PI;
    while (a < -PI) a += 2.0f * PI;
    return a;
}

void StateEstimator::_mat3_mul(const float A[9], const float B[9], float out[9]) {
    for (int r = 0; r < 3; ++r) {
        for (int c = 0; c < 3; ++c) {
            float s = 0.0f;
            for (int k = 0; k < 3; ++k)
                s += A[r * 3 + k] * B[k * 3 + c];
            out[r * 3 + c] = s;
        }
    }
}

bool StateEstimator::_mat3_inv(const float M[9], float out[9]) {
    const float a = M[0], b = M[1], c = M[2];
    const float d = M[3], e = M[4], f = M[5];
    const float g = M[6], h = M[7], i = M[8];

    const float det = a * (e * i - f * h)
                    - b * (d * i - f * g)
                    + c * (d * h - e * g);
    if (fabsf(det) < 1e-12f) return false;

    const float inv_det = 1.0f / det;
    out[0] =  (e * i - f * h) * inv_det;
    out[1] = -(b * i - c * h) * inv_det;
    out[2] =  (b * f - c * e) * inv_det;
    out[3] = -(d * i - f * g) * inv_det;
    out[4] =  (a * i - c * g) * inv_det;
    out[5] = -(a * f - c * d) * inv_det;
    out[6] =  (d * h - e * g) * inv_det;
    out[7] = -(a * h - b * g) * inv_det;
    out[8] =  (a * e - b * d) * inv_det;
    return true;
}
