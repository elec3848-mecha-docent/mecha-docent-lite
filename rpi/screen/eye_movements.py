"""Default eye movement animation routines for the screen module."""

import os
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from .display import EYE_HEIGHT, LID_HEIGHT, Screen
from camera import Camera


# Layout constants (pixels, 1080p baseline — scale if needed)
W, H = 1920, 1080

EYE_Y = H // 2

EYE_L_X = W // 2 - 220
EYE_R_X = W // 2 + 220

# Lids sit above the eyes by default (invisible/off-screen upward)
LID_TOP_OPEN_Y = EYE_Y - EYE_HEIGHT - LID_HEIGHT // 2 - 10
LID_BOTTOM_OPEN_Y = EYE_Y + EYE_HEIGHT + LID_HEIGHT // 2 + 10
LID_TOP_SHUT_Y = EYE_Y
LID_BOTTOM_SHUT_Y = EYE_Y

# Happy expression: bottom lids rise to cover the lower half of the eyes.
LID_BOTTOM_HAPPY_Y = EYE_Y + LID_HEIGHT // 2

# Squint leaves about 20% of eye height visible at centre.
_VISIBLE_SLIT_FRAC = 0.20
_TOP_COVER_FRAC = (1.0 - _VISIBLE_SLIT_FRAC) / 2.0
LID_TOP_SQUINT_Y = int(EYE_Y - EYE_HEIGHT / 2 + EYE_HEIGHT * _TOP_COVER_FRAC - LID_HEIGHT / 2)
LID_BOTTOM_SQUINT_Y = int(EYE_Y + EYE_HEIGHT / 2 - EYE_HEIGHT * _TOP_COVER_FRAC + LID_HEIGHT / 2)

LOOK_OFFSET = 160


def _run_animations(screen: Screen) -> None:
    """Background thread that drives the default eye animation loop."""

    def open_eyes(duration: float = 0.0) -> None:
        screen.move_all(
            eye_l_pos=(EYE_L_X, EYE_Y),
            eye_r_pos=(EYE_R_X, EYE_Y),
            lid_tl_pos=(EYE_L_X, LID_TOP_OPEN_Y),
            lid_tr_pos=(EYE_R_X, LID_TOP_OPEN_Y),
            lid_bl_pos=(EYE_L_X, LID_BOTTOM_OPEN_Y),
            lid_br_pos=(EYE_R_X, LID_BOTTOM_OPEN_Y),
            duration=duration,
        )

    def blink(duration: float = 0.20) -> None:
        screen.move_all(
            lid_tl_pos=(EYE_L_X, LID_TOP_SHUT_Y),
            lid_tr_pos=(EYE_R_X, LID_TOP_SHUT_Y),
            lid_bl_pos=(EYE_L_X, LID_BOTTOM_SHUT_Y),
            lid_br_pos=(EYE_R_X, LID_BOTTOM_SHUT_Y),
            duration=duration,
        )
        time.sleep(duration + 0.10)
        screen.move_all(
            lid_tl_pos=(EYE_L_X, LID_TOP_OPEN_Y),
            lid_tr_pos=(EYE_R_X, LID_TOP_OPEN_Y),
            lid_bl_pos=(EYE_L_X, LID_BOTTOM_OPEN_Y),
            lid_br_pos=(EYE_R_X, LID_BOTTOM_OPEN_Y),
            duration=duration,
        )

    def happy(duration: float = 0.2) -> None:
        screen.move_all(
            lid_bl_pos=(EYE_L_X, LID_BOTTOM_HAPPY_Y),
            lid_br_pos=(EYE_R_X, LID_BOTTOM_HAPPY_Y),
            duration=duration,
        )

    def look(direction: str, duration: float = 0.2) -> None:
        target_offset = {"left": -LOOK_OFFSET, "right": LOOK_OFFSET, "centre": 0}[direction]
        current_offset_x, _ = screen.get_group_offset()
        dx = target_offset - current_offset_x
        screen.move_group(dx=dx, dy=0.0, duration=duration)

    def squint(duration: float = 0.15) -> None:
        screen.move_all(
            lid_tl_pos=(EYE_L_X, LID_TOP_SQUINT_Y),
            lid_tr_pos=(EYE_R_X, LID_TOP_SQUINT_Y),
            lid_bl_pos=(EYE_L_X, LID_BOTTOM_SQUINT_Y),
            lid_br_pos=(EYE_R_X, LID_BOTTOM_SQUINT_Y),
            duration=duration,
        )

    screen.eye_left.snap_to(EYE_L_X, EYE_Y)
    screen.eye_right.snap_to(EYE_R_X, EYE_Y)
    screen.lid_top_left.snap_to(EYE_L_X, LID_TOP_OPEN_Y)
    screen.lid_top_right.snap_to(EYE_R_X, LID_TOP_OPEN_Y)
    screen.lid_bottom_left.snap_to(EYE_L_X, LID_BOTTOM_OPEN_Y)
    screen.lid_bottom_right.snap_to(EYE_R_X, LID_BOTTOM_OPEN_Y)

    time.sleep(1.0)

    while True:
        time.sleep(2.5)
        blink()
        time.sleep(0.15)

        look("left", duration=0.25)
        time.sleep(0.8)

        look("right", duration=0.3)
        time.sleep(0.8)

        look("centre", duration=0.2)
        time.sleep(0.5)

        blink(0.07)
        time.sleep(0.12)
        blink(0.07)
        time.sleep(0.5)

        happy(0.2)
        time.sleep(0.8)

        squint(0.2)
        time.sleep(1.0)

        open_eyes(0.2)
        time.sleep(1.5)


