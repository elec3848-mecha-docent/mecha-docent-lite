"""Visitor profile persistence helpers.

Provides atomic read/write operations for
:class:`~LLM.domain.models.VisitorProfile` so that the current visitor's
preferences and sentiment history survive process restarts and can be inspected
between runs.

All writes are atomic (temp-file + rename) to prevent corrupt JSON on crash.
Loading a missing or malformed file silently returns a fresh
:class:`~LLM.domain.models.VisitorProfile`.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from LLM.domain.models import VisitorProfile


def reset_profile(path: str) -> VisitorProfile:
    profile = VisitorProfile()
    save_profile(path, profile)
    return profile


def load_profile(path: str) -> VisitorProfile:
    profile_path = Path(path)
    if not profile_path.exists():
        return VisitorProfile()
    try:
        with profile_path.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return VisitorProfile()

    profile = VisitorProfile()
    profile.merge(data)
    history = data.get("sentiment_history")
    if isinstance(history, list):
        profile.sentiment_history = [x for x in history if isinstance(x, str)]
    notes = data.get("notes")
    if isinstance(notes, list):
        profile.notes = [x for x in notes if isinstance(x, str)]
    facts = data.get("facts")
    if isinstance(facts, dict):
        profile.facts = {str(k): str(v) for k, v in facts.items()}
    return profile


def save_profile(path: str, profile: VisitorProfile) -> None:
    out = Path(path)
    payload = json.dumps(profile.to_dict(), ensure_ascii=False, indent=2)
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
