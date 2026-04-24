"""Conversation finite-state machine for the Medo dialogue engine.

Defines the :class:`State` enumeration and the :class:`FSM` class that
enforces valid state transitions.  The allowed graph is:

.. code-block:: text

    GREETING → PROFILING → PLANNING → EXPLAINING
                │                        │
                └──────────────────── PAUSED
                                        │
                                   REROUTING
                                        │
                                   FAREWELL

Any attempt to perform a transition not listed in :data:`VALID_TRANSITIONS`
raises a :exc:`ValueError`.
"""
from __future__ import annotations

from enum import Enum


class State(str, Enum):
    GREETING = "greeting"
    PROFILING = "profiling"
    PLANNING = "planning"
    EXPLAINING = "explaining"
    PAUSED = "paused"
    REROUTING = "rerouting"
    FAREWELL = "farewell"


VALID_TRANSITIONS: dict[State, set[State]] = {
    State.GREETING: {State.PROFILING, State.FAREWELL},
    State.PROFILING: {State.PLANNING, State.FAREWELL},
    State.PLANNING: {State.EXPLAINING, State.FAREWELL},
    State.EXPLAINING: {State.PAUSED, State.REROUTING, State.FAREWELL},
    State.PAUSED: {State.EXPLAINING, State.REROUTING, State.FAREWELL},
    State.REROUTING: {State.EXPLAINING, State.FAREWELL},
    State.FAREWELL: set(),
}


class FSM:
    def __init__(self) -> None:
        self.state = State.GREETING

    def transition(self, next_state: State) -> None:
        if next_state == self.state:
            return
        if next_state not in VALID_TRANSITIONS[self.state]:
            raise ValueError(f"Invalid transition: {self.state} -> {next_state}")
        self.state = next_state
