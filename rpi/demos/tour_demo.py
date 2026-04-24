import threading

from screen.display import Screen
from screen.eye_movements import run_face_tracking
from tour.tour_fsm import DeterministicTourGuide


def run_tour_demo(
    voice_name: str,
    output_path: str | None,
    content_path: str | None,
    serial_port: str | None,
    serial_baud: int,
    painting_positions_path: str | None,
) -> None:
    guide = DeterministicTourGuide(
        voice_name=voice_name,
        output_path=output_path,
        content_path=content_path,
        serial_port=serial_port,
        serial_baud=serial_baud,
        painting_positions_path=painting_positions_path,
    )

    screen = Screen(width=1920, height=1080)
    run_face_tracking(screen, mode_provider=lambda: guide.state.name)

    tour_thread = threading.Thread(target=guide.run, daemon=True)
    tour_thread.start()

    # Keep the screen loop in the foreground; ESC closes the demo window.
    screen.run()
