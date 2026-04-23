# Mecha Docent Lite

This repository now contains an end-to-end Raspberry Pi to Arduino navigation bridge:

- Raspberry Pi estimates global pose from AprilTags.
- Raspberry Pi sends target coordinates to Arduino.
- Arduino drives a mecanum base toward the active target.
- Raspberry Pi streams periodic pose corrections to keep the Arduino estimator aligned.

## Serial Protocol

Transport: newline-delimited JSON at 115200 baud.

### RPi to Arduino

Target command (expects ACK or NACK):

~~~json
{"type":"target","id":1,"x":1.2,"y":-0.4,"yaw":1.57}
~~~

Pose correction (fire-and-forget):

~~~json
{"type":"pose_correction","x":1.19,"y":-0.41,"yaw":1.55,"confidence":0.82}
~~~

Cancel target:

~~~json
{"type":"cancel_target"}
~~~

Ping:

~~~json
{"type":"ping"}
~~~

### Arduino to RPi

ACK/NACK for target command IDs:

~~~json
{"type":"ack","id":1}
{"type":"nack","id":1,"reason":"missing_target_fields"}
~~~

Periodic status:

~~~json
{"type":"status","x":0.31,"y":0.14,"yaw":0.09,"vx_cmd":0.18,"vy_cmd":-0.03,"wz_cmd":0.10,"target_active":1,"target_id":1,"target_reached":0,"err_xy":0.22,"err_yaw":0.15,"stale_ms":120,"pose_stale":0}
~~~

## Arduino Firmware

Firmware entrypoint: arduino/src/main.cpp

Implemented behavior:

- Non-blocking serial JSON line parser.
- Target command preemption (latest target immediately becomes active).
- Proportional navigation controller in robot body frame.
- Pose correction integration through StateEstimator::correct().
- Dead-reckoning prediction using commanded velocities.
- Safety timeout for stale target commands.
- Periodic status publish.

Navigation tuning constants are in arduino/src/config.h.

## Raspberry Pi Demo

Navigation demo script: rpi/live_navigation_demo.py

Features:

- OpenCV preview with detections and top-view map.
- Overlay with navigation info: active target, latest ACK/NACK, Arduino errors, correction age.
- Runtime CLI target input while video loop runs.
- Periodic pose correction streaming to Arduino.

Install dependencies:

~~~bash
cd rpi
pip install -r requirements.txt
~~~

Run:

~~~bash
python live_navigation_demo.py --port /dev/ttyUSB0 --calibration apriltag-pose-estimator/config/camera_calibration_rpi.yaml --tag-map apriltag-pose-estimator/config/tag_map_example.json --picamera2
~~~

CLI commands while running:

- target 1.0 0.5 0.0
- 1.0 0.5 0.0
- cancel
- help

## Notes

- Serial ACK/NACK is intentionally limited to target commands.
- Pose corrections are high-rate and unacknowledged by design.
- Use the same coordinate frame convention between tag map and navigation targets.
