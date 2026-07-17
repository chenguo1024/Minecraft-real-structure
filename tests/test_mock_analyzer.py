"""测试 Mock 分析器（模板选择、关键词匹配、版本覆盖）。"""

from src.analysis.mock_analyzer import TEMPLATES, analyze
from src.models.building import MinecraftVersion


class TestMockAnalyzer:
    def test_template_count(self):
        """至少要有 5 个模板覆盖多种风格。"""
        assert len(TEMPLATES) >= 5

    def test_villa_template(self):
        desc = analyze("my_villa.jpg", MinecraftVersion.JAVA_1_20)
        assert desc.building_type == "villa"
        assert desc.style == "modern"

    def test_church_template(self):
        desc = analyze("a_church.jpg", MinecraftVersion.JAVA_1_20)
        assert desc.building_type == "church"
        assert desc.style == "gothic"
        assert desc.shape == "cross"

    def test_pagoda_template(self):
        desc = analyze("pagoda_photo.jpg", MinecraftVersion.JAVA_1_20)
        assert desc.building_type == "pagoda"
        assert desc.style == "asian"

    def test_mansion_template(self):
        desc = analyze("mansion_front.jpg", MinecraftVersion.JAVA_1_20)
        assert desc.building_type == "mansion"
        assert desc.style == "classical"

    def test_l_shape_template(self):
        desc = analyze("L_villa_design.jpg", MinecraftVersion.JAVA_1_20)
        assert desc.building_type == "villa"
        assert desc.shape == "L"

    def test_unknown_filename_fallsback_to_villa(self):
        desc = analyze("unknown_random.png", MinecraftVersion.JAVA_1_20)
        assert desc.building_type == "villa"

    def test_version_override(self):
        desc_12 = analyze("villa.jpg", MinecraftVersion.JAVA_1_12)
        desc_20 = analyze("villa.jpg", MinecraftVersion.JAVA_1_20)
        assert desc_12.minecraft_version == MinecraftVersion.JAVA_1_12
        assert desc_20.minecraft_version == MinecraftVersion.JAVA_1_20

    def test_materials_present(self):
        desc = analyze("church.jpg", MinecraftVersion.JAVA_1_20)
        assert len(desc.materials) > 0

    def test_features_present(self):
        desc = analyze("villa.jpg", MinecraftVersion.JAVA_1_20)
        assert len(desc.features) > 0
        # 至少要有 roof 特征
        roof_types = [f.feature_type for f in desc.features]
        assert "roof" in roof_types
