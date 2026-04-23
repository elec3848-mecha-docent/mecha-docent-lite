from dataclasses import dataclass


SCRIPT_CATEGORY_ORDER: tuple[str, ...] = ("year", "technique", "features", "history", "extra")

REQUIRED_PROMPT_KEYS: tuple[str, ...] = (
    "greeting",
    "rebuttal",
    "route_short",
    "route_long",
    "ask_time",
    "ask_verbosity",
    "ask_interest",
    "queue_intro",
    "moving",
    "checkin_detailed",
    "checkin_brief",
    "mid_detailed_checkin",
    "mid_detailed_continue",
    "mid_detailed_shorten",
    "fallback",
    "unclear_continue",
    "tour_complete",
)


@dataclass(frozen=True)
class AudioConfig:
    input_device: int | None = 1
    output_device: int | None = 1
    sample_rate: int = 48000


@dataclass(frozen=True)
class TourPolicy:
    max_clear_rejections: int = 2
    max_unclear_retries: int = 3
    short_tour_minutes_threshold: int = 5
    short_tour_artwork_count: int = 3
    interrupt_listen_max_sec: float = 1.8
    interrupt_silence_sec: float = 0.6
