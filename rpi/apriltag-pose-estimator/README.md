# AprilTag 2D Pose Estimation

Estimate a robot's 2D global pose (X, Y, Yaw) using AprilTags with known positions.

<img width="1743" height="831" alt="image" src="https://github.com/user-attachments/assets/1f60da5f-e0f8-4e62-8225-0f46cc36436f" />

## Installation

```bash
# Clone the repository
git clone https://github.com/iloevera/apriltag-pose-estimator.git
cd apriltag-pose-estimator

# Install in editable mode with dependencies
pip install -e .
```

## Quick Start (Demo)

1. **Calibrate your camera**:
   ```bash
   apriltag-calibrate --camera-index 0 --output config/my_camera.yaml
   ```
   *   Hold a 9x6 chessboard (24mm squares) in front of the camera.
   *   Press **SPACE** to capture frames (need ~20).
   *   Press **Q** to finish and save.

2. **Run the demo**:
   ```bash
   python examples/live_localization_demo.py --calibration config/my_camera.yaml
   ```

## Development Setup

### 1. Print the AprilTags

Print [apriltags_a4.pdf](apriltags_a4.pdf) on A4 paper **with no margins**. You'll need:
- Page 1: For camera calibration (contains a checkerboard with squares of side length 2.5 cm)
- Pages 2+: For the localization system (10 cm AprilTags with known positions)

### 2. Set Up Python Environment

```bash
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Calibrate Your Camera

```bash
apriltag-calibrate
```

1. Place the **checkerboard (page 1)** on a flat surface
2. Move the camera around the checkerboard, closer is better
3. Press **Space** to capture each photo (20 total)
4. Check the final RMS reprojection error:
   - **✅ Below 0.5**: Good to go!
   - **❌ Above 0.5**: Try again with better lighting and closer captures

This generates `config/camera_calibration_rpi.yaml` (default).

### 4. Run the Live Localization Demo

```bash
python examples/live_localization_demo.py
```

1. Set up pages 2+ of the printed AprilTags as shown in the top-down preview (place flat on walls)
2. Move your camera and tags around to explore localization
3. Exit with **Q**


## Configuration

Your camera calibration is saved to `config/camera_calibration.yaml` after calibration.

Tag positions are defined in `config/tag_map.json` with the format:
```json
{
  "tags": [
    {"tag_id": 0, "x": 0.0, "y": 0.0, "yaw": 0.0, "size": 0.1},
    {"tag_id": 1, "x": 1.0, "y": 0.0, "yaw": 0.0, "size": 0.1}
  ]
}
```

- `x`, `y`: Global position (meters)
- `yaw`: Orientation in radians ([-π, π])
- `size`: Tag side length (meters)

## Usage in Code

```python
from apriltag_pose_estimator import PoseEstimator, CameraCalibration, AprilTagMap
import cv2

# Load calibration and tag map
calibration = CameraCalibration.from_yaml("config/camera_calibration.yaml")
tag_map = AprilTagMap.from_json("config/tag_map.json")

# Initialize estimator
estimator = PoseEstimator(calibration, tag_map)

# Process frames
cap = cv2.VideoCapture(0)
while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    pose = estimator.estimate_pose(frame)
    print(f"Pose: x={pose.x:.2f}m, y={pose.y:.2f}m, yaw={pose.yaw:.2f}rad")

cap.release()
```

## Testing

```bash
pytest tests/                                      # Run all tests
pytest tests/ --cov=apriltag_pose_estimator      # With coverage
```

Expected: 60+ tests with ≥95% core module coverage

## Troubleshooting

**No tags detected?**
- Check lighting: AprilTags need good visibility
- Verify tag distance: Tags may be too small or far away
- Check camera focus

**Jittery pose estimates?**
- Add more tags to your tag map
- Re-run camera calibration (RMS error should be < 0.5)
- Consider using the example's median fusion strategy

**Large pose jumps?**
- Verify tag positions in `tag_map.json` are accurate
- Check camera calibration
- Ensure tag orientations (yaw) are correct

## Features

✅ Fast AprilTag detection via `pupil-apriltags`  
✅ Multi-tag fusion with confidence weighting  
✅ Perspective-N-Point (PnP) solving via `cv2.solvePnP()`  
✅ Robust fallback to last known pose  
✅ Modular, well-tested codebase  

## License

Designed for tour guide robots. See dependencies below.

**Dependencies:**
- [pupil-apriltags](https://github.com/pupil-labs/pupilpose) — Detection
- [OpenCV](https://opencv.org/) — Vision & pose solving
- [NumPy](https://numpy.org/) — Linear algebra
- [PyYAML](https://pyyaml.org/) — Config file parsing

## Contact & Support

For questions or issues, refer to the test files for usage examples and expected behavior.

---

**Last Updated:** April 2026  
**Version:** 0.1
