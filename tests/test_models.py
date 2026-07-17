"""测试数据模型（Pydantic 校验、枚举值、序列化）。"""

import json

import pytest
from pydantic import ValidationError

from src.models.building import (
    BlockMaterial,
    BuildingDescription,
    BuildingFeature,
    MinecraftVersion,
)


class TestMinecraftVersion:
    def test_valid_values(self):
        assert MinecraftVersion("java-1.12") == MinecraftVersion.JAVA_1_12
        assert MinecraftVersion("java-1.20") == MinecraftVersion.JAVA_1_20
        assert MinecraftVersion("bedrock-1.20") == MinecraftVersion.BEDROCK_1_20

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            MinecraftVersion("java-1.99")

    def test_all_versions_covered(self):
        assert len(MinecraftVersion) == 5


class TestBlockMaterial:
    def test_minimal(self):
        m = BlockMaterial(name="stone")
        assert m.name == "stone"
        assert m.color is None
        assert m.fraction == 1.0

    def test_full(self):
        m = BlockMaterial(name="oak_planks", color="brown", fraction=0.5)
        assert m.fraction == 0.5

    def test_fraction_bounds(self):
        with pytest.raises(ValidationError):
            BlockMaterial(name="stone", fraction=1.5)
        with pytest.raises(ValidationError):
            BlockMaterial(name="stone", fraction=-0.1)

    def test_serialize(self):
        m = BlockMaterial(name="stone_bricks", color="gray", fraction=0.7)
        d = m.model_dump()
        assert d["name"] == "stone_bricks"
        assert d["fraction"] == 0.7


class TestBuildingFeature:
    def test_minimal(self):
        f = BuildingFeature(feature_type="window")
        assert f.count == 1
        assert f.position is None

    def test_negative_count(self):
        with pytest.raises(ValidationError):
            BuildingFeature(feature_type="door", count=-1)


class TestBuildingDescription:
    def test_minimal_valid(self):
        desc = BuildingDescription(
            building_type="house",
            height=5,
            width=4,
            length=6,
        )
        assert desc.shape == "rectangle"
        assert desc.style == "modern"
        assert desc.materials == []
        assert desc.description == ""

    def test_default_version(self):
        desc = BuildingDescription(
            building_type="tower", height=10, width=5, length=5
        )
        assert desc.minecraft_version == MinecraftVersion.JAVA_1_20

    def test_height_bounds(self):
        with pytest.raises(ValidationError):
            BuildingDescription(building_type="x", height=0, width=1, length=1)
        with pytest.raises(ValidationError):
            BuildingDescription(building_type="x", height=257, width=1, length=1)

    def test_full_description(self):
        desc = BuildingDescription(
            minecraft_version=MinecraftVersion.JAVA_1_17,
            building_type="church",
            height=15, width=10, length=20,
            shape="cross", style="gothic",
            materials=[
                BlockMaterial(name="stone_bricks", fraction=0.8),
                BlockMaterial(name="glass", fraction=0.2),
            ],
            features=[
                BuildingFeature(feature_type="roof", position="gable"),
                BuildingFeature(feature_type="door", position="front"),
            ],
            description="A gothic church",
        )
        assert desc.minecraft_version == MinecraftVersion.JAVA_1_17
        assert len(desc.materials) == 2
        assert len(desc.features) == 2

    def test_serialize_roundtrip(self):
        desc = BuildingDescription(
            building_type="villa", height=8, width=6, length=10,
            materials=[
                BlockMaterial(name="stone_bricks", fraction=0.6),
                BlockMaterial(name="glass", fraction=0.4),
            ],
            features=[
                BuildingFeature(feature_type="window", position="front", count=4),
            ],
            description="Test villa",
        )
        d = desc.model_dump()
        restored = BuildingDescription(**d)
        assert restored.building_type == desc.building_type
        assert restored.height == desc.height
        assert len(restored.materials) == 2
        assert restored.materials[0].name == "stone_bricks"

    def test_json_roundtrip(self):
        desc = BuildingDescription(
            building_type="pagoda", height=14, width=8, length=8,
        )
        json_str = desc.model_dump_json()
        restored = BuildingDescription.model_validate_json(json_str)
        assert restored.building_type == "pagoda"
        assert restored.width == 8
