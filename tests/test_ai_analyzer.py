"""V2 AI 分析器单元测试（不调真实 API）。

验证：
  1. _coerce_material / _coerce_int / _coerce_float 容错归一化
  2. _parse_building_dsl 解析器对各种 AI 脏输入的容错
  3. 各子解析器（components/roof/walls/windows/entrance/curves/materials）
"""
import pytest

from src.analysis.ai_analyzer import (
    _coerce_float,
    _coerce_int,
    _coerce_material,
    _parse_building_dsl,
    _parse_components,
    _parse_entrance,
    _parse_curves,
    _parse_materials,
    _parse_roof,
    _parse_walls,
    _parse_windows,
    _try_repair_json,
)
from src.models.building import (
    BuildingDSL,
    Component,
    CurveSpec,
    EntranceSpec,
    MinecraftVersion,
    RoofSpec,
    WallSpec,
    WindowSystem,
)


class TestCoerceMaterial:
    def test_str_passthrough(self):
        assert _coerce_material("stone_bricks") == "stone_bricks"

    def test_dict_takes_name(self):
        # AI 实际返回过的脏输入
        assert _coerce_material({"name": "red_terracotta", "color": "red"}) == "red_terracotta"

    def test_dict_missing_name(self):
        assert _coerce_material({"color": "red"}) == ""

    def test_empty_str(self):
        assert _coerce_material("") == ""

    def test_none(self):
        assert _coerce_material(None) == ""

    def test_other_type(self):
        assert _coerce_material(123) == ""


class TestCoerceInt:
    def test_int_passthrough(self):
        assert _coerce_int(5) == 5

    def test_str_to_int(self):
        assert _coerce_int("5") == 5

    def test_float_str_to_int(self):
        assert _coerce_int("5.7") == 5

    def test_float_to_int(self):
        assert _coerce_int(5.9) == 5

    def test_none_default(self):
        assert _coerce_int(None, default=3) == 3

    def test_invalid_default(self):
        assert _coerce_int("abc", default=2) == 2


class TestCoerceFloat:
    def test_float_passthrough(self):
        assert _coerce_float(0.5) == 0.5

    def test_str_to_float(self):
        assert _coerce_float("0.7") == 0.7

    def test_int_to_float(self):
        assert _coerce_float(1) == 1.0

    def test_none_default(self):
        assert _coerce_float(None, default=0.3) == 0.3


class TestParseComponents:
    def test_empty(self):
        assert _parse_components([]) == []

    def test_single_box(self):
        comps = _parse_components([
            {"name": "main_body", "shape": "box", "width": 10, "length": 8, "height": 6}
        ])
        assert len(comps) == 1
        assert comps[0].name == "main_body"
        assert comps[0].shape == "box"
        assert comps[0].width == 10

    def test_cylinder(self):
        comps = _parse_components([
            {"name": "tower", "shape": "cylinder", "radius": 5, "height": 20,
             "position": "front_right_corner", "material": "stone_bricks"}
        ])
        assert comps[0].shape == "cylinder"
        assert comps[0].radius == 5
        assert comps[0].position == "front_right_corner"

    def test_dirty_input_string_width(self):
        # AI 有时把数值输出成字符串
        comps = _parse_components([
            {"name": "x", "shape": "box", "width": "10", "length": "8", "height": "6"}
        ])
        assert comps[0].width == 10
        assert comps[0].length == 8

    def test_non_dict_skipped(self):
        comps = _parse_components(["not a dict", 123, {"name": "ok", "shape": "box"}])
        assert len(comps) == 1


class TestParseRoof:
    def test_default(self):
        r = _parse_roof({})
        assert r.type == "flat"
        assert r.layer_count == 1

    def test_chinese_roof(self):
        r = _parse_roof({
            "type": "chinese_roof", "height": 6, "overhang": 3,
            "has_flying_eaves": True, "eaves_curvature": "0.7"
        })
        assert r.type == "chinese_roof"
        assert r.has_flying_eaves is True
        assert r.eaves_curvature == 0.7  # 字符串转 float


class TestParseWalls:
    def test_empty(self):
        assert _parse_walls([]) == []

    def test_pillar_wall(self):
        walls = _parse_walls([
            {"type": "pillar", "thickness": 2, "material": "stone_bricks",
             "pillars": {"count": 6, "spacing": 3, "material": "quartz_pillar"}}
        ])
        assert walls[0].type == "pillar"
        assert walls[0].pillars.count == 6

    def test_missing_pillars(self):
        walls = _parse_walls([{"type": "plain_wall"}])
        assert walls[0].pillars.count == 0  # default


