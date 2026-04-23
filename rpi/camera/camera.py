"""
camera/camera.py — Raspberry Pi camera wrapper using picamera2.

Usage
-----
    from camera import Camera

    cam = Camera()
    cam.start()

    frame = cam.capture_array()   # numpy array (RGB)
    cam.capture_file("photo.jpg") # save directly to disk

    cam.stop()

Or use as a context manager:

    with Camera() as cam:
        frame = cam.capture_array()
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import FileOutput


class Camera:
    """Thin wrapper around :class:`picamera2.Picamera2`.

    Parameters
    ----------
    width, height:
        Resolution of the main capture stream.
    framerate:
        Target frame rate (used when recording video).
    camera_index:
        Index of the camera to open (default 0).
    """

    def __init__(
        self,
        width: int = 1280,
        height: int = 720,
        framerate: int = 30,
        camera_index: int = 0,
    ) -> None:
        self._width = width
        self._height = height
        self._framerate = framerate
        self._camera_index = camera_index

        self._picam2: Optional[Picamera2] = None
        self._recording = False
        self._hw_rotation = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Initialise and start the camera."""
        if self._picam2 is not None:
            return

        self._picam2 = Picamera2(self._camera_index)
        config = self._picam2.create_still_configuration(
            main={"size": (self._width, self._height), "format": "RGB888"},
            buffer_count=2,
        )
        self._picam2.configure(config)

        # Account for upside-down installation (180deg rotation)
        # Note: If 'Transform' is not supported by the hardware/driver, we'll
        # fall back to software rotation in capture_array.
        try:
            self._picam2.set_controls({"Transform": "rotate180"})
            self._hw_rotation = True
        except Exception:
            self._hw_rotation = False

        self._picam2.start()

    def stop(self) -> None:
        """Stop and release the camera."""
        if self._picam2 is None:
            return
        if self._recording:
            self.stop_recording()
        self._picam2.stop()
        self._picam2.close()
        self._picam2 = None

    def __enter__(self) -> "Camera":
        self.start()
        return self

    def __exit__(self, *_) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------

    def capture_array(self) -> np.ndarray:
        """Return the latest frame as an (H, W, 3) uint8 RGB numpy array."""
        frame = self._picam2.capture_array("main")  # type: ignore[union-attr]
        
        if not self._hw_rotation:
            # Software fallback: Rotate 180 degrees (flip both axes)
            return np.flip(frame, axis=(0, 1))
        return frame

    def capture_file(self, path: str | Path) -> None:
        """Capture a still image and save it to *path*.

        The format is inferred from the file extension (jpg, png, …).
        """
        self._require_started()
        self._picam2.capture_file(str(path))  # type: ignore[union-attr]

    # ------------------------------------------------------------------
    # Video recording
    # ------------------------------------------------------------------

    def start_recording(self, path: str | Path, quality: int = 23) -> None:
        """Start H.264 video recording to *path* (.h264 or .mp4).

        Parameters
        ----------
        path:
            Output file path.
        quality:
            H.264 quantisation parameter (lower = higher quality, larger file).
        """
        self._require_started()
        if self._recording:
            raise RuntimeError("Already recording.")

        encoder = H264Encoder(qp=quality)
        self._picam2.start_recording(encoder, FileOutput(str(path)))  # type: ignore[union-attr]
        self._recording = True

    def stop_recording(self) -> None:
        """Stop an in-progress video recording."""
        if not self._recording:
            return
        self._picam2.stop_recording()  # type: ignore[union-attr]
        self._recording = False

    @property
    def is_recording(self) -> bool:
        return self._recording

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def resolution(self) -> tuple[int, int]:
        return (self._width, self._height)

    @property
    def started(self) -> bool:
        return self._picam2 is not None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_started(self) -> None:
        if self._picam2 is None:
            raise RuntimeError("Camera is not started. Call Camera.start() first.")
