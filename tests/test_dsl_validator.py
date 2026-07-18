"""测试 BuildingDSL 自洽校验器、置信度评分和自动修正。"""

import pytest

from src.analysis.dsl_validator import fix, score, validate
from src.models.building import (
    BuildingDSL,
    Component,
    CurveSpec,
    EntranceSpec,
    MinecraftVersion,
    RoofSpec,
    WindowItem,
    WindowSystem,
)


# ─── 辅助工厂 ───

def _make_dsl(
    width=20, length=20, height=16,
    floor_count=2,
    components=None,
    roof=None,
    windows=None,
    entrance=None,
    curves=None,
    materials=None,
    style="modern",
    building_type="house",
    description="test building",
    wall_material="stone_bricks",
    roof_material="terracotta",
    **kwargs,
):
    return BuildingDSL(
        minecraft_version=MinecraftVersion.JAVA_1_20,
        building_type=building_type,
        style=style,
        width=width,
        length=length,
        height=height,
        floor_count=floor_count,
        floor_height=4,
        components=components or [],
        roof=roof or RoofSpec(),
        windows=windows or WindowSystem(),
        entrance=entrance or EntranceSpec(),
        curves=curves or [],
        materials=materials or [],
        wall_material=wall_material,
        roof_material=roof_material,
        description=description,
        **kwargs,
    )


# ═══════════════════════════════════════════════════════
#  validate 测试
# ═══════════════════════════════════════════════════════


class TestValidateBasic:
    def test_perfect_dsl_passes(self):
        """合理 DSL 应无错误。"""
        dsl = _make_dsl(
            components=[
                Component(name="main_body", shape="box", width=18, length=18, height=12),
            ],
        )
        assert validate(dsl) == []

    def test_dimensions_too_large(self):
        """维度超过 256 应报错。"""
        dsl = _make_dsl(width=300, length=10, height=10)
        errs = validate(dsl)
        assert any("维度过大" in e for e in errs)

    def test_zero_size_component(self):
        """零尺寸组件应报错。"""
        dsl = _make_dsl(
            components=[
                Component(name="bad", shape="box", width=0, length=0, height=0),
            ],
        )
        errs = validate(dsl)
        assert any("尺寸全为零" in e for e in errs)


class TestValidateComponentBounds:
    def test_x_overflow(self):
        dsl = _make_dsl(width=20, components=[
            Component(name="wing", shape="box", width=15, offset_x=10),
        ])
        errs = validate(dsl)
        assert any("X 方向溢出" in e for e in errs)

    def test_z_overflow(self):
        dsl = _make_dsl(length=15, components=[
            Component(name="wing", shape="box", length=20, offset_z=5),
        ])
        errs = validate(dsl)
        assert any("Z 方向溢出" in e for e in errs)

    def test_y_overflow(self):
        dsl = _make_dsl(height=10, components=[
            Component(name="tower", shape="box", width=5, length=5, height=8, offset_y=5),
        ])
        errs = validate(dsl)
        assert any("Y 方向溢出" in e for e in errs)

    def test_cylinder_overflow(self):
        """圆柱体用 radius*2 计算尺寸。"""
        dsl = _make_dsl(width=10, length=10, components=[
            Component(name="cyl", shape="cylinder", radius=6, height=8),
        ])
        errs = validate(dsl)
        assert any("X 方向溢出" in e for e in errs)
        assert any("Z 方向溢出" in e for e in errs)


class TestValidateRoof:
    def test_roof_too_tall(self):
        dsl = _make_dsl(height=10, roof=RoofSpec(height=8))
        errs = validate(dsl)
        assert any("屋顶高度" in e and "一半" in e for e in errs)

    def test_roof_reasonable(self):
        dsl = _make_dsl(height=20, roof=RoofSpec(height=5))
        assert validate(dsl) == []


class TestValidateWindows:
    def test_window_floor_exceeds(self):
        dsl = _make_dsl(
            floor_count=2,
            windows=WindowSystem(items=[
                WindowItem(floor=5, side="front"),
            ]),
        )
        errs = validate(dsl)
        assert any("超出总楼层数" in e for e in errs)

    def test_window_floor_ok(self):
        dsl = _make_dsl(
            floor_count=3,
            windows=WindowSystem(items=[
                WindowItem(floor=2, side="front"),
            ]),
        )
        assert validate(dsl) == []


class TestValidateEntrance:
    def test_entrance_too_wide(self):
        dsl = _make_dsl(width=10, entrance=EntranceSpec(width=10))
        errs = validate(dsl)
        assert any("入口宽度" in e and "≥" in e for e in errs)

    def test_entrance_too_tall(self):
        dsl = _make_dsl(height=8, entrance=EntranceSpec(height=10))
        errs = validate(dsl)
        assert any("入口高度" in e for e in errs)

    def test_entrance_reasonable(self):
        dsl = _make_dsl(width=20, height=12, entrance=EntranceSpec(width=3, height=4))
        assert validate(dsl) == []


