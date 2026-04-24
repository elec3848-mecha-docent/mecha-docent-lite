"""Domain model dataclasses for the Medo dialogue engine.

Classes
-------
:class:`VisitorProfile`
    Accumulates visitor interests, dislikes, age group, background,
    verbosity preference, time budget, and per-turn sentiment history.
    Use :meth:`~VisitorProfile.merge` to apply partial updates from LLM
    inference results without overwriting existing data.

:class:`Exhibit` / :class:`ExhibitFeature`
    Lightweight representations of a museum exhibit loaded from
    ``exhibits.json``.  Each exhibit has a list of named features
    (e.g., ``colour_palette``, ``composition``) with free-text annotations
    that the LLM uses to generate chunked explanations.

:class:`OutputPacket`
    The structured output produced each turn.  Written atomically to
    ``output.json`` so that TTS, robot control, and the screen renderer can
    consume it asynchronously.  Contains speech text, head-movement hint,
    FSM state, visitor sentiment, optional laser target, and timing fields.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


HEAD_MOVEMENTS = {
    "eye_contact",
    "nod-yes",
    "nod-no",
    "painting",
    "direction",
    "thinking",
    "searching",
}


@dataclass
class ExhibitFeature:
    tag: str
    annotation: str


@dataclass
class Exhibit:
    id: str
    title: str
    artist: str
    tags: list[str]
    features: list[ExhibitFeature]


@dataclass
class VisitorProfile:
    interests: list[str] = field(default_factory=list)
    dislikes: list[str] = field(default_factory=list)
    age_group: str = "unknown"
    background: str = "unknown"
    detail_preference: str = "balanced"
    time_budget_minutes: int | None = None
    sentiment_history: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    facts: dict[str, str] = field(default_factory=dict)
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def merge(self, payload: dict) -> None:
        interests = payload.get("interests", [])
        dislikes = payload.get("dislikes", [])
        for item in interests:
            if isinstance(item, str) and item and item not in self.interests:
                self.interests.append(item)
        for item in dislikes:
            if isinstance(item, str) and item and item not in self.dislikes:
                self.dislikes.append(item)

        if isinstance(payload.get("age_group"), str) and payload["age_group"].strip():
            self.age_group = payload["age_group"].strip()
        if isinstance(payload.get("background"), str) and payload["background"].strip():
            self.background = payload["background"].strip()
        if isinstance(payload.get("detail_preference"), str) and payload["detail_preference"].strip():
            self.detail_preference = payload["detail_preference"].strip().lower()

        budget = payload.get("time_budget_minutes")
        if isinstance(budget, int) and budget > 0:
            self.time_budget_minutes = budget

        note = payload.get("note")
        if isinstance(note, str) and note.strip():
            self.notes.append(note.strip())

        facts = payload.get("facts", {})
        if isinstance(facts, dict):
            for key, value in facts.items():
                if isinstance(key, str) and isinstance(value, str) and key.strip() and value.strip():
                    self.facts[key.strip()] = value.strip()

        self.updated_at = datetime.now(timezone.utc).isoformat()

    def add_sentiment(self, sentiment: str) -> None:
        self.sentiment_history.append(sentiment)
        if len(self.sentiment_history) > 50:
            self.sentiment_history = self.sentiment_history[-50:]
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "interests": self.interests,
            "dislikes": self.dislikes,
            "age_group": self.age_group,
            "background": self.background,
            "detail_preference": self.detail_preference,
            "time_budget_minutes": self.time_budget_minutes,
            "sentiment_history": self.sentiment_history,
            "notes": self.notes,
            "facts": self.facts,
            "updated_at": self.updated_at,
        }


@dataclass
class OutputPacket:
    speech: str
    head_movement: str
    state: str
    laser_target: str | None = None
    current_exhibit: str | None = None
    tour_plan: list[str] = field(default_factory=list)
    visitor_sentiment: str = "neutral"
    pre_speech_delay_ms: int = 0
    post_speech_delay_ms: int = 0
    pause_for_thought_ms: int = 0

    def to_dict(self) -> dict:
        head = self.head_movement if self.head_movement in HEAD_MOVEMENTS else "eye_contact"
        return {
            "speech": self.speech,
            "head_movement": head,
            "laser_target": self.laser_target,
            "current_exhibit": self.current_exhibit,
            "tour_plan": self.tour_plan,
            "state": self.state,
            "visitor_sentiment": self.visitor_sentiment,
            "pre_speech_delay_ms": max(0, int(self.pre_speech_delay_ms)),
            "post_speech_delay_ms": max(0, int(self.post_speech_delay_ms)),
            "pause_for_thought_ms": max(0, int(self.pause_for_thought_ms)),
        }
