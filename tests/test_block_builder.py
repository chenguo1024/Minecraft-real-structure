"""测试 V2 方块生成器（按 BuildingDSL component 级渲染）。

覆盖：
  - 基础 build 输出尺寸
  - component 按 shape 渲染（box/cylinder/sphere/cone/prism/arch）
  - 屋顶系统（flat/gable/hip/pyramid/dome/mansard/barrel/spire/chinese_roof）
  - 墙体系统（pillar/buttress/arcade）
  - 窗户系统（square/arch/pointed_arch/circle + 重复排列）
  - 入口系统（simple/arch/portal/porch/grand_stair/column_entrance）
  - 曲线系统（cylinder/dome/arch/flying_eaves）
  - 部位材质生效
  - 位置标签解析
"""
from src.generator.block_builder import BlockBuilder, BlockStructure
from src.models.building import (
    BlockMaterial,
    BuildingDSL,
    Component,
    CurveSpec,
    EntranceSpec,
    MinecraftVersion,
    PillarSpec,
    RoofSpec,
    WallSpec,
    WindowItem,
    WindowSystem,
)


def _make_dsl(**overrides) -> BuildingDSL:
    """构造测试用 BuildingDSL，默认最小主体 + 禁用默认入口（避免覆盖 front 面）。"""
    params = dict(
        building_type="house",
        width=10,
        length=10,
        height=8,
        entrance=EntranceSpec(type="simple", width=0, height=0),
    )
    params.update(overrides)
    return BuildingDSL(**params)


def _idx(s: BlockStructure, x: int, y: int, z: int) -> int:
    """从 BlockStructure 取 (x,y,z) 的 palette 索引。"""
    return s.blocks[x + y * s.size_x + z * s.size_x * s.size_y]


class TestBuildOutput:
    def test_output_has_correct_size(self):
        dsl = _make_dsl(width=6, length=10, height=8)
        builder = BlockBuilder(dsl)
        s = builder.build()
        assert s.size_x == 6
        assert s.size_y == 8
        assert s.size_z == 10
        assert len(s.blocks) == 6 * 8 * 10

    def test_palette_has_air(self):
        dsl = _make_dsl()
        s = BlockBuilder(dsl).build()
        assert "minecraft:air" in s.palette

    def test_empty_components_falls_back_to_main_body(self):
        """无 components 时 fallback 画一个主体 box。"""
        dsl = _make_dsl(width=4, length=4, height=4)
        s = BlockBuilder(dsl).build()
        # 主体 box 实心填充，至少有非空气方块
        air_idx = s.palette.index("minecraft:air")
        non_air = sum(1 for b in s.blocks if b != air_idx)
        assert non_air > 0


class TestComponentRendering:
    def test_box_component(self):
        dsl = _make_dsl(
            width=8, length=8, height=6,
            components=[
                Component(name="main_body", shape="box", width=6, length=6, height=4,
                          material="stone_bricks"),
            ],
        )
        s = BlockBuilder(dsl).build()
        stone_idx = s.palette.index("minecraft:stone_bricks")
        # box 中心应有 stone_bricks
        assert _idx(s, 4, 2, 4) == stone_idx

    def test_cylinder_component(self):
        dsl = _make_dsl(
            width=12, length=12, height=10,
            components=[
                Component(name="tower", shape="cylinder", radius=4, height=8,
                          position="center", material="stone_bricks"),
            ],
        )
        s = BlockBuilder(dsl).build()
        # 圆柱中心点应有
        assert _idx(s, 6, 4, 6) != s.palette.index("minecraft:air")

    def test_sphere_component(self):
        dsl = _make_dsl(
            width=10, length=10, height=10,
            components=[
                Component(name="dome", shape="sphere", radius=3, position="top",
                          material="white_concrete"),
            ],
        )
        s = BlockBuilder(dsl).build()
        # 球心区域应有方块
        air_idx = s.palette.index("minecraft:air")
        assert _idx(s, 5, 3, 5) != air_idx

    def test_cone_component(self):
        dsl = _make_dsl(
            width=10, length=10, height=10,
            components=[
                Component(name="spire", shape="cone", radius=3, height=8,
                          position="top", material="black_concrete"),
            ],
        )
        s = BlockBuilder(dsl).build()
        # 圆锥底面中心应有
        assert _idx(s, 5, 0, 5) != s.palette.index("minecraft:air")

    def test_component_with_offset(self):
        dsl = _make_dsl(
            width=12, length=12, height=6,
            components=[
                Component(name="wing", shape="box", width=4, length=4, height=4,
                          position="front_left_corner",
                          offset_x=8, offset_z=8, material="oak_planks"),
            ],
        )
        s = BlockBuilder(dsl).build()
        oak_idx = s.palette.index("minecraft:oak_planks")
        # front_left_corner → (0,0), +offset(8,8) → box 在 8~11
        assert _idx(s, 9, 1, 9) == oak_idx

    def test_position_front(self):
        dsl = _make_dsl(
            width=10, length=10, height=6,
            components=[
                Component(name="porch", shape="box", width=4, length=2, height=3,
                          position="front", material="oak_planks"),
            ],
        )
        s = BlockBuilder(dsl).build()
        # front → z 偏移 0，x 居中 (10-4)/2=3, box x=3~6, z=0~1
        oak_idx = s.palette.index("minecraft:oak_planks")
        assert _idx(s, 4, 1, 0) == oak_idx


