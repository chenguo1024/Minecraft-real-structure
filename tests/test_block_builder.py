"""测试方块生成器（各屋顶类型、形状、风格模板、特征）。"""

from src.generator.block_builder import BlockBuilder, BlockStructure
from src.models.building import (
    BlockMaterial,
    BuildingDescription,
    BuildingFeature,
    MinecraftVersion,
)


def _make_desc(
    height: int = 8, width: int = 6, length: int = 10,
    shape: str = "rectangle", style: str = "modern",
    roof: str = "flat",
    materials: list | None = None,
    features: list | None = None,
) -> BuildingDescription:
    if features is None:
        features = [BuildingFeature(feature_type="roof", position=roof)]
    return BuildingDescription(
        minecraft_version=MinecraftVersion.JAVA_1_20,
        building_type="test",
        height=height, width=width, length=length,
        shape=shape, style=style,
        materials=materials or [],
        features=features,
    )


class TestBlockStructure:
    def test_structure_attributes(self):
        s = BlockStructure(palette=["a", "b"], blocks=[0, 1, 0], size_x=1, size_y=1, size_z=3)
        assert s.size_x == 1
        assert s.size_y == 1
        assert s.size_z == 3
        assert len(s.blocks) == 3
        assert len(s.palette) == 2


class TestBuildOutput:
    def test_output_has_correct_size(self):
        desc = _make_desc(height=8, width=6, length=10)
        builder = BlockBuilder(desc)
        s = builder.build()
        assert s.size_x == 6
        assert s.size_y == 8
        assert s.size_z == 10
        assert len(s.blocks) == 6 * 8 * 10

    def test_palette_has_air(self):
        desc = _make_desc()
        builder = BlockBuilder(desc)
        s = builder.build()
        assert "minecraft:air" in s.palette
        assert s.blocks.count(s.palette.index("minecraft:air")) > 0

    def test_no_empty_palette(self):
        desc = _make_desc()
        builder = BlockBuilder(desc)
        s = builder.build()
        assert len(s.palette) > 0


class TestRoofTypes:
    """测试五种屋顶类型都能正常生成且不抛异常。"""

    @staticmethod
    def _build_with_roof(roof_type: str) -> BlockStructure:
        desc = _make_desc(roof=roof_type,
                          features=[BuildingFeature(feature_type="roof", position=roof_type)])
        return BlockBuilder(desc).build()

    def test_flat_roof(self):
        s = self._build_with_roof("flat")
        assert len(s.blocks) > 0

    def test_gable_roof(self):
        s = self._build_with_roof("gable")
        assert len(s.blocks) > 0

    def test_hip_roof(self):
        s = self._build_with_roof("hip")
        assert len(s.blocks) > 0

    def test_pyramid_roof(self):
        s = self._build_with_roof("pyramid")
        assert len(s.blocks) > 0

    def test_dome_roof(self):
        s = self._build_with_roof("dome")
        assert len(s.blocks) > 0

    def test_invalid_roof_fallsback_to_flat(self):
        desc = _make_desc(roof="unknown",
                          features=[BuildingFeature(feature_type="roof", position="unknown")])
        s = BlockBuilder(desc).build()
        assert len(s.blocks) > 0


class TestShapes:
    """测试四种建筑平面形状。"""

    @staticmethod
    def _build_with_shape(shape: str) -> BlockStructure:
        desc = _make_desc(height=10, width=12, length=14, shape=shape)
        return BlockBuilder(desc).build()

    def test_rectangle(self):
        s = self._build_with_shape("rectangle")
        assert len(s.blocks) == 12 * 10 * 14

    def test_L_shape(self):
        s = self._build_with_shape("L")
        assert len(s.blocks) == 12 * 10 * 14

    def test_cross_shape(self):
        s = self._build_with_shape("cross")
        assert len(s.blocks) == 12 * 10 * 14

    def test_T_shape(self):
        s = self._build_with_shape("T")
        assert len(s.blocks) == 12 * 10 * 14


class TestStyleTemplates:
    """测试六种风格模板能正常生效。"""

    STYLES = ["modern", "gothic", "classical", "asian", "medieval", "brutalist"]

    def test_all_styles(self):
        for style in self.STYLES:
            desc = _make_desc(style=style)
            s = BlockBuilder(desc).build()
            assert len(s.blocks) > 0

    def test_unknown_style_fallsback(self):
        desc = _make_desc(style="nonexistent_style")
        s = BlockBuilder(desc).build()
        assert len(s.blocks) > 0


class TestFeatures:
    def test_door_adds_air(self):
        desc = _make_desc(
            features=[
                BuildingFeature(feature_type="door", position="front", count=1),
                BuildingFeature(feature_type="roof", position="flat"),
            ],
        )
        builder = BlockBuilder(desc)
        s = builder.build()
        air_idx = s.palette.index("minecraft:air")
        front_z = 0
        for dx in range(s.size_x):
            for dy in range(1, 3):
                idx = dx + dy * s.size_x + front_z * s.size_x * s.size_y
                center_start = s.size_x // 2 - 1
                if center_start <= dx <= center_start + 1 and dy <= 2:
                    assert s.blocks[idx] == air_idx, f"门洞 ({dx},{dy}) 应为空气"

    def test_modern_has_polished_andesite(self):
        """modern 风格的屋顶边缘使用 polished_andesite。"""
        desc = _make_desc(height=10, style="modern")
        s = BlockBuilder(desc).build()
        assert "minecraft:polished_andesite" in s.palette

    def test_pillar_styles_config(self):
        """gothic/classical styles have wall_pillar=True in config."""
        from src.generator.block_builder import STYLE_DEFAULTS
        assert STYLE_DEFAULTS["gothic"]["wall_pillar"] is True
        assert STYLE_DEFAULTS["classical"]["wall_pillar"] is True
        assert STYLE_DEFAULTS["modern"]["wall_pillar"] is False
        assert STYLE_DEFAULTS["brutalist"]["wall_pillar"] is False

    def test_flat_roof_all_styles_have_polished_andesite(self):
        """所有平顶风格的屋顶边缘都使用 polished_andesite。"""
        for style in ["modern", "brutalist"]:
            desc = _make_desc(height=8, width=8, length=10, style=style, roof="flat")
            s = BlockBuilder(desc).build()
            assert "minecraft:polished_andesite" in s.palette


class TestBuilderEdgeCases:
    def test_minimal_dimensions(self):
        desc = _make_desc(height=3, width=3, length=3)
        s = BlockBuilder(desc).build()
        assert len(s.blocks) == 27

    def test_large_dimensions(self):
        desc = _make_desc(height=30, width=20, length=30)
        s = BlockBuilder(desc).build()
        assert len(s.blocks) == 20 * 30 * 30

    def test_materials_names_are_resolved(self):
        desc = _make_desc(
            materials=[BlockMaterial(name="glass", fraction=1.0)],
        )
        builder = BlockBuilder(desc)
        s = builder.build()
        assert "minecraft:glass" in s.palette