class TestParseWindows:
    def test_empty(self):
        ws = _parse_windows({})
        assert ws.arrangement == "symmetry"
        assert ws.items == []

    def test_with_items(self):
        ws = _parse_windows({
            "arrangement": "grid",
            "items": [
                {"shape": "arch", "floor": 1, "side": "front", "x": 0.5},
                {"shape": "arch", "floor": 2, "side": "front", "x": 0.5},
            ]
        })
        assert ws.arrangement == "grid"
        assert len(ws.items) == 2
        assert ws.items[0].shape == "arch"

    def test_dirty_x_string(self):
        ws = _parse_windows({
            "items": [{"x": "0.5", "width": "0.2", "height": "2"}]
        })
        assert ws.items[0].x == 0.5
        assert ws.items[0].width == 0.2
        assert ws.items[0].height == 2


class TestParseEntrance:
    def test_default(self):
        e = _parse_entrance({})
        assert e.type == "simple"
        assert e.position == "center"
        assert e.width == 2

    def test_grand_stair(self):
        e = _parse_entrance({
            "type": "grand_stair", "has_stairs": True, "stair_count": "8",
            "has_columns": True, "column_count": 4
        })
        assert e.has_stairs is True
        assert e.stair_count == 8  # 字符串转 int
        assert e.column_count == 4


class TestParseCurves:
    def test_empty(self):
        assert _parse_curves([]) == []

    def test_cylinder(self):
        curves = _parse_curves([
            {"type": "cylinder", "radius": 5, "height": 20, "center_x": 10, "center_z": 10}
        ])
        assert curves[0].type == "cylinder"
        assert curves[0].radius == 5

    def test_flying_eaves(self):
        curves = _parse_curves([
            {"type": "flying_eaves", "direction": "up", "curvature": "0.8",
             "material": "red_terracotta"}
        ])
        assert curves[0].direction == "up"
        assert curves[0].curvature == 0.8


class TestParseMaterials:
    def test_empty(self):
        assert _parse_materials([]) == []

    def test_dict_materials(self):
        mats = _parse_materials([
            {"name": "red_concrete", "color": "red", "percentage": 50, "location": "wall"}
        ])
        assert mats[0].name == "red_concrete"
        assert mats[0].percentage == 50
        assert mats[0].location == "wall"

    def test_string_materials(self):
        mats = _parse_materials(["stone_bricks", "oak_planks"])
        assert mats[0].name == "stone_bricks"
        assert mats[1].name == "oak_planks"

    def test_dict_material_with_dict_name(self):
        # AI 把 name 字段输出成 dict
        mats = _parse_materials([{"name": {"name": "quartz_block"}, "percentage": 30}])
        assert mats[0].name == "quartz_block"