class TestValidateCurves:
    def test_curve_center_outside(self):
        dsl = _make_dsl(
            width=20, length=20, height=16,
            curves=[
                CurveSpec(type="dome", radius=5, center_x=-3, center_y=5, center_z=10),
            ],
        )
        errs = validate(dsl)
        assert any("center_x" in e and "超出" in e for e in errs)

    def test_curve_center_ok(self):
        dsl = _make_dsl(
            width=30, length=30, height=20,
            curves=[
                CurveSpec(type="dome", radius=5, center_x=10, center_y=5, center_z=10),
            ],
        )
        assert validate(dsl) == []


# ═══════════════════════════════════════════════════════
#  score 测试
# ═══════════════════════════════════════════════════════


class TestScoreComponents:
    def test_no_components_low_score(self):
        dsl = _make_dsl()
        s, reasons = score(dsl)
        assert s < 60
        assert any("components 为空" in r for r in reasons)

    def test_one_component(self):
        dsl = _make_dsl(components=[
            Component(name="main_body", shape="box", width=10, length=10, height=8),
        ])
        s, reasons = score(dsl)
        assert any("仅 1 个" in r for r in reasons)

    def test_multiple_components_no_penalty(self):
        dsl = _make_dsl(
            wall_material="stone_bricks",
            roof_material="terracotta",
            components=[
                Component(name="main_body", shape="box", width=10, length=10, height=8),
                Component(name="tower", shape="box", width=4, length=4, height=12, offset_x=3, offset_z=3),
            ],
        )
        s, reasons = score(dsl)
        assert not any("components" in r.lower() for r in reasons)


class TestScoreMaterials:
    def test_few_materials(self):
        dsl = _make_dsl(materials=[])
        s, reasons = score(dsl)
        assert any("materials" in r for r in reasons)

    def test_enough_materials(self):
        from src.models.building import BlockMaterial
        mats = [
            BlockMaterial(name="stone_bricks", location="wall"),
            BlockMaterial(name="terracotta", location="roof"),
            BlockMaterial(name="oak_planks", location="floor"),
        ]
        dsl = _make_dsl(materials=mats)
        s, reasons = score(dsl)
        assert not any("materials" in r for r in reasons)


class TestScoreDefaultMaterials:
    def test_all_defaults(self):
        """所有部位材质都是默认值应扣分。"""
        dsl = _make_dsl(
            wall_material="stone_bricks",
            roof_material="stone_bricks",  # 默认值
            description="test",
        )
        s, reasons = score(dsl)
        assert any("默认值" in r for r in reasons)

    def test_custom_materials(self):
        dsl = _make_dsl(
            wall_material="quartz_block",
            roof_material="red_terracotta",
            description="test",
        )
        s, reasons = score(dsl)
        assert not any("默认值" in r for r in reasons)


class TestScoreComplexStyle:
    def test_gothic_no_curves(self):
        dsl = _make_dsl(
            style="gothic",
            building_type="church",
            curves=[],
        )
        s, reasons = score(dsl)
        assert any("curves" in r.lower() for r in reasons)

    def test_gothic_with_curves(self):
        dsl = _make_dsl(
            style="gothic",
            building_type="church",
            curves=[CurveSpec(type="arch")],
        )
        s, reasons = score(dsl)
        assert not any("curves" in r.lower() for r in reasons)

    def test_modern_no_curves_ok(self):
        """现代风格没有 curves 不扣分。"""
        dsl = _make_dsl(style="modern", building_type="house")
        s, reasons = score(dsl)
        assert not any("curves" in r.lower() for r in reasons)


class TestScoreEdge:
    def test_score_is_bounded(self):
        """分数不应该低于 0。"""
        dsl = _make_dsl(
            components=[Component(name="zero", shape="box")],
            style="gothic",
            building_type="church",
        )
        s, _ = score(dsl)
        assert s >= 0

    def test_reasons_count(self):
        """扣分原因应该有若干条。"""
        dsl = _make_dsl()
        s, reasons = score(dsl)
        assert len(reasons) >= 3


# ═══════════════════════════════════════════════════════
#  fix 测试
# ═══════════════════════════════════════════════════════


