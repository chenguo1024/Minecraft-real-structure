"""V2 集成测试 —— 完整管线（Mock 分析 → BuildingDSL → BlockBuilder → NBT 导出）。"""
from pathlib import Path

import pytest

from src.analysis.mock_analyzer import analyze as mock_analyze
from src.exporter.nbt_exporter import export
from src.generator.block_builder import BlockBuilder
from src.models.building import MinecraftVersion


@pytest.fixture
def tmp_output(tmp_path):
    """临时 .nbt 输出路径。"""
    return tmp_path / "test_output.nbt"


class TestFullPipeline:
    """完整管线：Mock 分析 → BlockBuilder → NBT 导出。"""

    def test_pipeline_villa(self, tmp_output):
        """现代别墅完整管线。"""
        desc = mock_analyze("villa.jpg")
        builder = BlockBuilder(desc)
        structure = builder.build()
        export(structure, tmp_output, desc.minecraft_version)
        assert tmp_output.exists()
        assert tmp_output.stat().st_size > 0

    def test_pipeline_church(self, tmp_output):
        """哥特教堂完整管线。"""
        desc = mock_analyze("gothic_church.jpg")
        builder = BlockBuilder(desc)
        structure = builder.build()
        export(structure, tmp_output, desc.minecraft_version)
        assert tmp_output.exists()

    def test_pipeline_gate(self, tmp_output):
        """中式城门完整管线。"""
        desc = mock_analyze("tiananmen_gate.jpg")
        builder = BlockBuilder(desc)
        structure = builder.build()
        export(structure, tmp_output, desc.minecraft_version)
        assert tmp_output.exists()

    def test_pipeline_tower(self, tmp_output):
        """圆塔完整管线。"""
        desc = mock_analyze("round_tower.jpg")
        builder = BlockBuilder(desc)
        structure = builder.build()
        export(structure, tmp_output, desc.minecraft_version)
        assert tmp_output.exists()

    def test_pipeline_temple(self, tmp_output):
        """古典庙宇完整管线。"""
        desc = mock_analyze("classical_temple.jpg")
        builder = BlockBuilder(desc)
        structure = builder.build()
        export(structure, tmp_output, desc.minecraft_version)
        assert tmp_output.exists()

    def test_pipeline_all_templates(self, tmp_path):
        """所有模板都能走通完整管线。"""
        from src.analysis.mock_analyzer import TEMPLATES
        for name in TEMPLATES:
            desc = mock_analyze(f"{name}.jpg")
            builder = BlockBuilder(desc)
            structure = builder.build()
            out = tmp_path / f"{name}.nbt"
            export(structure, out, desc.minecraft_version)
            assert out.exists(), f"{name} 导出失败"

    def test_pipeline_all_versions(self, tmp_path):
        """所有 Minecraft 版本都能导出。"""
        desc = mock_analyze("villa.jpg")
        builder = BlockBuilder(desc)
        structure = builder.build()
        for version in MinecraftVersion:
            desc_copy = desc.model_copy(deep=True)
            desc_copy.minecraft_version = version
            out = tmp_path / f"villa_{version.value}.nbt"
            export(structure, out, version)
            assert out.exists(), f"{version.value} 导出失败"

    def test_pipeline_block_count_matches_size(self, tmp_output):
        """导出的方块总数 = size_x * size_y * size_z。"""
        desc = mock_analyze("villa.jpg")
        builder = BlockBuilder(desc)
        structure = builder.build()
        export(structure, tmp_output, desc.minecraft_version)
        assert len(structure.blocks) == structure.size_x * structure.size_y * structure.size_z

    def test_pipeline_nbt_has_correct_structure(self, tmp_output):
        """NBT 文件是有效的 GZip 压缩 NBT（GZip magic number 1f 8b）。"""
        desc = mock_analyze("villa.jpg")
        builder = BlockBuilder(desc)
        structure = builder.build()
        export(structure, tmp_output, desc.minecraft_version)
        # 验证是 GZip 文件（NBT 结构文件用 GZip 压缩）
        with open(tmp_output, "rb") as f:
            magic = f.read(2)
        assert magic == b"\x1f\x8b", f"NBT 文件应为 GZip 压缩，magic={magic!r}"
