"""测试 V2 Building DSL 数据模型（Pydantic 校验、枚举、序列化、component 几何）。"""

import pytest
from pydantic import ValidationError

from src.models.building import (
    BlockMaterial,
    BuildingDSL,
    Component,
    CurveSpec,
    EntranceSpec,
    GeometryRef,
    MinecraftVersion,
    PillarSpec,
    RoofSpec,
    WallSpec,
    WindowItem,
    WindowSystem,
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
        assert m.percentage == 100.0
        assert m.location == "wall"

    def test_full(self):
        m = BlockMaterial(name="oak_planks", color="brown", percentage=50.0, location="floor")
        assert m.percentage == 50.0
        assert m.location == "floor"

    def test_percentage_bounds(self):
        with pytest.raises(ValidationError):
            BlockMaterial(name="stone", percentage=150.0)
        with pytest.raises(ValidationError):
            BlockMaterial(name="stone", percentage=-10.0)


class TestGeometryRef:
    def test_default_box(self):
        g = GeometryRef(type="box")
        assert g.type == "box"
        assert g.width == 0
        assert g.half_or_full == "full"

    def test_cylinder(self):
        g = GeometryRef(type="cylinder", radius=5, height=20)
        assert g.radius == 5
        assert g.height == 20

    def test_sphere_half(self):
        g = GeometryRef(type="sphere", radius=8, half_or_full="half")
        assert g.half_or_full == "half"


class TestComponent:
    def test_box_component(self):
        c = Component(name="main_body", shape="box", width=10, length=8, height=12)
        assert c.name == "main_body"
        assert c.shape == "box"
        assert c.position == "center"
        assert c.rotation_deg == 0

    def test_cylinder_tower(self):
        c = Component(
            name="right_tower",
            shape="cylinder",
            radius=5,
            height=25,
            position="front_right_corner",
            material="stone_bricks",
        )
        assert c.radius == 5
        assert c.position == "front_right_corner"

    def test_offset_defaults(self):
        c = Component(name="side_wing", shape="box")
        assert c.offset_x == 0
        assert c.offset_y == 0
        assert c.offset_z == 0

    def test_rotation_bounds(self):
        with pytest.raises(ValidationError):
            Component(name="x", rotation_deg=400)


class TestRoofSpec:
    def test_default_flat(self):
        r = RoofSpec()
        assert r.type == "flat"
        assert r.layer_count == 1

    def test_chinese_roof_with_eaves(self):
        r = RoofSpec(
            type="chinese_roof",
            height=6,
            overhang=3,
            has_flying_eaves=True,
            eaves_curvature=0.7,
        )
        assert r.has_flying_eaves is True
        assert r.eaves_curvature == 0.7

    def test_gothic_spire(self):
        r = RoofSpec(type="spire", spire_height=15, spire_angle=30)
        assert r.spire_height == 15

    def test_eaves_curvature_bounds(self):
        with pytest.raises(ValidationError):
            RoofSpec(eaves_curvature=1.5)


class TestPillarSpec:
    def test_defaults(self):
        p = PillarSpec()
        assert p.count == 0
        assert p.spacing == 3
        assert p.width == 1

    def test_classical_colonnade(self):
        p = PillarSpec(count=8, spacing=3, width=1, protrusion=1, material="quartz_pillar")
        assert p.count == 8
        assert p.material == "quartz_pillar"


class TestWallSpec:
    def test_plain_wall(self):
        w = WallSpec(type="plain_wall", thickness=1, material="stone_bricks")
        assert w.type == "plain_wall"
        assert w.thickness == 1

    def test_pillar_wall(self):
        w = WallSpec(
            type="pillar",
            thickness=2,
            material="stone_bricks",
            pillars=PillarSpec(count=6, spacing=3, material="chiseled_stone_bricks"),
        )
        assert w.pillars.count == 6

    def test_default_pillars_factory(self):
        w = WallSpec()
        assert isinstance(w.pillars, PillarSpec)
        assert w.pillars.count == 0


class TestWindowItem:
    def test_square_window(self):
        w = WindowItem(shape="square", floor=2, side="front", x=0.5, width=0.2, height=2)
        assert w.shape == "square"
        assert w.floor == 2

    def test_pointed_arch_window(self):
        w = WindowItem(shape="pointed_arch", floor=1, side="front", height=4)
        assert w.shape == "pointed_arch"

    def test_x_bounds(self):
        with pytest.raises(ValidationError):
            WindowItem(x=1.5)
        with pytest.raises(ValidationError):
            WindowItem(x=-0.1)


class TestWindowSystem:
    def test_default(self):
        ws = WindowSystem()
        assert ws.arrangement == "symmetry"
        assert ws.items == []

    def test_with_items(self):
        ws = WindowSystem(
            arrangement="grid",
            items=[
                WindowItem(shape="arch", floor=1),
                WindowItem(shape="arch", floor=2),
            ],
        )
        assert len(ws.items) == 2


class TestEntranceSpec:
    def test_simple(self):
        e = EntranceSpec(type="simple", width=2, height=3)
        assert e.type == "simple"
        assert e.position == "center"

    def test_grand_stair(self):
        e = EntranceSpec(
            type="grand_stair",
            has_stairs=True,
            stair_count=8,
            has_columns=True,
            column_count=4,
            has_roof_cover=True,
        )
        assert e.has_stairs is True
        assert e.stair_count == 8

    def test_arch_curvature(self):
        e = EntranceSpec(type="arch", curvature=1.0)
        assert e.curvature == 1.0

    def test_curvature_bounds(self):
        with pytest.raises(ValidationError):
            EntranceSpec(curvature=2.0)


class TestCurveSpec:
    def test_cylinder(self):
        c = CurveSpec(type="cylinder", radius=5, height=20, center_x=10, center_z=10)
        assert c.radius == 5

    def test_dome(self):
        c = CurveSpec(type="dome", radius=8, height=8, center_x=20, center_y=15, center_z=20)
        assert c.type == "dome"

    def test_arch(self):
        c = CurveSpec(type="arch", width=4, height=3, curve_radius=2, arch_type="semicircle")
        assert c.arch_type == "semicircle"

    def test_flying_eaves(self):
        c = CurveSpec(
            type="flying_eaves",
            direction="up",
            curvature=0.8,
            material="red_terracotta",
        )
        assert c.direction == "up"
        assert c.curvature == 0.8

    def test_curvature_bounds(self):
        with pytest.raises(ValidationError):
            CurveSpec(curvature=1.5)


class TestBuildingDSL:
    def test_minimal_valid(self):
        d = BuildingDSL(building_type="house", width=6, length=8, height=5)
        assert d.building_type == "house"
        assert d.style == "modern"
        assert d.shape == "rectangle"
        assert d.materials == []
        assert d.components == []
        assert d.curves == []

    def test_default_version(self):
        d = BuildingDSL(building_type="tower", width=5, length=5, height=20)
        assert d.minecraft_version == MinecraftVersion.JAVA_1_20

    def test_height_bounds(self):
        with pytest.raises(ValidationError):
            BuildingDSL(building_type="x", width=1, length=1, height=0)
        with pytest.raises(ValidationError):
            BuildingDSL(building_type="x", width=1, length=1, height=2000)

    def test_full_dsl(self):
        d = BuildingDSL(
            building_name="天安门",
            building_type="gate",
            style="chinese_traditional",
            location="Beijing, China",
            width=60,
            length=32,
            height=20,
            floor_count=2,
            floor_height=5,
            wall_thickness=2,
            shape="rectangle",
            geometry=GeometryRef(type="box", width=60, length=32, height=20),
            components=[
                Component(name="main_body", shape="box", width=60, length=32, height=12, material="red_concrete"),
                Component(name="roof", shape="prism", width=60, length=32, height=8, position="top", material="red_terracotta"),
            ],
            roof=RoofSpec(type="chinese_roof", height=8, overhang=3, has_flying_eaves=True, eaves_curvature=0.6, material="red_terracotta"),
            walls=[
                WallSpec(type="pillar", thickness=2, material="red_concrete",
                         pillars=PillarSpec(count=12, spacing=5, material="chiseled_stone_bricks")),
            ],
            windows=WindowSystem(
                arrangement="symmetry",
                items=[WindowItem(shape="arch", floor=2, side="front", x=0.5, width=0.2, height=3)],
            ),
            entrance=EntranceSpec(type="portal", position="center", width=6, height=5, curvature=1.0, door_material="dark_oak_door"),
            curves=[
                CurveSpec(type="flying_eaves", direction="up", curvature=0.6, material="red_terracotta"),
            ],
            materials=[
                BlockMaterial(name="red_concrete", color="red", percentage=50, location="wall"),
                BlockMaterial(name="red_terracotta", color="red", percentage=30, location="roof"),
                BlockMaterial(name="chiseled_stone_bricks", color="gray", percentage=10, location="pillar"),
            ],
            description="天安门城台+重檐歇山顶+飞檐翘角",
            keywords=["天安门", "Tiananmen", "Beijing gate tower"],
        )
        assert d.building_name == "天安门"
        assert len(d.components) == 2
        assert d.roof.has_flying_eaves is True
        assert len(d.materials) == 3
        assert d.keywords == ["天安门", "Tiananmen", "Beijing gate tower"]

    def test_serialize_roundtrip(self):
        d = BuildingDSL(
            building_type="villa", width=10, length=12, height=8,
            materials=[BlockMaterial(name="stone_bricks", percentage=60, location="wall")],
            components=[Component(name="main_body", shape="box", width=10, length=12, height=8)],
        )
        data = d.model_dump()
        restored = BuildingDSL(**data)
        assert restored.building_type == "villa"
        assert len(restored.materials) == 1
        assert restored.materials[0].name == "stone_bricks"
        assert len(restored.components) == 1

    def test_json_roundtrip(self):
        d = BuildingDSL(building_type="pagoda", width=8, length=8, height=14)
        json_str = d.model_dump_json()
        restored = BuildingDSL.model_validate_json(json_str)
        assert restored.building_type == "pagoda"
        assert restored.width == 8

    def test_global_material_defaults(self):
        d = BuildingDSL(building_type="house", width=5, length=5, height=5)
        assert d.platform_material == "stone_bricks"
        assert d.window_glass_material == "glass"
        assert d.door_material == "dark_oak_door"
        assert d.wall_material == "stone_bricks"

    def test_keywords_default_empty(self):
        d = BuildingDSL(building_type="x", width=1, length=1, height=1)
        assert d.keywords == []
