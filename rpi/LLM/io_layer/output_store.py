"""Output packet timing, serialisation, and display utilities.

Responsibilities
----------------
* **Timing policy** (:data:`TIMING_POLICY`): per-state baseline values for
  ``pre_speech_delay_ms``, ``post_speech_delay_ms``, and
  ``pause_for_thought_ms``.
* :func:`apply_timing`: adjusts timing based on the visitor's
  ``detail_preference`` (brief / detailed) and current sentiment
  (engaged / disengaged).
* :func:`write_packet`: atomically writes an
  :class:`~LLM.domain.models.OutputPacket` to disk as JSON (write to temp
  file, then rename) so downstream readers never see a partial write.
* :func:`show_packet`: prints a human-readable summary to stdout for
  development/debugging.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from LLM.core.state_machine import State
from LLM.domain.models import OutputPacket


TIMING_POLICY = {
    State.GREETING.value: (150, 200, 350),
    State.PROFILING.value: (150, 200, 400),
    State.PLANNING.value: (250, 300, 500),
    State.EXPLAINING.value: (100, 250, 850),
    State.PAUSED.value: (80, 180, 350),
    State.REROUTING.value: (120, 220, 450),
    State.FAREWELL.value: (180, 220, 600),
}


def apply_timing(packet: OutputPacket, pace: str, sentiment: str) -> OutputPacket:
    pre, post, think = TIMING_POLICY.get(packet.state, (120, 200, 400))

    if pace == "brief":
        pre = max(50, pre - 60)
        post = max(100, post - 80)
        think = max(200, think - 300)
    elif pace == "detailed":
        pre += 40
        post += 120
        think += 200

    if sentiment == "disengaged":
        think = max(180, think - 350)
    elif sentiment == "engaged":
        think += 120

    packet.pre_speech_delay_ms = pre
    packet.post_speech_delay_ms = post
    packet.pause_for_thought_ms = think
    return packet


def write_packet(path: str, packet: OutputPacket) -> None:
    out = Path(path)
    payload = json.dumps(packet.to_dict(), ensure_ascii=False, indent=2)
    fd, temp_path = tempfile.mkstemp(dir=out.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
        os.replace(temp_path, out)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def show_packet(packet: OutputPacket) -> None:
    print(f"\nMedo> {packet.speech}")
    print(
        "  "
        f"[head: {packet.head_movement}] "
        f"[state: {packet.state}] "
        f"[pre: {packet.pre_speech_delay_ms}ms post: {packet.post_speech_delay_ms}ms think: {packet.pause_for_thought_ms}ms]"
    )
    if packet.laser_target:
        print(f"  [laser: {packet.laser_target}]")