def run_eye_animation_demo(width: int = W, height: int = H) -> None:
    """Run the default animated eyes fullscreen demo."""
    screen = Screen(width=width, height=height)
    anim_thread = threading.Thread(target=_run_animations, args=(screen,), daemon=True)
    anim_thread.start()
    screen.run()


# ---------------------------------------------------------------------------
# Face-tracking
# ---------------------------------------------------------------------------

_MODEL_DIR = Path(__file__).parent.parent / "models"
_PROTOTXT_PATH = str(_MODEL_DIR / "opencv_face_detector.prototxt")
_CAFFEMODEL_PATH = str(_MODEL_DIR / "res10_300x300_ssd_iter_140000.caffemodel")


def _load_dnn_model() -> cv2.dnn.Net:
    """Load the OpenCV DNN face detector model.
    
    Falls back to Haar Cascade if DNN files are missing.
    """
    if os.path.exists(_PROTOTXT_PATH) and os.path.exists(_CAFFEMODEL_PATH):
        try:
            net = cv2.dnn.readNetFromCaffe(_PROTOTXT_PATH, _CAFFEMODEL_PATH)
            print(f"[FaceTracker] Loaded DNN model from {_CAFFEMODEL_PATH}")
            return net
        except Exception as e:
            print(f"[FaceTracker] Failed to load DNN model: {e}. Using Haar Cascade fallback.")
    else:
        print(f"[FaceTracker] Model files not found. Using Haar Cascade fallback.")
    return None


def _detect_faces_dnn(net: cv2.dnn.Net, frame: np.ndarray, conf_threshold: float = 0.5) -> list:
    """Detect faces using OpenCV DNN SSD model.
    
    Returns list of (x, y, w, h) rectangles.
    """
    h, w = frame.shape[:2]
    
    # Prepare blob: resize to 300x300 and normalize
    blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300), [104, 177, 123], False, False)
    net.setInput(blob)
    detections = net.forward()
    
    faces = []
    # detections shape: (1, 1, N, 7) where each detection is [img_id, class_id, confidence, x1, y1, x2, y2]
    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence > conf_threshold:
            # Get bounding box coordinates (normalized to [0, 1])
            x1 = int(detections[0, 0, i, 3] * w)
            y1 = int(detections[0, 0, i, 4] * h)
            x2 = int(detections[0, 0, i, 5] * w)
            y2 = int(detections[0, 0, i, 6] * h)
            
            # Convert to (x, y, w, h) format
            faces.append((x1, y1, x2 - x1, y2 - y1))
    
    return faces


def _detect_faces_cascade(frame: np.ndarray) -> list:
    """Detect faces using Haar Cascade (fallback).
    
    Returns list of (x, y, w, h) rectangles.
    """
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    cascade = cv2.CascadeClassifier(cascade_path)
    return cascade.detectMultiScale(frame, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))


