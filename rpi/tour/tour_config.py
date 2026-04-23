from dataclasses import dataclass


SCRIPT_CATEGORY_ORDER: tuple[str, ...] = ("year", "technique", "features", "history", "extra")

REQUIRED_PROMPT_KEYS: tuple[str, ...] = (
    "greeting",
    "greeting_silent",
    "greeting_retry",
    "greeting_default",
    "rebuttal",
    "route_short",
    "route_long",
    "ask_time",
    "ask_time_silent",
    "ask_time_retry",
    "ask_time_default",
    "ask_period",
    "ask_period_silent",
    "ask_period_retry",
    "period_response_newer",
    "period_response_older",
    "period_response_unclear",
    "ask_aspect",
    "ask_aspect_unclear",
    "queue_intro",
    "moving",
    "checkin_detailed",
    "checkin_brief",
    "checkin_silent",
    "mid_detailed_checkin",
    "mid_detailed_checkin_silent",
    "mid_detailed_checkin_unclear",
    "mid_detailed_continue",
    "mid_detailed_shorten",
    "fallback",
    "unclear_continue",
    "tour_complete",
)

# Approximate starting year for each era, used for sorting artworks newest-first.
ERA_APPROXIMATE_YEAR: dict[str, int] = {
    "High Renaissance": 1490,
    "Dutch Golden Age": 1600,
    "Post-Impressionism": 1886,
    "Surrealism": 1920,
}

# Average words-per-response threshold above which Medo uses detailed explanations.
VERBOSITY_INFER_WORD_THRESHOLD: int = 5


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
