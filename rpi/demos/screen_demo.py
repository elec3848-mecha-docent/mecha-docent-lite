"""Screen demo: animated eyes with optional face-tracking."""

from screen.eye_movements import run_eye_animation_demo, run_face_tracking_demo


def run_screen_demo(width: int = 1920, height: int = 1080, face_tracking: bool = False) -> None:
    """Run the fullscreen eye demo.

    Parameters
    ----------
    face_tracking:
        When True, eyes follow the nearest detected face via the camera.
        When False (default), the pre-scripted animation loop runs instead.
    """
    if face_tracking:
        run_face_tracking_demo(width=width, height=height)
    else:
        run_eye_animation_demo(width=width, height=height)
