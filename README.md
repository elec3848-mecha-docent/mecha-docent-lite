# MechaDocent-Lite

A museum guide robot system combining an Arduino-based mobile platform with an intelligent Raspberry Pi brain. The robot navigates between exhibits, delivers contextual explanations powered by a local LLM, and adapts its tour in real time based on visitor feedback.

<img width="1079" height="601" alt="image" src="https://github.com/user-attachments/assets/1467a8ef-a0f8-4f4a-baad-ad496fef0fc4" />

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Hardware Requirements](#hardware-requirements)
4. [Software Requirements](#software-requirements)
5. [Project Structure](#project-structure)
6. [Subsystems](#subsystems)
   - [Arduino Firmware](#arduino-firmware)
   - [LLM Dialogue Engine](#llm-dialogue-engine)
   - [Tour FSM](#tour-fsm)
   - [Speech (STT / TTS)](#speech-stt--tts)
   - [Screen & Eye Display](#screen--eye-display)
   - [Camera](#camera)
   - [Localization](#localization)
   - [Robot Serial Protocol](#robot-serial-protocol)
7. [Setup & Installation](#setup--installation)
8. [Running the Demos](#running-the-demos)
9. [Configuration](#configuration)
10. [Arduino Serial Command Reference](#arduino-serial-command-reference)
11. [Adding New Exhibits](#adding-new-exhibits)

---

## System Overview

MechaDocent-Lite ("Medo") is a lite implementation of a museum docent robot. It can:

- Greet visitors and profile their interests via natural conversation.
- Plan a personalised tour route through museum exhibits.
- Navigate to each painting using mecanum-wheel odometry.
- Highlight exhibit features with a laser pointer mounted on a servo pan/tilt rig.
- Adapt explanations (brief ↔ detailed) based on visitor sentiment and feedback.
- Track its own position using AprilTag visual markers fused with wheel odometry via an Extended Kalman Filter.
- Display animated eyes on a connected screen.

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Raspberry Pi                          │
│                                                          │
│  ┌──────────┐   ┌──────────┐  ┌─────────────────────┐    │
│  │ tour_fsm │   │  LLM     │  │   Localization      │    │
│  │ (Determ.)│   │ (Gen.)   │  │   AprilTag + EKF    │    │
│  └────┬─────┘   └────┬─────┘  └────────┬────────────┘    │
│       │              │                 │                 │
│  ┌────▼──────────────▼─────────────────▼──────────────┐  │
│  │           robot_serial (SerialProtocolClient)      │  │
│  └────────────────────────┬───────────────────────────┘  │
│                           │ UART / USB serial            │
│  ┌────────────────────────▼────────────────────────────┐ │
│  │               Raspberry Pi Camera (Picamera2)       │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                          │
│  ┌──────────────┐  ┌────────────────┐                    │
│  │  Speech STT  │  │  TTS + Screen  │                    │
│  │  (Whisper)   │  │  (Supertonic)  │                    │
│  └──────────────┘  └────────────────┘                    │
└──────────────────────────┬───────────────────────────────┘
                           │ USB Serial (115200 baud)
┌──────────────────────────▼───────────────────────────────┐
│                   Arduino Mega 2560                      │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │  Motor Drive │  │  Servo Ctrl  │  │  Laser Ctrl    │  │
│  │  (Mecanum)   │  │  (4x servos) │  │  (A10 pin)     │  │
│  └──────────────┘  └──────────────┘  └────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

**Data flow summary:**

1. The Raspberry Pi runs either the deterministic `tour_fsm` or the generative `LLM` orchestrator.
2. Both send movement and laser commands through `SerialProtocolClient` over USB serial.
3. The Arduino executes low-level motor/servo/laser control and streams back odometry.
4. The localization module uses the camera and AprilTag markers to correct the position estimate.

---

## Hardware Requirements

| Component | Specification |
|---|---|
| Robot compute | Raspberry Pi 4 (4 GB+ recommended) |
| Microcontroller | Arduino Mega 2560 |
| Drive system | 4× mecanum wheels with DC motors and quadrature encoders |
| Camera | Raspberry Pi Camera Module (Picamera2 compatible) |
| Servos | 4× standard servo (camera pan, camera tilt, laser pan, laser tilt) |
| Laser | 5 mW laser module wired to Arduino pin A10 |
| Display | HDMI monitor or touchscreen for eye animations |
| Audio in | USB microphone or compatible input device (index 1 by default) |
| Audio out | USB speaker or compatible output device (index 1 by default) |
| Localization | AprilTag markers (tag36h11 family) placed around the museum |

**Motor pin mapping (Arduino Mega)** — see [arduino/src/config.h](arduino/src/config.h) for the full pin list.

---

## Software Requirements

### Raspberry Pi

- Python 3.10+
- Dependencies listed in [rpi/requirements.txt](rpi/requirements.txt)

Key packages:

| Package | Purpose |
|---|---|
| `llama-cpp-python` | Local LLM inference (llama.cpp backend) |
| `faster-whisper` | Speech-to-text |
| `supertonic` | Neural TTS |
| `sounddevice` | Audio I/O |
| `webrtcvad` | Voice activity detection |
| `picamera2` | Raspberry Pi camera |
| `opencv-python` | Image processing |
| `pupil-apriltags` | AprilTag detection |
| `pyserial` | Arduino serial communication |
| `numpy`, `scipy` | Numerics / signal resampling |

### Arduino

- PlatformIO (VS Code extension recommended)
- `paulstoffregen/Servo` v1.3.0 (declared in [arduino/platformio.ini](arduino/platformio.ini))

---

## Project Structure

```
mecha-docent-lite/
├── arduino/
│   ├── platformio.ini          # PlatformIO build config (ATmega2560, 115200 baud)
│   └── src/
│       ├── config.h            # All hardware pin/parameter constants
│       ├── main.cpp            # Serial command parser and dispatcher
│       ├── motor.h / motor.cpp # Mecanum drive, odometry, moveTo controller
│       ├── servo.h / servo.cpp # 4-servo controller with smooth animation
│       ├── laser.h / laser.cpp # Laser on/off wrapper
│       ├── example_motor.cpp         # Demo: motor + odometry commands
│       └── example_servo_laser.cpp   # Demo: servo/laser animation sequence
│
└── rpi/
    ├── demo.py                 # Top-level demo launcher
    ├── requirements.txt        # Python dependencies
    │
    ├── LLM/                    # Generative dialogue engine
    │   ├── config.py           # CLI argument parser and defaults
    │   ├── app/
    │   │   └── orchestrator.py # Main conversation loop
    │   ├── core/
    │   │   └── state_machine.py# Conversation FSM (GREETING → FAREWELL)
    │   ├── dialogue/
    │   │   └── templates.py    # Pre-written dialogue snippets
    │   ├── domain/
    │   │   └── models.py       # Dataclasses: VisitorProfile, Exhibit, OutputPacket
    │   ├── generation/
    │   │   ├── llm_client.py   # llama-cpp-python wrapper
    │   │   ├── prompts.py      # LLM prompt builders
    │   │   └── explanation_cache.py # Background pre-generation of exhibit explanations
    │   ├── io_layer/
    │   │   ├── input_reader.py # Timeout-aware stdin reader
    │   │   ├── knowledge_base.py # Exhibit JSON loader/indexer
    │   │   ├── output_store.py # OutputPacket timing + atomic JSON write
    │   │   └── profile_store.py# VisitorProfile persistence
    │   ├── nlp/
    │   │   ├── intent_router.py# Keyword/regex intent classifier
    │   │   └── sentiment.py    # Lexical sentiment scorer
    │   └── planning/
    │       └── tour_planner.py # LLM-driven + fallback tour route planner
    │
    ├── camera/
    │   └── camera.py           # Picamera2 wrapper
    │
    ├── demos/
    │   ├── apriltag_demo.py    # Live localization visualiser
    │   ├── audio_demo.py       # Microphone + TTS test
    │   ├── llm_demo.py         # LLM dialogue demo
    │   ├── screen_demo.py      # Eye animation demo
    │   ├── serial_protocol_demo.py # Serial command sender demo
    │   ├── stt_to_tts_demo.py  # Full speech round-trip demo
    │   └── tour_demo.py        # Main deterministic tour demo
    │
    ├── localization/
    │   ├── config/
    │   │   ├── camera_calibration_rpi.yaml  # Camera intrinsics
    │   │   └── tag_map_example.json         # AprilTag positions
    │   ├── core/
    │   │   ├── camera_calibration.py # Intrinsic matrix loader/saver
    │   │   ├── fusion.py             # Multi-tag pose fusion
    │   │   ├── pose_estimator.py     # solvePnP-based tag pose estimation
    │   │   └── tag_map.py            # AprilTag global position database
    │   ├── filtering/
    │   │   ├── kalman_filter.py      # Extended Kalman Filter (6-state)
    │   │   └── utils.py              # Angle normalisation helpers
    │   └── tracking/
    │       └── localization_tracker.py # Vision + odometry fusion tracker
    │
    ├── models/
    │   ├── opencv_face_detector.prototxt
    │   └── res10_300x300_ssd_iter_140000.caffemodel
    │
    ├── robot_serial/
    │   └── serial_protocol.py  # High-level Arduino serial client
    │
    ├── screen/
    │   ├── display.py          # OpenCV eye renderer (60 FPS)
    │   └── eye_movements.py    # Eye animation presets + face tracking
    │
    ├── speech/
    │   ├── stt.py              # Whisper STT with VAD
    │   └── tts.py              # Supertonic TTS + sounddevice playback
    │
    └── tour/
        ├── painting_positions.json  # Robot nav poses per painting (meters, radians)
        ├── tour_config.py           # TourPolicy, AudioConfig, script constants
        ├── tour_content_loader.py   # Tour content JSON parser
        ├── tour_content.json        # Dialogue templates + artwork scripts (5 paintings)
        └── tour_fsm.py             # Deterministic tour state machine
```

---

## Subsystems

### Arduino Firmware

The firmware runs on an **Arduino Mega 2560** and handles all real-time hardware control. It listens for newline-terminated ASCII commands on the USB serial port at **115200 baud** and replies with status lines.

#### Motor Controller (`motor.cpp`)

- Drives four mecanum wheels independently using PWM + direction pins.
- Integrates quadrature encoder counts into a planar odometry pose (x, y, θ).
- Provides `move(vx, vy, wz)` for direct velocity control and `moveTo(x, y, yaw)` for non-blocking position control.
- Uses a motor-sync service to compensate for wheel speed mismatch using encoder feedback.
- Applies low-speed pulse shaping (pulsing below 45 PWM over 100 ms) to overcome stall torque.

#### Servo Controller (`servo.cpp`)

- Controls four servos: camera pan/tilt and laser pan/tilt (0–180°).
- Smooth motion uses cubic ease-in-out interpolation updated every loop iteration.
- Supports two laser animation modes:
  - **Direction move** — smoothly move laser to a target pan/tilt offset at a given angular speed.
  - **Circle draw** — parametrically trace a circle of a given radius at a given speed for *N* rotations.

#### Laser Controller (`laser.cpp`)

- Simple on/off wrapper around `digitalWrite` for the laser module on pin **A10**.

#### Build Environments (platformio.ini)

| Environment | Source file | Description |
|---|---|---|
| `main` | `main.cpp` | Full robot firmware |
| `example_motor` | `example_motor.cpp` | Motor/odometry demo |
| `example_servo_laser` | `example_servo_laser.cpp` | Servo/laser animation demo |

---

### LLM Dialogue Engine

Located in `rpi/LLM/`. Driven by a **local GGUF model** (default: `qwen2.5-1.5b-instruct-q4_k_m.gguf`) loaded via `llama-cpp-python`.

#### Conversation Flow

```
GREETING
   │
   ├─ YES → PROFILING → PLANNING → EXPLAINING ──────┐
   │                                                │
   │              (bored / switch)                  ▼
   │                      └───────────── REROUTING ─┤
   │                                                │
   └─ NO ─────────────────────────────── FAREWELL ◄─┘
```

1. **GREETING** — Robot introduces itself and asks if the visitor wants a tour.
2. **PROFILING** — Visitor describes interests; LLM extracts age group, background, topics, and preferred pacing.
3. **PLANNING** — LLM orders the exhibit list according to the visitor profile, announces the route.
4. **EXPLAINING** — For each exhibit, the robot delivers chunked explanations (segment A → engagement question → segment B). Chunks are pre-generated in a background thread (`ExplanationCache`).
5. **REROUTING** — If the visitor is bored or requests a switch, remaining exhibits are re-prioritised.
6. **FAREWELL** — Goodbye message; visitor profile is saved to disk.

#### Output Packet

Each turn produces an `OutputPacket` (written atomically to `output.json`):

```json
{
  "speech": "...",
  "head_movement": "painting",
  "state": "explaining",
  "visitor_sentiment": "engaged",
  "laser_target": null,
  "current_exhibit": "starry-night",
  "tour_plan": ["mona-lisa", "starry-night"],
  "pre_speech_delay_ms": 200,
  "post_speech_delay_ms": 400,
  "pause_for_thought_ms": 600
}
```

Valid `head_movement` values: `eye_contact`, `nod-yes`, `nod-no`, `painting`, `direction`, `thinking`, `searching`.

---

### Tour FSM

Located in `rpi/tour/tour_fsm.py`. A fully **deterministic** alternative to the LLM engine — no model inference required at runtime. Dialogue is driven by templated scripts stored in `tour_content.json`.

#### States

| State | Description |
|---|---|
| `GREETING` | Welcome visitor, offer tour |
| `REJECTION_REBUTTAL` | Gently convince a hesitant visitor |
| `ROUTE_SELECTION` | Ask for time preference and interests |
| `PROFILE_GATHERING` | Gather additional profile data |
| `MOVE_TO_ARTWORK` | Navigate to the next painting |
| `ARTWORK_TALK` | Deliver scripted explanation |
| `CHECKIN_QUESTION` | Ask engagement question, adapt verbosity |
| `TOUR_COMPLETE` | Farewell |

#### Content

`tour_content.json` contains 5 artworks by default:
- Mona Lisa
- The Starry Night
- The Last Supper
- Girl with a Pearl Earring
- The Persistence of Memory

Each artwork has `brief` and `detailed` scripts divided into 5 categories: `year`, `technique`, `features`, `history`, `extra`.

---

### Speech (STT / TTS)

| Module | Technology | Notes |
|---|---|---|
| `rpi/speech/stt.py` | faster-whisper (tiny model, int8) | WebRTC VAD; records up to 10 s; resamples to 16 kHz |
| `rpi/speech/tts.py` | Supertonic neural vocoder | Default voice F4; 48 kHz sample rate; ALSA volume set to 100% on init |

---

### Screen & Eye Display

`rpi/screen/display.py` renders an animated pair of eyes using OpenCV at **60 FPS** on a fullscreen window.

- Eyes are rounded rectangles drawn with custom corner-radius rendering.
- All motions use cubic ease-in-out interpolation.
- `eye_movements.py` provides high-level presets: `open_eyes`, `blink`, `happy`, `squint`, `look`.
- A background thread runs randomised idle animations.
- A face-tracking integration point is provided (placeholder).

---

### Camera

`rpi/camera/camera.py` wraps **Picamera2**. Default: 1280×720 @ 30 FPS with 180° hardware rotation (falls back to software rotation on unsupported hardware).

---

### Localization

AprilTag-based visual odometry fused with wheel encoder odometry via an **Extended Kalman Filter**.

```
Camera frame
    │
    ▼
PoseEstimator (solvePnP per tag)
    │
    ▼
fusion.py (weighted average + circular mean for yaw)
    │
    ▼
PlanarPoseKalmanFilter  ←───  Encoder / velocity from Arduino
    │
    ▼
LocalizationTracker (TAG_TRACKING / TAG_LOST_PREDICT / SEARCH_ROTATE)
```

**EKF state vector:** [x, y, yaw, vx, vy, ωz]

Place `tag_map_example.json` entries for each AprilTag in the environment. Camera intrinsics are loaded from `camera_calibration_rpi.yaml`.

---

### Robot Serial Protocol

`rpi/robot_serial/serial_protocol.py` — `SerialProtocolClient` provides a thread-safe Python interface to the Arduino.

All methods ultimately call `send_command(str)`, which acquires `_io_lock` before writing.

`move_to_and_wait(x, y, yaw, timeout_sec)` blocks until the Arduino reports `GOTO=IDLE` or the timeout expires.

---

## Setup & Installation

### 1. Arduino

```bash
# From the arduino/ directory
pio run -e main -t upload
```

Ensure `upload_port` in `platformio.ini` matches your device (default `/dev/ttyUSB0`).

### 2. Raspberry Pi

```bash
cd rpi
pip install -r requirements.txt
```

Download a compatible GGUF model (e.g., Qwen 2.5 1.5B Instruct Q4_K_M) and place it at:

```
rpi/models/qwen2.5-1.5b-instruct-q4_k_m.gguf
```

---

## Running the Demos

All demos are run from the `rpi/` directory.

```bash
cd rpi

# Deterministic tour (no LLM required)
python -m demos.tour_demo

# LLM-driven dialogue demo
python -m demos.llm_demo

# Live AprilTag localization visualiser
python -m demos.apriltag_demo

# Eye animation demo
python -m demos.screen_demo

# Audio round-trip (STT → TTS)
python -m demos.stt_to_tts_demo

# Serial command sender
python -m demos.serial_protocol_demo
```

### LLM Orchestrator (standalone)

```bash
python -m LLM.app.orchestrator \
    --model models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
    --exhibits tour/tour_content.json \
    --output-path output.json \
    --n-ctx 2048 \
    --max-tokens 300 \
    --temperature 0.35
```

---

## Configuration

### LLM Runtime (`LLM/config.py`)

| Argument | Default | Description |
|---|---|---|
| `--model` | `models/qwen2.5-1.5b-instruct-q4_k_m.gguf` | Path to GGUF model |
| `--exhibits` | `exhibits.json` | Path to exhibits JSON |
| `--output-path` | `output.json` | Destination for runtime `OutputPacket` |
| `--profile-path` | `profile_current.json` | Session visitor profile (overwritten each run) |
| `--silence-timeout` | `20` | Seconds before silence triggers disengagement |
| `--n-ctx` | `2048` | Model context length |
| `--n-threads` | `min(4, cpu_count)` | Inference threads |
| `--n-batch` | `128` | Batch size |
| `--max-tokens` | `300` | Max tokens per LLM response |
| `--temperature` | `0.35` | Sampling temperature |

### Tour Policy (`tour/tour_config.py`)

| Field | Default | Description |
|---|---|---|
| `max_clear_rejections` | 2 | Max "no" responses before ending tour |
| `max_unclear_retries` | 3 | Max retries on unclear visitor input |
| `short_tour_minutes_threshold` | 5 | Below this → short-tour mode |
| `short_tour_artwork_count` | 3 | Artworks shown in short-tour mode |
| `interrupt_listen_max_sec` | 1.8 | Max duration of interrupt listening window |
| `interrupt_silence_sec` | 0.6 | Silence duration to confirm end of utterance |

### Audio (`tour/tour_config.py → AudioConfig`)

| Field | Default | Description |
|---|---|---|
| `input_device` | 1 | sounddevice input device index |
| `output_device` | 1 | sounddevice output device index |
| `sample_rate` | 48000 | Sample rate in Hz |

### Arduino Hardware (`arduino/src/config.h`)

Edit `config.h` to match your wiring:
- Motor PWM/direction/encoder pins
- Servo pins (camera pan/tilt, laser pan/tilt)
- Laser pin
- Odometry constants (wheel radius, ticks per revolution, wheelbase)
- PID/motion tuning parameters

---

## Arduino Serial Command Reference

All commands are newline-terminated ASCII strings sent at **115200 baud**.

| Command | Arguments | Description |
|---|---|---|
| `vx vy wz` | `vx vy wz` (−255..255) | Direct velocity command (mecanum decomposition) |
| `goto` | `x*100 y*100 yaw*57.2958` | Move to pose; position in cm-int, yaw in decidegrees-int |
| `odom_reset` | — | Zero the odometry pose |
| `goto_cancel` | — | Cancel an active `moveTo` |
| `stop` | — | Hard stop all motors |
| `servo_cam` | `pan tilt` (0–180°) | Set camera servo angles |
| `servo_laser` | `pan tilt` (0–180°) | Set laser servo angles |
| `laser_dir` | `panOffset tiltOffset speed` | Smooth laser move to offset at deg/s |
| `laser_circle` | `pan tilt radius rotations` | Draw laser circle |
| `laser_on` | — | Turn laser on |
| `laser_off` | — | Turn laser off |
| `laser_cancel` | — | Cancel active laser motion |

**Arduino status replies** (emitted periodically):

```
POSE=x,y,yaw          # Odometry pose (scaled ×100 for position, ×57.2958 for yaw)
GOTO=MOVING           # moveTo in progress
GOTO=IDLE             # moveTo complete
ENC=fl,fr,bl,br       # Encoder tick counts
```

---

## Adding New Exhibits

### For the LLM engine

1. Add an entry to your `exhibits.json`:

```json
{
  "exhibits": [
    {
      "id": "unique-id",
      "title": "Exhibit Title",
      "artist": "Artist Name",
      "tags": ["impressionism", "landscape"],
      "features": [
        { "tag": "colour_palette", "annotation": "Uses short, thick brushstrokes of pure colour..." },
        { "tag": "composition",   "annotation": "The swirling sky dominates two-thirds of the canvas..." }
      ]
    }
  ]
}
```

2. Add a robot navigation pose to `tour/painting_positions.json`:

```json
{
  "id": "unique-id",
  "x": 1.20,
  "y": -0.50,
  "yaw": -1.57,
  "laser_circle": { "pan_deg": 90, "tilt_deg": 150, "radius_deg": 6.0 }
}
```

### For the deterministic FSM

Add a full artwork entry to the `artworks` array in `tour/tour_content.json` following the existing schema (id, title, artist, era, popularity, topic_tags, and `brief`/`detailed` script sections for year/technique/features/history/extra).