class TestRoofRendering:
    def test_flat_roof(self):
        dsl = _make_dsl(width=6, length=6, height=4, roof=RoofSpec(type="flat"))
        s = BlockBuilder(dsl).build()
        # flat roof 在 y=h-1=3 整层
        assert _idx(s, 2, 3, 2) != s.palette.index("minecraft:air")

    def test_gable_roof(self):
        dsl = _make_dsl(width=6, length=6, height=6, roof=RoofSpec(type="gable", height=3))
        s = BlockBuilder(dsl).build()
        # gable 屋顶应有非空气方块在顶层
        assert _idx(s, 2, 5, 3) != s.palette.index("minecraft:air")

    def test_pyramid_roof(self):
        dsl = _make_dsl(width=8, length=8, height=6, roof=RoofSpec(type="pyramid", height=3))
        s = BlockBuilder(dsl).build()
        # 金字塔顶中心应有
        assert _idx(s, 4, 5, 4) != s.palette.index("minecraft:air")

    def test_dome_roof(self):
        dsl = _make_dsl(width=10, length=10, height=8, roof=RoofSpec(type="dome", height=4))
        s = BlockBuilder(dsl).build()
        # 穹顶中心应有
        assert _idx(s, 5, 7, 5) != s.palette.index("minecraft:air")

    def test_spire_roof(self):
        dsl = _make_dsl(width=8, length=8, height=10, roof=RoofSpec(type="spire", height=5))
        s = BlockBuilder(dsl).build()
        # 尖塔底面中心应有
        assert _idx(s, 4, 7, 4) != s.palette.index("minecraft:air")

    def test_chinese_roof_with_eaves(self):
        dsl = _make_dsl(
            width=10, length=10, height=8,
            roof=RoofSpec(type="chinese_roof", height=3, has_flying_eaves=True,
                          eaves_curvature=0.8, material="red_terracotta"),
        )
        s = BlockBuilder(dsl).build()
        # 不崩即可
        assert len(s.blocks) == 10 * 10 * 8

    def test_mansard_roof(self):
        dsl = _make_dsl(width=8, length=8, height=8, roof=RoofSpec(type="mansard", height=4))
        s = BlockBuilder(dsl).build()
        assert len(s.blocks) == 8 * 8 * 8

    def test_barrel_roof(self):
        dsl = _make_dsl(width=8, length=8, height=8, roof=RoofSpec(type="barrel", height=3))
        s = BlockBuilder(dsl).build()
        assert len(s.blocks) == 8 * 8 * 8

    def test_roof_material_overrides_global(self):
        dsl = _make_dsl(
            width=6, length=6, height=4,
            roof=RoofSpec(type="flat", material="black_concrete"),
        )
        s = BlockBuilder(dsl).build()
        bc_idx = s.palette.index("minecraft:black_concrete")
        assert _idx(s, 2, 3, 2) == bc_idx


class TestWallRendering:
    def test_pillar_wall(self):
        dsl = _make_dsl(
            width=12, length=8, height=8,
            walls=[WallSpec(type="pillar", material="stone_bricks",
                            pillars=PillarSpec(count=4, spacing=3, width=1,
                                               material="chiseled_stone_bricks"))],
        )
        s = BlockBuilder(dsl).build()
        chisel_idx = s.palette.index("minecraft:chiseled_stone_bricks")
        # 4 根柱子沿正面均匀分布，第 1 根在 x=1
        assert _idx(s, 1, 3, 0) == chisel_idx

    def test_arcade_wall(self):
        dsl = _make_dsl(
            width=12, length=8, height=8,
            walls=[WallSpec(type="arcade", material="stone_bricks",
                            pillars=PillarSpec(count=4, spacing=3,
                                               material="quartz_pillar"))],
        )
        s = BlockBuilder(dsl).build()
        # 柱子 + 拱，不崩即可
        assert len(s.blocks) == 12 * 8 * 8