class TestFixZeroComponents:
    def test_removes_zero_sized(self):
        dsl = _make_dsl(components=[
            Component(name="bad", shape="box", width=0, length=0, height=0),
            Component(name="good", shape="box", width=10, length=10, height=8),
        ])
        msgs = fix(dsl)
        assert len(dsl.components) == 1
        assert dsl.components[0].name == "good"
        assert any("删除" in m for m in msgs)

    def test_keeps_valid(self):
        dsl = _make_dsl(components=[
            Component(name="good", shape="box", width=10, length=10, height=8),
        ])
        msgs = fix(dsl)
        assert len(dsl.components) == 1
        assert not any("删除" in m for m in msgs)


class TestFixBounds:
    def test_clamp_x_overflow(self):
        dsl = _make_dsl(width=20, components=[
            Component(name="wing", shape="box", width=8, offset_x=15),
        ])
        fix(dsl)
        assert dsl.components[0].offset_x + dsl.components[0].width <= 20

    def test_clamp_z_overflow(self):
        dsl = _make_dsl(length=15, components=[
            Component(name="wing", shape="box", width=5, length=8, offset_z=10),
        ])
        fix(dsl)
        assert dsl.components[0].offset_z + dsl.components[0].length <= 15

    def test_clamp_y_overflow(self):
        dsl = _make_dsl(height=10, components=[
            Component(name="tower", shape="box", width=4, length=4, height=8, offset_y=5),
        ])
        fix(dsl)
        assert dsl.components[0].offset_y + dsl.components[0].height <= 10


class TestFixRoof:
    def test_clamp_roof_height(self):
        dsl = _make_dsl(height=10, roof=RoofSpec(height=8))
        fix(dsl)
        assert dsl.roof.height <= 5


class TestFixWindows:
    def test_clamp_window_floor(self):
        dsl = _make_dsl(
            floor_count=2,
            windows=WindowSystem(items=[
                WindowItem(floor=5, side="front"),
            ]),
        )
        fix(dsl)
        assert dsl.windows.items[0].floor == 2


class TestFixEntrance:
    def test_clamp_entrance_width(self):
        dsl = _make_dsl(width=10, entrance=EntranceSpec(width=10))
        fix(dsl)
        assert dsl.entrance.width < dsl.width

    def test_clamp_entrance_height(self):
        dsl = _make_dsl(height=6, entrance=EntranceSpec(height=10))
        fix(dsl)
        assert dsl.entrance.height < dsl.height


class TestFixMaterials:
    def test_invalid_material_fallback(self):
        """不在方块表中的材质应回退。"""
        dsl = _make_dsl(wall_material="nonexistent_block_xyz")
        fix(dsl)
        # wall_material 默认就是 stone_bricks，不在表中的值应被替换
        assert dsl.wall_material == "stone_bricks"

    def test_valid_material_kept(self):
        dsl = _make_dsl(wall_material="quartz_block")
        fix(dsl)
        assert dsl.wall_material == "quartz_block"


class TestFixIntegration:
    def test_fix_then_validate_clean(self):
        """fix 之后 validate 应该通过（或至少没有硬性错误）。"""
        dsl = _make_dsl(
            width=20, height=10, floor_count=2,
            components=[
                Component(name="zero", shape="box", width=0, length=0, height=0),
                Component(name="big", shape="box", width=50, length=50, height=50, offset_x=100, offset_y=100, offset_z=100),
            ],
            roof=RoofSpec(height=20),
            entrance=EntranceSpec(width=99, height=99),
            windows=WindowSystem(items=[
                WindowItem(floor=10, side="front"),
            ]),
        )
        fix(dsl)
        errs = validate(dsl)
        # 所有可修复的错误应已清除
        assert len(errs) == 0, f"fix 后仍有错误: {errs}"

    def test_fix_returns_messages(self):
        dsl = _make_dsl(
            width=10, height=8,
            components=[
                Component(name="zero", shape="box"),
                Component(name="overflow", shape="box", width=50, height=50, offset_x=50, offset_y=50),
            ],
            roof=RoofSpec(height=20),
        )
        msgs = fix(dsl)
        assert len(msgs) >= 3  # 至少应返回多条修正信息


class TestFixCurves:
    def test_clamp_curve_center_negative(self):
        dsl = _make_dsl(
            width=20, length=20, height=16,
            curves=[
                CurveSpec(type="dome", radius=5, center_x=-3, center_y=5, center_z=10),
            ],
        )
        fix(dsl)
        assert dsl.curves[0].center_x == 0

    def test_clamp_curve_center_outside(self):
        dsl = _make_dsl(
            width=20, length=20, height=16,
            curves=[
                CurveSpec(type="dome", radius=5, center_x=20, center_y=16, center_z=20),
            ],
        )
        fix(dsl)
        assert dsl.curves[0].center_x == 19
        assert dsl.curves[0].center_y == 15
        assert dsl.curves[0].center_z == 19

    def test_curve_no_fix_when_valid(self):
        dsl = _make_dsl(
            width=30, length=30, height=20,
            curves=[
                CurveSpec(type="arch", radius=5, center_x=10, center_y=5, center_z=10),
            ],
        )
        msgs = fix(dsl)
        assert not any("曲线" in m for m in msgs)


