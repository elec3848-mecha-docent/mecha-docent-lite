"""
Unit tests for tag_map module.
"""

import pytest

from apriltag_pose_estimator import AprilTagMap, TagDefinition


class TestAprilTagMap:
    """Tests for AprilTagMap class."""

    def test_init_empty(self):
        """Test initialization with empty map."""
        tag_map = AprilTagMap()
        assert len(tag_map) == 0
        assert 0 not in tag_map

    def test_add_tag(self):
        """Test adding tags to map."""
        tag_map = AprilTagMap()
        tag_map.add_tag(tag_id=0, x=1.0, y=2.0, yaw=0.5, size=0.1)
        
        assert len(tag_map) == 1
        assert 0 in tag_map
        tag = tag_map.get_tag(0)
        assert tag.tag_id == 0
        assert tag.x == 1.0
        assert tag.y == 2.0

    def test_get_tag_not_found(self):
        """Test getting non-existent tag."""
        tag_map = AprilTagMap()
        assert tag_map.get_tag(999) is None

    def test_get_all_tags(self, sample_tag_map):
        """Test getting all tags."""
        all_tags = sample_tag_map.get_all_tags()
        assert len(all_tags) == 3
        assert 0 in all_tags
        assert 1 in all_tags
        assert 2 in all_tags

    def test_from_json_valid(self, sample_tag_map_json):
        """Test loading from JSON file."""
        tag_map = AprilTagMap.from_json(str(sample_tag_map_json))
        assert len(tag_map) == 3
        
        tag0 = tag_map.get_tag(0)
        assert tag0.x == 0.0
        assert tag0.y == 0.0
        assert tag0.size == 0.1

    def test_from_json_file_not_found(self):
        """Test loading from non-existent file."""
        with pytest.raises(FileNotFoundError):
            AprilTagMap.from_json("/nonexistent/tags.json")

    def test_from_json_missing_tags_key(self, tmp_path):
        """Test loading JSON with missing 'tags' key."""
        bad_json = tmp_path / "bad.json"
        bad_json.write_text('{"other": []}')
        
        with pytest.raises(ValueError, match="tags"):
            AprilTagMap.from_json(str(bad_json))

    def test_from_json_missing_field_in_tag(self, tmp_path):
        """Test loading JSON with missing field in tag."""
        bad_json = tmp_path / "bad.json"
        bad_json.write_text('{"tags": [{"tag_id": 0, "x": 0.0}]}')
        
        with pytest.raises(ValueError, match="required fields"):
            AprilTagMap.from_json(str(bad_json))

    def test_to_json(self, sample_tag_map, tmp_path):
        """Test saving to JSON file."""
        output_file = tmp_path / "output.json"
        sample_tag_map.to_json(str(output_file))
        
        assert output_file.exists()
        # Load it back and verify
        loaded = AprilTagMap.from_json(str(output_file))
        assert len(loaded) == len(sample_tag_map)

    def test_repr(self, sample_tag_map):
        """Test string representation."""
        repr_str = repr(sample_tag_map)
        assert "AprilTagMap" in repr_str
        assert "3 tags" in repr_str


class TestTagDefinition:
    """Tests for TagDefinition class."""

    def test_tag_definition_creation(self):
        """Test creating a TagDefinition."""
        tag = TagDefinition(tag_id=5, x=1.5, y=2.5, yaw=0.3, size=0.15)
        
        assert tag.tag_id == 5
        assert tag.x == 1.5
        assert tag.y == 2.5
        assert tag.yaw == 0.3
        assert tag.size == 0.15
