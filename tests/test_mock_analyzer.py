"""测试 V2 Mock 分析器（模板选择、字段覆盖、版本适配）。"""
from src.analysis.mock_analyzer import TEMPLATES, analyze
from src.models.building import BuildingDSL, MinecraftVersion


class TestMockAnalyzer:
    def test_template_count(self):
        """至少要有 5 个模板覆盖多种风格。"""
        assert len(TEMPLATES) >= 5

    def test_templates_are_building_dsl(self):
        for name, dsl in TEMPLATES.items():
            assert isinstance(dsl, BuildingDSL), f"{name} 不是 BuildingDSL"

    def test_villa_template(self):
        dsl = analyze("villa.jpg")
        assert dsl.building_type == "villa"
        assert dsl.style == "modern"
        assert dsl.width == 12

    def test_gate_template(self):
        dsl = analyze("tiananmen_gate.jpg")
        assert dsl.building_type == "gate"
        assert dsl.style == "chinese_traditional"
        assert dsl.building_name == "城门"

    def test_church_template(self):
        dsl = analyze("gothic_church.jpg")
        assert dsl.building_type == "church"
        assert dsl.style == "gothic"
        assert dsl.roof.type == "spire"

    def test_tower_template(self):
        dsl = analyze("round_tower.jpg")
        assert dsl.building_type == "tower"
        assert dsl.style == "medieval"
        # 圆塔应有 cylinder component
        assert any(c.shape == "cylinder" for c in dsl.components)

    def test_temple_template(self):
        dsl = analyze("classical_temple.jpg")
        assert dsl.building_type == "temple"
        assert dsl.style == "classical"
        assert dsl.roof.type == "dome"

    def test_default_falls_back_to_villa(self):
        dsl = analyze("unknown_building.jpg")
        assert dsl.building_type == "villa"

    def test_version_override(self):
        dsl = analyze("villa.jpg", version=MinecraftVersion.JAVA_1_17)
        assert dsl.minecraft_version == MinecraftVersion.JAVA_1_17

    def test_returns_copy_not_template(self):
        """analyze 返回副本，修改不影响模板。"""
        dsl1 = analyze("villa.jpg")
        dsl1.width = 999
        dsl2 = analyze("villa.jpg")
        assert dsl2.width == 12  # 模板未被修改

    def test_templates_have_components(self):
        """每个模板至少有一个 component。"""
        for name, dsl in TEMPLATES.items():
            assert len(dsl.components) > 0, f"{name} 没有 components"

    def test_templates_have_materials(self):
        """每个模板至少有 3 种材料。"""
        for name, dsl in TEMPLATES.items():
            assert len(dsl.materials) >= 3, f"{name} 材料不足 3 种"

    def test_templates_have_description(self):
        for name, dsl in TEMPLATES.items():
            assert dsl.description, f"{name} 没有 description"
