"""Tour route planner for the Medo dialogue engine.

Builds and adjusts the ordered list of exhibit IDs that the robot will visit
during a session.

Functions
---------
:func:`build_initial_tour_plan`
    Calls the LLM with a planning prompt to produce an interest-ordered list
    of exhibit IDs and an introductory speech.  Falls back to
    :func:`_fallback_sort` (tag-overlap scoring) if the LLM returns an invalid
    or unparseable result.

:func:`reroute_remaining`
    Re-prioritises the exhibits not yet visited based on the current visitor
    profile.  Called when the visitor signals boredom or requests a switch.

:func:`_fallback_sort`
    Deterministic fallback: ranks exhibits by the number of interest-tag
    matches minus dislike-tag matches.
"""
from __future__ import annotations

from LLM.domain.models import Exhibit, VisitorProfile
from LLM.generation.llm_client import call_json
from LLM.generation.prompts import planning_prompt


def _fallback_sort(profile: VisitorProfile, exhibits: list[Exhibit]) -> list[str]:
    interests = {x.lower() for x in profile.interests}
    dislikes = {x.lower() for x in profile.dislikes}

    def score(exhibit: Exhibit) -> int:
        tags = {tag.lower() for tag in exhibit.tags}
        positive = len(interests.intersection(tags))
        negative = len(dislikes.intersection(tags))
        return positive - negative

    ranked = sorted(exhibits, key=score, reverse=True)
    return [x.id for x in ranked]


def build_initial_tour_plan(llm, profile: VisitorProfile, exhibits: list[Exhibit], max_tokens: int, temperature: float) -> tuple[list[str], str]:
    fallback = _fallback_sort(profile, exhibits)
    messages = [
        {"role": "system", "content": planning_prompt(profile, exhibits)},
        {"role": "user", "content": "Plan the tour."},
    ]

    try:
        data = call_json(llm, messages, max_tokens=max_tokens, temperature=temperature)
    except ValueError:
        return fallback, "I planned a route that should fit your interests."

    proposed = data.get("tour_plan", [])
    valid_ids = {item.id for item in exhibits}
    clean = [x for x in proposed if isinstance(x, str) and x in valid_ids]
    for eid in fallback:
        if eid not in clean:
            clean.append(eid)
    if not clean:
        clean = fallback

    speech = data.get("speech", "I have a route ready for you.")
    return clean, str(speech)


def reroute_remaining(profile: VisitorProfile, remaining: list[str], exhibit_map: dict[str, Exhibit]) -> list[str]:
    if not remaining:
        return []

    interests = {x.lower() for x in profile.interests}
    dislikes = {x.lower() for x in profile.dislikes}

    def score(exhibit_id: str) -> int:
        exhibit = exhibit_map[exhibit_id]
        tags = {tag.lower() for tag in exhibit.tags}
        return len(tags.intersection(interests)) - len(tags.intersection(dislikes))

    best = sorted(remaining, key=score, reverse=True)
    return best
