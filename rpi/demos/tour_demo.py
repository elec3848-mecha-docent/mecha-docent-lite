from tour.tour_fsm import run_tour_guide_demo


def run_tour_demo(
    voice_name: str,
    output_path: str | None,
    content_path: str | None,
    serial_port: str | None,
    serial_baud: int,
    painting_positions_path: str | None,
) -> None:
    run_tour_guide_demo(
        voice_name=voice_name,
        output_path=output_path,
        content_path=content_path,
        serial_port=serial_port,
        serial_baud=serial_baud,
        painting_positions_path=painting_positions_path,
    )
