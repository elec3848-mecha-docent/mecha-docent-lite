from tour.tour_fsm import run_tour_guide_demo


def run_tour_demo(
    voice_name: str,
    output_path: str | None,
    content_path: str | None,
) -> None:
    run_tour_guide_demo(
        voice_name=voice_name,
        output_path=output_path,
        content_path=content_path,
    )