class TestWindowRendering:
    def test_single_window(self):
        dsl = _make_dsl(
            width=10, length=8, height=8,
            windows=WindowSystem(items=[
                WindowItem(shape="square", floor=1, side="front",
                           x=0.5, width=0.2, height=2, y_offset=1,
                           glass_material="glass", frame_material="oak_planks"),
            ]),
        )
        s = BlockBuilder(dsl).build()
        glass_idx = s.palette.index("minecraft:glass")
        # 窗中心 x=int(0.5*9)=4, y=1+1=2, z=0
        assert _idx(s, 4, 2, 0) == glass_idx

    def test_window_frame(self):
        dsl = _make_dsl(
            width=10, length=8, height=8,
            windows=WindowSystem(items=[
                WindowItem(shape="square", floor=1, side="front",
                           x=0.5, width=0.2, height=2, y_offset=1,
                           frame_material="dark_oak_planks"),
            ]),
        )
        s = BlockBuilder(dsl).build()
        oak_idx = s.palette.index("minecraft:dark_oak_planks")
        # 窗框在窗左侧 x=3, y=2, z=0
        assert _idx(s, 3, 2, 0) == oak_idx

    def test_arch_window(self):
        dsl = _make_dsl(
            width=10, length=8, height=10,
            windows=WindowSystem(items=[
                WindowItem(shape="arch", floor=1, side="front",
                           x=0.5, width=0.3, height=3, y_offset=1,
                           frame_material="quartz_block"),
            ]),
        )
        s = BlockBuilder(dsl).build()
        # 拱顶应有 quartz_block
        qb_idx = s.palette.index("minecraft:quartz_block")
        found = False
        for y in range(4, 8):
            for x in range(2, 7):
                if _idx(s, x, y, 0) == qb_idx:
                    found = True
                    break
            if found:
                break
        assert found, "arch 窗顶应有 quartz_block"

    def test_window_on_second_floor(self):
        dsl = _make_dsl(
            width=10, length=8, height=12, floor_count=2, floor_height=5,
            windows=WindowSystem(items=[
                WindowItem(shape="square", floor=2, side="front",
                           x=0.5, width=0.2, height=2, y_offset=1,
                           glass_material="glass"),
            ]),
        )
        s = BlockBuilder(dsl).build()
        glass_idx = s.palette.index("minecraft:glass")
        # floor=2 → y_offset = 1 + (2-1)*5 = 6, 窗中心 y=6+1=7
        assert _idx(s, 4, 7, 0) == glass_idx


class TestEntranceRendering:
    def test_simple_entrance(self):
        dsl = _make_dsl(
            width=10, length=8, height=8,
            entrance=EntranceSpec(type="simple", position="center", side="front",
                                  width=2, height=3),
        )
        s = BlockBuilder(dsl).build()
        air_idx = s.palette.index("minecraft:air")
        # 门洞中心 x=5, y=1, z=0 应为空气
        assert _idx(s, 5, 1, 0) == air_idx

    def test_arch_entrance(self):
        dsl = _make_dsl(
            width=10, length=8, height=8,
            entrance=EntranceSpec(type="arch", position="center", side="front",
                                  width=4, height=3, curvature=1.0,
                                  frame_material="quartz_block"),
        )
        s = BlockBuilder(dsl).build()
        qb_idx = s.palette.index("minecraft:quartz_block")
        # 拱顶应有 quartz_block
        found = False
        for y in range(3, 7):
            for x in range(3, 7):
                if _idx(s, x, y, 0) == qb_idx:
                    found = True
                    break
            if found:
                break
        assert found, "arch 门顶应有 quartz_block"

    def test_entrance_with_stairs(self):
        dsl = _make_dsl(
            width=10, length=8, height=8,
            entrance=EntranceSpec(type="grand_stair", position="center", side="front",
                                  width=3, height=3, has_stairs=True, stair_count=3),
        )
        s = BlockBuilder(dsl).build()
        # 不崩即可
        assert len(s.blocks) == 10 * 8 * 8

    def test_entrance_with_columns(self):
        dsl = _make_dsl(
            width=10, length=8, height=8,
            entrance=EntranceSpec(type="porch", position="center", side="front",
                                  width=4, height=3, has_columns=True, column_count=2,
                                  has_roof_cover=True),
        )
        s = BlockBuilder(dsl).build()
        assert len(s.blocks) == 10 * 8 * 8

    def test_entrance_frame(self):
        dsl = _make_dsl(
            width=10, length=8, height=8,
            entrance=EntranceSpec(type="simple", position="center", side="front",
                                  width=2, height=3, frame_material="quartz_block"),
        )
        s = BlockBuilder(dsl).build()
        qb_idx = s.palette.index("minecraft:quartz_block")
        # 门框左侧 ex1-1=3, y=1, z=0 (ex_center=4, ex1=3, ex2=5)
        assert _idx(s, 2, 1, 0) == qb_idx


