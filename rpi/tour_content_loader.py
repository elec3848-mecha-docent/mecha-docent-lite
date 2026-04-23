import json
from dataclasses import dataclass
from pathlib import Path

from tour_config import REQUIRED_PROMPT_KEYS, SCRIPT_CATEGORY_ORDER, TourPolicy


@dataclass(frozen=True)
class ScriptSections:
    year: list[str]
    technique: list[str]
    features: list[str]
    history: list[str]
    extra: list[str]


@dataclass(frozen=True)
class ArtworkContent:
    id: str
    title: str
    artist: str
    era: str
    popularity: int
    topic_tags: tuple[str, ...]
    intro: list[str]
    brief: ScriptSections
    detailed: ScriptSections


@dataclass(frozen=True)
class TourContent:
    policy: TourPolicy
    keyword_buckets: dict[str, set[str]]
    interest_topics: dict[str, set[str]]
    prompt_variants: dict[str, list[str]]
    artworks: list[ArtworkContent]


def load_tour_content(content_path: str | None = None) -> TourContent:
    path = Path(content_path) if content_path else Path(__file__).with_name("tour_content.json")
    if not path.exists():
        raise FileNotFoundError(f"Tour content JSON not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        raw = json.load(file)

    _validate_top_level(raw, str(path))

    policy_raw = raw["policy"]
    policy = TourPolicy(
        max_clear_rejections=int(policy_raw["max_clear_rejections"]),
        max_unclear_retries=int(policy_raw["max_unclear_retries"]),
        short_tour_minutes_threshold=int(policy_raw["short_tour_minutes_threshold"]),
        short_tour_artwork_count=int(policy_raw["short_tour_artwork_count"]),
        interrupt_listen_max_sec=float(policy_raw["interrupt_listen_max_sec"]),
        interrupt_silence_sec=float(policy_raw["interrupt_silence_sec"]),
    )

    keyword_buckets = {
        name: {item.strip().lower() for item in values if item.strip()}
        for name, values in raw["keyword_buckets"].items()
    }
    interest_topics = {
        name: {item.strip().lower() for item in values if item.strip()}
        for name, values in raw["interest_topics"].items()
    }
    prompt_variants = {
        name: [item.strip() for item in values if item.strip()]
        for name, values in raw["prompt_variants"].items()
    }

    artworks: list[ArtworkContent] = []
    for artwork_raw in raw["artworks"]:
        scripts = artwork_raw.get("scripts", {})
        intro = _to_sentence_list(scripts.get("intro", []), "scripts.intro")
        brief = _parse_sections(scripts.get("brief", {}), "scripts.brief")
        detailed = _parse_sections(scripts.get("detailed", {}), "scripts.detailed")

        artworks.append(
            ArtworkContent(
                id=str(artwork_raw["id"]),
                title=str(artwork_raw["title"]),
                artist=str(artwork_raw["artist"]),
                era=str(artwork_raw["era"]),
                popularity=int(artwork_raw["popularity"]),
                topic_tags=tuple(str(tag).strip().lower() for tag in artwork_raw.get("topic_tags", [])),
                intro=intro,
                brief=brief,
                detailed=detailed,
            )
        )

    return TourContent(
        policy=policy,
        keyword_buckets=keyword_buckets,
        interest_topics=interest_topics,
        prompt_variants=prompt_variants,
        artworks=artworks,
    )


def _validate_top_level(raw: dict, source: str) -> None:
    required_keys = {"policy", "keyword_buckets", "interest_topics", "prompt_variants", "artworks"}
    missing = required_keys - set(raw.keys())
    if missing:
        raise ValueError(f"Missing top-level keys in {source}: {sorted(missing)}")

    for key in REQUIRED_PROMPT_KEYS:
        variants = raw["prompt_variants"].get(key)
        if not isinstance(variants, list) or not any(str(item).strip() for item in variants):
            raise ValueError(f"prompt_variants.{key} must be a non-empty list")

    if not isinstance(raw["artworks"], list) or not raw["artworks"]:
        raise ValueError("artworks must be a non-empty list")


def _parse_sections(raw_sections: dict, path: str) -> ScriptSections:
    values: dict[str, list[str]] = {}
    for category in SCRIPT_CATEGORY_ORDER:
        values[category] = _to_sentence_list(raw_sections.get(category, []), f"{path}.{category}")

    return ScriptSections(
        year=values["year"],
        technique=values["technique"],
        features=values["features"],
        history=values["history"],
        extra=values["extra"],
    )


def _to_sentence_list(raw_value: object, path: str) -> list[str]:
    if not isinstance(raw_value, list):
        raise ValueError(f"{path} must be a list of strings")

    cleaned = [str(item).strip() for item in raw_value if str(item).strip()]
    if not cleaned:
        raise ValueError(f"{path} must contain at least one sentence")
    return cleaned