def _face_tracking_thread(
    screen: Screen,
    cam_width: int,
    cam_height: int,
    max_offset_x: float,
    max_offset_y: float,
    poll_interval: float,
) -> None:
    """Background thread: capture frames, detect faces, move eye group."""
    # Try to load DNN model; fall back to Haar Cascade if unavailable
    dnn_net = _load_dnn_model()
    use_dnn = dnn_net is not None
    method = "DNN" if use_dnn else "Haar Cascade"
    print(f"[FaceTracker] Using {method} for face detection")

    print(f"[FaceTracker] Starting camera ({cam_width}x{cam_height})...")
    with Camera(width=cam_width, height=cam_height) as cam:
        print("[FaceTracker] Camera started. Entering detection loop.")
        frame_count = 0
        while True:
            start_time = time.time()
            frame = cam.capture_array()  # RGB uint8

            # Quick check if frame is empty
            if frame is None or frame.size == 0:
                print("[FaceTracker] ERROR: Captured empty frame!")
                time.sleep(poll_interval)
                continue

            # Detect faces using the selected method
            if use_dnn:
                faces = _detect_faces_dnn(dnn_net, frame, conf_threshold=0.5)
            else:
                gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
                faces = _detect_faces_cascade(gray)

            processing_time = (time.time() - start_time) * 1000
            frame_count += 1

            if len(faces) > 0:
                # Choose the largest face as the nearest person
                areas = [w * h for (x, y, w, h) in faces]
                idx = int(np.argmax(areas))
                x, y, w, h = faces[idx]

                # Log every 10 frames to reduce spam
                if frame_count % 10 == 0:
                    print(f"[FaceTracker] Found {len(faces)} face(s). Largest: {w}x{h} at ({x}, {y}). Proc: {processing_time:.1f}ms")

                # Normalised offset of face centre relative to frame centre ([-1, 1])
                norm_x = -(x + w / 2 - cam_width / 2) / (cam_width / 2)
                norm_y = (y + h / 2 - cam_height / 2) / (cam_height / 2)

                target_x = norm_x * max_offset_x
                target_y = norm_y * max_offset_y

                current_x, current_y = screen.get_group_offset()
                dx = target_x - current_x
                dy = target_y - current_y

                # Only issue a move when the delta is noticeable
                if abs(dx) > 2 or abs(dy) > 2:
                    screen.move_group(dx=dx, dy=dy, duration=poll_interval * 3)
            else:
                # Optional: print every ~2 seconds if no faces found to avoid spam
                if int(time.time()) % 2 == 0:
                    print(f"[FaceTracker] No faces detected. Proc: {processing_time:.1f}ms")

            time.sleep(poll_interval)


def run_face_tracking(
    screen: Screen,
    *,
    cam_width: int = 640,
    cam_height: int = 480,
    max_offset_x: float = 400,
    max_offset_y: float = 80,
    poll_interval: float = 0.1,
) -> threading.Thread:
    """Start face-tracking eye movement in a daemon background thread.

    The eyes follow the largest detected face in the camera frame. When no
    face is visible the eyes remain at their last position.

    Parameters
    ----------
    screen:
        The :class:`~screen.display.Screen` instance to control.
    cam_width, cam_height:
        Camera capture resolution (lower = faster detection).
    max_offset_x:
        Maximum horizontal eye displacement in pixels (maps to frame edge).
    max_offset_y:
        Maximum vertical eye displacement in pixels (maps to frame edge).
    poll_interval:
        Seconds between camera captures / position updates.

    Returns
    -------
    threading.Thread
        The daemon thread driving tracking (already started).
    """
    # Snap to default open-eye positions before starting
    screen.eye_left.snap_to(EYE_L_X, EYE_Y)
    screen.eye_right.snap_to(EYE_R_X, EYE_Y)
    screen.lid_top_left.snap_to(EYE_L_X, LID_TOP_OPEN_Y)
    screen.lid_top_right.snap_to(EYE_R_X, LID_TOP_OPEN_Y)
    screen.lid_bottom_left.snap_to(EYE_L_X, LID_BOTTOM_OPEN_Y)
    screen.lid_bottom_right.snap_to(EYE_R_X, LID_BOTTOM_OPEN_Y)

    thread = threading.Thread(
        target=_face_tracking_thread,
        args=(screen, cam_width, cam_height, max_offset_x, max_offset_y, poll_interval),
        daemon=True,
    )
    thread.start()
    return thread


def run_face_tracking_demo(width: int = W, height: int = H) -> None:
    """Fullscreen demo: eyes follow the nearest detected face."""
    screen = Screen(width=width, height=height)
    run_face_tracking(screen)
    screen.run()