class TestParseBuildingDSL:
    def test_minimal_valid(self):
        dsl = _parse_building_dsl(
            {"building_type": "house", "width": 10, "length": 10, "height": 8},
            MinecraftVersion.JAVA_1_20,
        )
        assert isinstance(dsl, BuildingDSL)
        assert dsl.building_type == "house"
        assert dsl.width == 10
        assert dsl.height == 8
        assert dsl.style == "modern"

    def test_full_tiananmen(self):
        """完整天安门用例验证解析器。"""
        raw = {
            "building_name": "天安门",
            "building_type": "gate",
            "style": "chinese_traditional",
            "location": "Beijing, China",
            "keywords": ["天安门", "Tiananmen"],
            "width": 60, "length": 32, "height": 20,
            "floor_count": 2, "floor_height": 5, "wall_thickness": 2,
            "shape": "rectangle",
            "components": [
                {"name": "main_body", "shape": "box", "width": 60, "length": 32, "height": 12,
                 "material": "red_concrete"},
                {"name": "roof", "shape": "prism", "width": 60, "length": 32, "height": 8,
                 "position": "top", "material": "red_terracotta"},
            ],
            "roof": {"type": "chinese_roof", "height": 8, "overhang": 3,
                     "has_flying_eaves": True, "eaves_curvature": 0.6,
                     "material": "red_terracotta"},
            "walls": [{"type": "pillar", "thickness": 2, "material": "red_concrete",
                       "pillars": {"count": 12, "spacing": 5, "material": "chiseled_stone_bricks"}}],
            "windows": {"arrangement": "symmetry",
                        "items": [{"shape": "arch", "floor": 2, "side": "front", "x": 0.5,
                                   "width": 0.2, "height": 3}]},
            "entrance": {"type": "portal", "position": "center", "width": 6, "height": 5,
                         "curvature": 1.0, "door_material": "dark_oak_door"},
            "curves": [{"type": "flying_eaves", "direction": "up", "curvature": 0.6,
                        "material": "red_terracotta"}],
            "materials": [
                {"name": "red_concrete", "color": "red", "percentage": 50, "location": "wall"},
                {"name": "red_terracotta", "color": "red", "percentage": 30, "location": "roof"},
            ],
            "platform_material": "stone_bricks",
            "roof_material": "red_terracotta",
            "door_material": "dark_oak_door",
            "window_glass_material": "glass",
            "description": "天安门城台+重檐歇山顶+飞檐翘角",
        }
        dsl = _parse_building_dsl(raw, MinecraftVersion.JAVA_1_20)
        assert dsl.building_name == "天安门"
        assert dsl.style == "chinese_traditional"
        assert dsl.location == "Beijing, China"
        assert dsl.keywords == ["天安门", "Tiananmen"]
        assert len(dsl.components) == 2
        assert dsl.components[0].name == "main_body"
        assert dsl.roof.type == "chinese_roof"
        assert dsl.roof.has_flying_eaves is True
        assert len(dsl.walls) == 1
        assert dsl.walls[0].pillars.count == 12
        assert len(dsl.windows.items) == 1
        assert dsl.entrance.type == "portal"
        assert dsl.entrance.curvature == 1.0
        assert len(dsl.curves) == 1
        assert dsl.curves[0].type == "flying_eaves"
        assert len(dsl.materials) == 2
        assert dsl.platform_material == "stone_bricks"
        assert dsl.roof_material == "red_terracotta"

    def test_dirty_input_all_string_numbers(self):
        """AI 把所有数值输出成字符串。"""
        raw = {
            "building_type": "tower",
            "width": "20", "length": "20", "height": "50",
            "floor_count": "10", "floor_height": "5",
            "detail_scale": "2",
        }
        dsl = _parse_building_dsl(raw, MinecraftVersion.JAVA_1_20)
        assert dsl.width == 20
        assert dsl.length == 20
        assert dsl.height == 50
        assert dsl.floor_count == 10
        assert dsl.floor_height == 5
        assert dsl.detail_scale == 2

    def test_missing_fields_use_defaults(self):
        dsl = _parse_building_dsl({"building_type": "x"}, MinecraftVersion.JAVA_1_20)
        assert dsl.width == 10  # default
        assert dsl.height == 8  # default
        assert dsl.materials == []
        assert dsl.components == []

    def test_material_dict_in_components(self):
        """AI 把 component.material 输出成 dict。"""
        dsl = _parse_building_dsl(
            {"building_type": "x", "width": 10, "length": 10, "height": 8,
             "components": [{"name": "main", "shape": "box", "width": 8, "length": 8, "height": 6,
                             "material": {"name": "white_concrete", "color": "white"}}]},
            MinecraftVersion.JAVA_1_20,
        )
        assert dsl.components[0].material == "white_concrete"


class TestTryRepairJson:
    """测试截断 JSON 修复（AI 输出被 max_tokens 截断时用）。"""

    def test_valid_json_passthrough(self):
        result = _try_repair_json('{"a": 1, "b": [2, 3]}')
        assert result == {"a": 1, "b": [2, 3]}

    def test_truncated_object(self):
        # 截断在中间：{"a": 1, "b": [2, 3  （没闭合 ] 和 }）
        result = _try_repair_json('{"a": 1, "b": [2, 3')
        assert result is not None
        assert result.get("a") == 1

    def test_truncated_array_of_objects(self):
        # 截断在组件数组中间
        truncated = '{"components": [{"name": "main", "shape": "box", "width": 10}, {"name": "roof"'
        result = _try_repair_json(truncated)
        # 至少能解析出第一个 component
        assert result is not None
        assert "components" in result
        assert len(result["components"]) >= 1

    def test_truncated_string_value(self):
        # 截断在字符串值中间：{"desc": "这是建
        result = _try_repair_json('{"desc": "这是建')
        # 可能修复成功（字符串被截）或返回 None
        # 关键是不崩
        assert result is None or "desc" in result

    def test_completely_broken_returns_none(self):
        result = _try_repair_json("not json at all {{{")
        assert result is None

    def test_nested_truncation(self):
        # 深层嵌套截断
        truncated = '{"roof": {"type": "chinese_roof", "eaves": {"curvature": 0.7, "direction": "up"'
        result = _try_repair_json(truncated)
        assert result is not None
        assert "roof" in result