class TestFixStairs:
    def test_stair_count_clamped(self):
        """台阶数不应超过门高。"""
        dsl = _make_dsl(
            entrance=EntranceSpec(width=3, height=4, has_stairs=True, stair_count=10),
        )
        fix(dsl)
        assert dsl.entrance.stair_count <= dsl.entrance.height
        assert dsl.entrance.stair_count >= 1

    def test_stair_count_not_clamped_when_ok(self):
        dsl = _make_dsl(
            entrance=EntranceSpec(width=3, height=6, has_stairs=True, stair_count=2),
        )
        msgs = fix(dsl)
        assert not any("台阶" in m for m in msgs)


class TestFixColumns:
    def test_column_count_zero_with_has_columns(self):
        """has_columns=True 但 count=0 时应设为 2。"""
        dsl = _make_dsl(
            entrance=EntranceSpec(width=3, height=4, has_columns=True, column_count=0),
        )
        fix(dsl)
        assert dsl.entrance.column_count == 2

    def test_columns_not_touched_when_ok(self):
        dsl = _make_dsl(
            entrance=EntranceSpec(width=3, height=4, has_columns=True, column_count=4),
        )
        msgs = fix(dsl)
        assert not any("柱" in m for m in msgs)


class TestFixWallPillars:
    def test_pillar_count_clamped(self):
        """柱数不应超过宽度可容纳的最大值。"""
        from src.models.building import WallSpec, PillarSpec
        dsl = _make_dsl(
            width=10,
            walls=[
                WallSpec(type="pillar", pillars=PillarSpec(count=20, spacing=3)),
            ],
        )
        fix(dsl)
        assert dsl.walls[0].pillars.count <= 10 // 3


class TestFixWindowWidth:
    def test_window_x_plus_width_clamped(self):
        """x + width > 1.0 时应修正。"""
        dsl = _make_dsl(
            windows=WindowSystem(items=[
                WindowItem(x=0.8, width=0.5, side="front"),
            ]),
        )
        fix(dsl)
        assert dsl.windows.items[0].x + dsl.windows.items[0].width <= 1.001


class TestValidateStairs:
    def test_stair_count_exceeds_height(self):
        dsl = _make_dsl(
            entrance=EntranceSpec(width=3, height=4, has_stairs=True, stair_count=10),
        )
        errs = validate(dsl)
        assert any("台阶" in e for e in errs)


class TestValidateColumns:
    def test_columns_true_count_zero(self):
        dsl = _make_dsl(
            entrance=EntranceSpec(width=3, height=4, has_columns=True, column_count=0),
        )
        errs = validate(dsl)
        assert any("column_count=0" in e for e in errs)


class TestValidateWindowWidth:
    def test_x_plus_width_over_1(self):
        dsl = _make_dsl(
            windows=WindowSystem(items=[
                WindowItem(x=0.8, width=0.5, side="front"),
            ]),
        )
        errs = validate(dsl)
        assert any("> 1.0" in e for e in errs)


class TestValidateWallPillars:
    def test_pillar_count_exceeds_width(self):
        from src.models.building import WallSpec, PillarSpec
        dsl = _make_dsl(
            width=10,
            walls=[
                WallSpec(type="pillar", pillars=PillarSpec(count=20, spacing=3)),
            ],
        )
        errs = validate(dsl)
        assert any("柱数" in e for e in errs)


class TestFixIntegrationExtended:
    def test_fix_all_new_constraints(self):
        """fix 后所有新增约束也应通过 validate。"""
        from src.models.building import WallSpec, PillarSpec
        dsl = _make_dsl(
            width=20, height=10, floor_count=2,
            components=[
                Component(name="zero", shape="box"),
            ],
            roof=RoofSpec(height=8),
            entrance=EntranceSpec(
                width=30, height=30,
                has_stairs=True, stair_count=20,
                has_columns=True, column_count=0,
            ),
            windows=WindowSystem(items=[
                WindowItem(floor=5, side="front", x=0.8, width=0.5),
            ]),
            curves=[
                CurveSpec(type="dome", radius=5, center_x=-10, center_y=-5, center_z=999),
            ],
            walls=[
                WallSpec(type="pillar", pillars=PillarSpec(count=50, spacing=2)),
            ],
        )
        fix(dsl)
        errs = validate(dsl)
        assert len(errs) == 0, f"fix 后仍有错误: {errs}"