class TestCurveRendering:
    def test_cylinder_curve(self):
        dsl = _make_dsl(
            width=10, length=10, height=10,
            curves=[CurveSpec(type="cylinder", radius=3, height=8,
                              center_x=5, center_y=0, center_z=5,
                              material="stone_bricks")],
        )
        s = BlockBuilder(dsl).build()
        # 圆柱中心应有
        assert _idx(s, 5, 4, 5) != s.palette.index("minecraft:air")

    def test_dome_curve(self):
        dsl = _make_dsl(
            width=10, length=10, height=10,
            curves=[CurveSpec(type="dome", radius=4, height=4,
                              center_x=5, center_y=6, center_z=5,
                              material="white_concrete")],
        )
        s = BlockBuilder(dsl).build()
        # 穹顶中心应有
        assert _idx(s, 5, 7, 5) != s.palette.index("minecraft:air")

    def test_arch_curve(self):
        dsl = _make_dsl(
            width=10, length=10, height=10,
            curves=[CurveSpec(type="arch", width=4, height=4, curve_radius=2,
                              center_x=5, center_z=0, arch_type="semicircle",
                              material="quartz_block")],
        )
        s = BlockBuilder(dsl).build()
        # 拱应有方块
        assert len(s.blocks) == 10 * 10 * 10

    def test_flying_eaves_curve(self):
        dsl = _make_dsl(
            width=10, length=10, height=8,
            roof=RoofSpec(type="chinese_roof", height=3),
            curves=[CurveSpec(type="flying_eaves", direction="up", curvature=0.8,
                              material="red_terracotta")],
        )
        s = BlockBuilder(dsl).build()
        # 飞檐不崩即可
        assert len(s.blocks) == 10 * 10 * 8


class TestMaterialResolution:
    def test_global_materials_used(self):
        dsl = _make_dsl(
            width=6, length=6, height=4,
            wall_material="white_concrete",
            components=[Component(name="main", shape="box", width=4, length=4, height=3,
                                  position="center")],
        )
        s = BlockBuilder(dsl).build()
        wc_idx = s.palette.index("minecraft:white_concrete")
        assert _idx(s, 3, 1, 3) == wc_idx

    def test_component_material_overrides_global(self):
        dsl = _make_dsl(
            width=6, length=6, height=4,
            wall_material="white_concrete",
            components=[Component(name="main", shape="box", width=4, length=4, height=3,
                                  position="center", material="red_concrete")],
        )
        s = BlockBuilder(dsl).build()
        rc_idx = s.palette.index("minecraft:red_concrete")
        assert _idx(s, 3, 1, 3) == rc_idx

    def test_window_glass_material(self):
        dsl = _make_dsl(
            width=10, length=8, height=8,
            window_glass_material="blue_stained_glass",
            windows=WindowSystem(items=[
                WindowItem(shape="square", floor=1, side="front",
                           x=0.5, width=0.2, height=2, y_offset=1),
            ]),
        )
        s = BlockBuilder(dsl).build()
        bsg_idx = s.palette.index("minecraft:blue_stained_glass")
        assert _idx(s, 4, 2, 0) == bsg_idx


class TestDetailScale:
    def test_detail_scale_doubles_size(self):
        dsl = _make_dsl(width=5, length=5, height=5, detail_scale=2)
        s = BlockBuilder(dsl).build()
        # detail_scale=2 → 5*2=10
        assert s.size_x == 10
        assert s.size_y == 10
        assert s.size_z == 10
