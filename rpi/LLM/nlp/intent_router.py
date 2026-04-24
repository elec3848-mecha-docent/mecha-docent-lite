"""Rule-based visitor intent classifier.

Classifies a single visitor utterance into one of the intent constants
defined in this module using keyword matching, phrase matching, and simple
regex patterns.  No ML model is required.

Intent constants
----------------
``INTENT_YES``, ``INTENT_NO``, ``INTENT_HESITANT``
    Affirmative / negative / uncertain responses.
``INTENT_BORED``, ``INTENT_SWITCH``
    Visitor wants to move on.
``INTENT_TOO_LONG``, ``INTENT_TOO_SHORT``
    Feedback on explanation verbosity; triggers ``detail_preference`` update.
``INTENT_TIME_INFO``
    Visitor mentions how many minutes they have.
``INTENT_QUESTION``
    Visitor is asking a question.
``INTENT_STOP``
    Visitor wants to end the tour.
``INTENT_UNKNOWN``
    Default when no pattern matches.

Public API
----------
:func:`classify_intent` — map text to an intent constant string.
:func:`extract_time_budget_minutes` — parse a minute count from text.
"""
from __future__ import annotations

import re


INTENT_YES = "yes"
INTENT_NO = "no"
INTENT_HESITANT = "hesitant"
INTENT_BORED = "bored"
INTENT_TOO_LONG = "too_long"
INTENT_TOO_SHORT = "too_short"
INTENT_TIME_INFO = "time_info"
INTENT_SWITCH = "switch"
INTENT_CONTINUE = "continue"
INTENT_STOP = "stop"
INTENT_QUESTION = "question"
INTENT_UNKNOWN = "unknown"


def classify_intent(text: str | None) -> str:
    if text is None:
        return INTENT_UNKNOWN
    message = text.strip().lower()
    if not message:
        return INTENT_UNKNOWN

    if message in {"yes", "y", "sure", "ok", "okay", "yep", "yeah"}:
        return INTENT_YES
    if message in {"no", "n", "nope", "nah", "not really"}:
        return INTENT_NO
    if any(token in message for token in ["maybe", "not sure", "hmm", "i guess"]):
        return INTENT_HESITANT
    if any(token in message for token in ["bored", "boring", "skip", "next", "move on"]):
        return INTENT_BORED
    if any(token in message for token in ["too long", "long", "wordy", "shorter"]):
        return INTENT_TOO_LONG
    if any(token in message for token in ["too short", "more detail", "tell me more"]):
        return INTENT_TOO_SHORT
    if re.search(r"\b\d+\s*(min|mins|minute|minutes)\b", message):
        return INTENT_TIME_INFO
    if any(token in message for token in ["switch", "different", "another painting"]):
        return INTENT_SWITCH
    if any(token in message for token in ["stop", "done", "enough", "end"]):
        return INTENT_STOP
    if any(token in message for token in ["continue", "go on", "keep going"]):
        return INTENT_CONTINUE
    if "?" in message or message.startswith(("what", "why", "how", "who", "when", "where")):
        return INTENT_QUESTION
    return INTENT_UNKNOWN


def extract_time_budget_minutes(text: str | None) -> int | None:
    if not text:
        return None
    match = re.search(r"\b(\d{1,3})\s*(min|mins|minute|minutes)\b", text.lower())
    if not match:
        return None
    minutes = int(match.group(1))
    if minutes <= 0:
        return None
    return min(240, minutes)
