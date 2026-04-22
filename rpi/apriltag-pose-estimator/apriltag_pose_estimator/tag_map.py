"""
AprilTag map management: loading tag definitions with global coordinates.
"""

import json
from pathlib import Path
from typing import Dict, NamedTuple, Optional

import numpy as np


class TagDefinition(NamedTuple):
    """
    Definition of an AprilTag with its global 2D pose.

    Attributes:
        tag_id (int): Unique AprilTag ID.
        x (float): Global X position (meters).
        y (float): Global Y position (meters).
        yaw (float): Global yaw rotation (radians, typically [-π, π]).
        size (float): Physical size of the tag (meters, side length).
    """

    tag_id: int
    x: float
    y: float
    yaw: float
    size: float


class AprilTagMap:
    """
    Map of AprilTags with known global coordinates.

    Provides lookup and storage of tag definitions for pose estimation.
    """

    def __init__(self, tags: Optional[Dict[int, TagDefinition]] = None):
        """
        Initialize tag map.

        Args:
            tags: Optional dict mapping tag_id -> TagDefinition.
        """
        self._tags: Dict[int, TagDefinition] = tags or {}

    def add_tag(
        self, tag_id: int, x: float, y: float, yaw: float, size: float
    ) -> None:
        """
        Add or update a tag definition.

        Args:
            tag_id: Unique AprilTag ID.
            x: Global X position (meters).
            y: Global Y position (meters).
            yaw: Global yaw rotation (radians).
            size: Physical tag size (meters).
        """
        self._tags[tag_id] = TagDefinition(
            tag_id=tag_id, x=x, y=y, yaw=yaw, size=size
        )

    def get_tag(self, tag_id: int) -> Optional[TagDefinition]:
        """
        Retrieve a tag definition by ID.

        Args:
            tag_id: AprilTag ID.

        Returns:
            TagDefinition if found, None otherwise.
        """
        return self._tags.get(tag_id)

    def get_all_tags(self) -> Dict[int, TagDefinition]:
        """Return all tags as a dictionary."""
        return dict(self._tags)

    def __len__(self) -> int:
        """Return number of tags in map."""
        return len(self._tags)

    def __contains__(self, tag_id: int) -> bool:
        """Check if tag ID is in map."""
        return tag_id in self._tags

    @classmethod
    def from_json(cls, json_path: str) -> "AprilTagMap":
        """
        Load tag map from JSON file.

        Expected JSON structure:
        ```json
        {
          "tags": [
            {
              "tag_id": 0,
              "x": 0.0,
              "y": 0.0,
              "yaw": 0.0,
              "size": 0.1
            },
            ...
          ]
        }
        ```

        Args:
            json_path: Path to JSON file.

        Returns:
            AprilTagMap instance.

        Raises:
            FileNotFoundError: If file doesn't exist.
            ValueError: If JSON is malformed or missing required fields.
        """
        json_path = Path(json_path)
        if not json_path.exists():
            raise FileNotFoundError(f"Tag map file not found: {json_path}")

        with open(json_path, "r") as f:
            data = json.load(f)

        if "tags" not in data:
            raise ValueError("Missing 'tags' key in JSON")

        tag_map = cls()
        for tag_data in data["tags"]:
            required_fields = {"tag_id", "x", "y", "yaw", "size"}
            if not required_fields.issubset(tag_data.keys()):
                missing = required_fields - set(tag_data.keys())
                raise ValueError(
                    f"Tag entry missing required fields: {missing}. Entry: {tag_data}"
                )

            tag_map.add_tag(
                tag_id=int(tag_data["tag_id"]),
                x=float(tag_data["x"]),
                y=float(tag_data["y"]),
                yaw=float(tag_data["yaw"]),
                size=float(tag_data["size"]),
            )

        return tag_map

    def to_json(self, json_path: str) -> None:
        """
        Save tag map to JSON file.

        Args:
            json_path: Output path.
        """
        json_path = Path(json_path)
        json_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "tags": [
                {
                    "tag_id": tag.tag_id,
                    "x": tag.x,
                    "y": tag.y,
                    "yaw": tag.yaw,
                    "size": tag.size,
                }
                for tag in self._tags.values()
            ]
        }

        with open(json_path, "w") as f:
            json.dump(data, f, indent=2)

    def __repr__(self) -> str:
        return f"AprilTagMap({len(self._tags)} tags)"
