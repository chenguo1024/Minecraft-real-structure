"""测试方块生成器（各屋顶类型、形状、风格模板、特征）。"""

from src.generator.block_builder import BlockBuilder, BlockStructure
from src.models.building import (
    BlockMaterial,
    BuildingDescription,
    BuildingFeature,
    Facade,
    FaceWindow,
    FaceOpening,
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

    def test_xieshan_roof(self):
        s = self._build_with_roof("xieshan")
        assert len(s.blocks) > 0

    def test_curved_roof(self):
        s = self._build_with_roof("curved")
        assert len(s.blocks) > 0

    def test_eaved_roof(self):
        desc = _make_desc(
            roof="eaved",
            features=[BuildingFeature(feature_type="roof", position="eaved")],
        )
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


class TestFacades:
    """测试逐面生成（facades）功能。"""

    def _facade_desc(self, **overrides) -> BuildingDescription:
        params = dict(
            minecraft_version=MinecraftVersion.JAVA_1_20,
            building_type="house",
            height=10, width=12, length=12,
            style="modern",
            materials=[BlockMaterial(name="stone_bricks")],
            features=[BuildingFeature(feature_type="roof", position="flat")],
            facades=[
                Facade(face="front", material="stone_bricks",
                       windows=[FaceWindow(x=0.5, width=0.2, height=2, y_offset=2)],
                       openings=[FaceOpening(x=0.5, width=0.3, height=3, style="rectangle")]),
            ],
        )
        params.update(overrides)
        return BuildingDescription(**params)

    def test_facades_route_to_separate_path(self):
        """facades 非空时触发 _build_from_facades 路径。"""
        desc = self._facade_desc()
        builder = BlockBuilder(desc)
        s = builder.build()
        assert len(s.blocks) == 12 * 10 * 12

    def test_facade_front_wall_exists(self):
        """正面墙（z=0）有墙块。"""
        desc = self._facade_desc()
        builder = BlockBuilder(desc)
        s = builder.build()
        air_idx = s.palette.index("minecraft:air")
        # z=0, y=2, x=6 应在窗户区域或门洞区域，但我们先检查墙存在
        # y=3 超出窗户高度应在墙区域
        idx = lambda x, y, z: x + y * s.size_x + z * s.size_x * s.size_y
        # 正面墙中间偏右（非窗户非门）应为实心
        solid = s.blocks[idx(2, 4, 0)]
        assert solid != air_idx, "正面墙中间应为实心块"

    def test_facade_creates_window(self):
        """正面窗户位置应为玻璃。"""
        desc = self._facade_desc()
        builder = BlockBuilder(desc)
        s = builder.build()
        glass_idx = s.palette.index("minecraft:glass")
        idx = lambda x, y, z: x + y * s.size_x + z * s.size_x * s.size_y
        # 窗在 x=int(0.5*11)=5, y=2..3。但 y=2 被门洞覆盖，y=3 应为玻璃
        win_block = s.blocks[idx(5, 3, 0)]
        assert win_block == glass_idx, f"窗户位置 x=5,y=3,z=0 应为玻璃，实际索引 {win_block}"

    def test_facade_creates_door_opening(self):
        """正面门洞区域应为空气。"""
        desc = self._facade_desc()
        builder = BlockBuilder(desc)
        s = builder.build()
        air_idx = s.palette.index("minecraft:air")
        idx = lambda x, y, z: x + y * s.size_x + z * s.size_x * s.size_y
        # 门在 x=int(0.5*12)=5, width=int(0.3*12)=3, 所以 x=4~6, y=0~2
        for dx in range(4, 7):
            assert s.blocks[idx(dx, 1, 0)] == air_idx, f"门洞 x={dx},y=1 应为空气"

    def test_facade_multiple_faces(self):
        """多面同时生效。"""
        desc = self._facade_desc(
            facades=[
                Facade(face="front", material="stone_bricks",
                       openings=[FaceOpening(x=0.5, width=0.3, height=3)]),
                Facade(face="back", material="quartz_block",
                       windows=[FaceWindow(x=0.3, width=0.2, height=2, y_offset=2)]),
            ],
        )
        builder = BlockBuilder(desc)
        s = builder.build()
        assert "minecraft:quartz_block" in s.palette, "背面用了不同材料"

    def test_facade_columns_placed(self):
        """立柱被正确放置。"""
        desc = self._facade_desc(
            facades=[
                Facade(face="front", material="stone_bricks",
                       columns=[0.1, 0.5, 0.9]),
            ],
        )
        builder = BlockBuilder(desc)
        s = builder.build()
        stone_idx = s.palette.index("minecraft:stone_bricks")
        air_idx = s.palette.index("minecraft:air")
        idx = lambda x, y, z: x + y * s.size_x + z * s.size_x * s.size_y
        # 柱子使用默认材料 (stone_bricks)，位置 int(0.1*11)=1, int(0.5*11)=5, int(0.9*11)=9
        for col_x in [1, 5, 9]:
            block = s.blocks[idx(col_x, 2, 0)]
            assert block == stone_idx, f"x={col_x} 应为 stone_bricks"

    def test_facade_no_windows_without_feature(self):
        """没有 windows 列表时不开窗。"""
        from src.generator.block_builder import MAT_WINDOW
        desc = self._facade_desc(
            facades=[Facade(face="front", material="stone_bricks")],
        )
        builder = BlockBuilder(desc)
        s = builder.build()
        # 正面整面墙应无玻璃窗
        if "minecraft:glass" in s.palette:
            glass_idx = s.palette.index("minecraft:glass")
            idx = lambda x, y, z: x + y * s.size_x + z * s.size_x * s.size_y
            for x in range(s.size_x):
                for y in range(1, s.size_y - 1):
                    block = s.blocks[idx(x, y, 0)]
                    assert block != glass_idx, f"正面 ({x},{y}) 不应有玻璃"

    def test_facade_cornice(self):
        """檐口线脚被放置。"""
        desc = self._facade_desc(
            materials=[BlockMaterial(name="stone_bricks"), BlockMaterial(name="polished_andesite")],
            facades=[Facade(face="front", material="stone_bricks", cornice=True)],
        )
        builder = BlockBuilder(desc)
        s = builder.build()
        andesite_idx = s.palette.index("minecraft:polished_andesite")
        idx = lambda x, y, z: x + y * s.size_x + z * s.size_x * s.size_y
        # 檐口在 y=h-1=9 (wy2+1), z=0
        cornice_block = s.blocks[idx(3, 9, 0)]
        assert cornice_block == andesite_idx, "檐口应为 polished_andesite"

    def test_facade_back_mirrors_config(self):
        """背面独立于正面。"""
        desc = self._facade_desc(
            materials=[BlockMaterial(name="stone_bricks"), BlockMaterial(name="quartz_block")],
            facades=[
                Facade(face="front", material="stone_bricks"),
                Facade(face="back", material="quartz_block"),
            ],
        )
        builder = BlockBuilder(desc)
        s = builder.build()
        idx = lambda x, y, z: x + y * s.size_x + z * s.size_x * s.size_y
        qb_idx = s.palette.index("minecraft:quartz_block")
        stone_idx = s.palette.index("minecraft:stone_bricks")
        front = s.blocks[idx(3, 3, 0)]
        back = s.blocks[idx(3, 3, s.size_z - 1)]
        assert front == stone_idx, "正面应为 stone_bricks"
        assert back == qb_idx, "背面应为 quartz_block"

    def test_facade_all_faces_different(self):
        """四个面各自独立材料。"""
        desc = self._facade_desc(
            materials=[
                BlockMaterial(name="stone_bricks"),
                BlockMaterial(name="quartz_block"),
                BlockMaterial(name="red_terracotta"),
                BlockMaterial(name="bricks"),
            ],
            facades=[
                Facade(face="front", material="stone_bricks"),
                Facade(face="back", material="quartz_block"),
                Facade(face="left", material="red_terracotta"),
                Facade(face="right", material="bricks"),
            ],
        )
        builder = BlockBuilder(desc)
        s = builder.build()
        idx = lambda x, y, z: x + y * s.size_x + z * s.size_x * s.size_y
        palette = s.palette
        assert palette[s.blocks[idx(3, 3, 0)]] == "minecraft:stone_bricks", "正面 stone_bricks"
        assert palette[s.blocks[idx(3, 3, s.size_z - 1)]] == "minecraft:quartz_block", "背面 quartz_block"
        assert palette[s.blocks[idx(0, 3, 3)]] == "minecraft:red_terracotta", "左侧 red_terracotta"
        assert palette[s.blocks[idx(s.size_x - 1, 3, 3)]] == "minecraft:bricks", "右侧 bricks"

    def test_facade_arch_opening(self):
        """拱门样式的开口。"""
        desc = self._facade_desc(
            facades=[
                Facade(face="front", material="stone_bricks",
                       openings=[FaceOpening(x=0.5, width=0.3, height=3, style="arch")]),
            ],
        )
        builder = BlockBuilder(desc)
        s = builder.build()
        idx = lambda x, y, z: x + y * s.size_x + z * s.size_x * s.size_y
        air_idx = s.palette.index("minecraft:air")
        # 拱门底部应为空气
        assert s.blocks[idx(5, 1, 0)] == air_idx, "拱门底部应为空气"


class TestCurvesAndCircles:
    """测试曲线/圆形辅助方法。"""

    def test_circle_xz_places_blocks(self):
        desc = _make_desc(roof="flat")
        builder = BlockBuilder(desc)
        builder._grid = [
            [[builder._idx("air") for _ in range(builder.w)] for _ in range(builder.h)]
            for _ in range(builder.l)
        ]
        builder._circle_xz(3, 4, 2, 1, "stone_bricks")
        w, h, l = builder.w, builder.h, builder.l
        grid = [builder._grid[z][y][x] for z in range(l) for y in range(h) for x in range(w)]
        pal = builder._palette_list
        # check a point on the circle ring
        idx = lambda x, y, z: x + y * w + z * w * h
        assert pal[grid[idx(3, 1, 2)]] == "minecraft:stone_bricks", "圆环上应有石砖"

    def test_cylinder_y_builds_cylinder(self):
        desc = _make_desc(roof="flat")
        builder = BlockBuilder(desc)
        builder._grid = [
            [[builder._idx("air") for _ in range(builder.w)] for _ in range(builder.h)]
            for _ in range(builder.l)
        ]
        builder._cylinder_y(3, 3, 1, 0, 5, "stone_bricks")
        w, h, l = builder.w, builder.h, builder.l
        grid = [builder._grid[z][y][x] for z in range(l) for y in range(h) for x in range(w)]
        pal = builder._palette_list
        idx = lambda x, y, z: x + y * w + z * w * h
        # ring point at bottom
        assert pal[grid[idx(3, 0, 2)]] == "minecraft:stone_bricks"
        # ring point at top
        assert pal[grid[idx(3, 5, 4)]] == "minecraft:stone_bricks"

    def test_circle_xz_in_bounds(self):
        """圆不超出边界。"""
        desc = _make_desc(height=5, width=10, length=10, roof="flat")
        builder = BlockBuilder(desc)
        builder._grid = [
            [[builder._idx("air") for _ in range(builder.w)] for _ in range(builder.h)]
            for _ in range(builder.l)
        ]
        builder._circle_xz(8, 8, 3, 1, "stone_bricks")
        w, h, l = builder.w, builder.h, builder.l
        grid = [builder._grid[z][y][x] for z in range(l) for y in range(h) for x in range(w)]
        pal = builder._palette_list
        idx = lambda x, y, z: x + y * w + z * w * h
        # 圆上一点 (dx=-3, dz=0 → x=5, z=8)
        assert pal[grid[idx(5, 1, 8)]] == "minecraft:stone_bricks"


class TestInterior:
    """测试内部结构（楼梯/隔墙/家具）。"""

    def test_stairs_generated(self):
        desc = _make_desc(height=12, width=8, length=10,
                          features=[
                              BuildingFeature(feature_type="stairs"),
                              BuildingFeature(feature_type="roof", position="flat"),
                          ])
        builder = BlockBuilder(desc)
        s = builder.build()
        assert len(s.blocks) > 0

    def test_room_partitions_generated(self):
        desc = _make_desc(height=10, width=12, length=12,
                          features=[
                              BuildingFeature(feature_type="room"),
                              BuildingFeature(feature_type="roof", position="flat"),
                          ])
        builder = BlockBuilder(desc)
        s = builder.build()
        assert len(s.blocks) > 0

    def test_furniture_generated(self):
        desc = _make_desc(height=8, width=8, length=8,
                          features=[
                              BuildingFeature(feature_type="furniture"),
                              BuildingFeature(feature_type="roof", position="flat"),
                          ])
        builder = BlockBuilder(desc)
        s = builder.build()
        assert len(s.blocks) > 0

    def test_interior_all_features(self):
        desc = _make_desc(height=12, width=10, length=12,
                          features=[
                              BuildingFeature(feature_type="stairs"),
                              BuildingFeature(feature_type="room"),
                              BuildingFeature(feature_type="furniture"),
                              BuildingFeature(feature_type="roof", position="flat"),
                          ])
        builder = BlockBuilder(desc)
        s = builder.build()
        assert len(s.blocks) > 0


class TestWikipediaDepth:
    """测试 Wikipedia 深度利用相关字段。"""

    def test_bays_field_stored(self):
        from src.models.building import BuildingDescription
        desc = BuildingDescription(
            minecraft_version=MinecraftVersion.JAVA_1_20,
            building_type="gate",
            height=8, width=12, length=6,
            bays=5,
        )
        assert desc.bays == 5

    def test_columns_field_parsed(self):
        from src.generator.block_builder import BlockBuilder
        desc = _make_desc(
            features=[
                BuildingFeature(feature_type="column", count=4),
                BuildingFeature(feature_type="roof", position="flat"),
            ],
        )
        builder = BlockBuilder(desc)
        s = builder.build()
        assert len(s.blocks) > 0

    def test_roof_style_from_wikipedia(self):
        desc = _make_desc(
            roof="xieshan",
            features=[BuildingFeature(feature_type="roof", position="xieshan")],
        )
        s = BlockBuilder(desc).build()
        assert len(s.blocks) > 0

    def test_arch_curve_places_blocks(self):
        desc = _make_desc(roof="flat")
        builder = BlockBuilder(desc)
        builder._grid = [
            [[builder._idx("air") for _ in range(builder.w)] for _ in range(builder.h)]
            for _ in range(builder.l)
        ]
        builder._arch_curve(4, 4, 3, 1, 4, "stone_bricks")
        w, h, l = builder.w, builder.h, builder.l
        grid = [builder._grid[z][y][x] for z in range(l) for y in range(h) for x in range(w)]
        pal = builder._palette_list
        idx = lambda x, y, z: x + y * w + z * w * h
        # 拱顶 (x=4, y=1+4=5)
        assert pal[grid[idx(4, 5, 4)]] == "minecraft:stone_bricks"
