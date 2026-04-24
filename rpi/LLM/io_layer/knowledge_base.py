"""Exhibit knowledge-base loader and indexer.

Loads exhibit data from a JSON file whose top-level key is ``"exhibits"``,
deserialises each entry into an :class:`~LLM.domain.models.Exhibit` with its
associated :class:`~LLM.domain.models.ExhibitFeature` list, and provides a
dictionary index for O(1) lookups by exhibit ID.

Expected JSON schema
--------------------
.. code-block:: json

    {
      "exhibits": [
        {
          "id": "starry-night",
          "title": "The Starry Night",
          "artist": "Vincent van Gogh",
          "tags": ["post-impressionism", "landscape"],
          "features": [
            { "tag": "colour_palette", "annotation": "..." }
          ]
        }
      ]
    }
"""
from __future__ import annotations

import json
from pathlib import Path

from LLM.domain.models import Exhibit, ExhibitFeature


def load_exhibits(path: str) -> list[Exhibit]:
    exhibits_path = Path(path).expanduser().resolve()
    if not exhibits_path.is_file():
        raise SystemExit(f"Exhibits file not found: {exhibits_path}")

    with exhibits_path.open(encoding="utf-8") as fh:
        data = json.load(fh)

    raw = data.get("exhibits", [])
    if not isinstance(raw, list) or not raw:
        raise SystemExit("exhibits.json must contain a non-empty 'exhibits' array")

    exhibits: list[Exhibit] = []
    for item in raw:
        features = [
            ExhibitFeature(tag=f.get("tag", "feature"), annotation=f.get("annotation", ""))
            for f in item.get("features", [])
        ]
        exhibits.append(
            Exhibit(
                id=item.get("id", "unknown"),
                title=item.get("title", "Untitled"),
                artist=item.get("artist", "Unknown"),
                tags=item.get("tags", []),
                features=features,
            )
        )
    return exhibits


def index_exhibits(exhibits: list[Exhibit]) -> dict[str, Exhibit]:
    return {item.id: item for item in exhibits}
