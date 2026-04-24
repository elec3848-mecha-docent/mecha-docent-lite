"""Pre-written dialogue templates for the Medo dialogue engine.

:data:`TEMPLATES` is a dictionary mapping template keys to lists of variant
strings.  :func:`pick` selects variants in round-robin order so the robot
does not repeat the same phrase back-to-back.

Template keys cover:

* Greeting / farewell acknowledgements
* Tour rejection rebuttals
* Time-budget prompts
* Routing and rerouting announcements
* Engagement check-in questions
* Verbosity adjustment acknowledgements
* Generic fallback responses

:func:`head_for_state` maps an FSM :class:`~LLM.core.state_machine.State`
value to the appropriate ``head_movement`` string for the output packet.
"""
from __future__ import annotations

from collections import defaultdict

from LLM.core.state_machine import State


TEMPLATES: dict[str, list[str]] = {
    "greeting_no_ack": [
        "No worries. Are you sure? I can show you around if you change your mind.",
        "That is totally fine. Are you sure? I can still guide a short tour.",
    ],
    "greeting_hesitant": [
        "No pressure. I can do a quick highlight tour if you like.",
        "Totally okay to be unsure. I can keep it brief and adaptive.",
    ],
    "time_check": [
        "Before we continue, how much time do you have today?",
        "Quick check: how many minutes would you like to spend here?",
    ],
    "verbosity_check": [
        "Am I going on too long, or is this level of detail okay?",
        "Would you like shorter summaries so we can cover more pieces?",
    ],
    "engagement_check": [
        "How are you feeling so far? Want to keep this pace?",
        "Is this pace working for you, or should we switch things up?",
    ],
    "bored_confirm": [
        "I can switch to a different painting right now. Want me to?",
        "Would you like me to jump to something that fits you better?",
    ],
    "short_mode_ack": [
        "Got it. I will keep things concise from now on.",
        "Understood. I will use shorter explanations from here.",
    ],
    "detailed_mode_ack": [
        "Great, I will go deeper into the details.",
        "Nice. I will include more context and detail.",
    ],
    "default_followup": [
        "Would you like to continue?",
        "Want to go to the next part?",
    ],
    "farewell": [
        "Thanks for visiting. I loved guiding you today.",
        "Thank you for spending time with me at the museum.",
    ],
}


_rotor: dict[str, int] = defaultdict(int)


def pick(key: str) -> str:
    options = TEMPLATES.get(key, TEMPLATES["default_followup"])
    idx = _rotor[key] % len(options)
    _rotor[key] += 1
    return options[idx]


def head_for_state(state: State) -> str:
    if state == State.EXPLAINING:
        return "painting"
    if state == State.REROUTING:
        return "direction"
    if state == State.FAREWELL:
        return "nod-yes"
    if state == State.PAUSED:
        return "eye_contact"
    return "eye_contact"
