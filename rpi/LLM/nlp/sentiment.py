"""Lexical sentiment scorer for visitor utterances.

Provides a lightweight, dependency-free approach to estimating visitor
engagement level from free-text input.  The score is a floating-point value
computed by counting positive and negative keyword hits; an optional
LLM-derived hint and a silence flag can shift the result.

Output labels
-------------
``"engaged"``  — score ≥ +0.75 (or LLM hint is ``"engaged"``)
``"disengaged"`` — score ≤ −0.75, silence, or LLM hint is ``"disengaged"``
``"neutral"``  — all other cases

The result is appended to :attr:`~LLM.domain.models.VisitorProfile.sentiment_history`
and used by :func:`~LLM.io_layer.output_store.apply_timing` to adjust
pre/post-speech delays.
"""
from __future__ import annotations


def lexical_sentiment_score(text: str | None) -> float:
    if not text:
        return 0.0
    message = text.lower()
    positive = ["great", "nice", "cool", "interesting", "love", "good", "wow", "curious"]
    negative = ["boring", "tired", "bad", "stop", "skip", "long", "confused", "annoying"]

    score = 0.0
    for token in positive:
        if token in message:
            score += 1.0
    for token in negative:
        if token in message:
            score -= 1.0

    if len(message.split()) <= 2 and message not in {"yes", "no", "ok", "okay"}:
        score -= 0.5
    return score


def classify_sentiment(text: str | None, llm_hint: str | None = None, silence: bool = False) -> str:
    if silence:
        return "disengaged"

    score = lexical_sentiment_score(text)
    if llm_hint in {"engaged", "neutral", "disengaged"}:
        if llm_hint == "engaged":
            score += 0.8
        elif llm_hint == "disengaged":
            score -= 0.8

    if score <= -0.75:
        return "disengaged"
    if score >= 0.75:
        return "engaged"
    return "neutral"
