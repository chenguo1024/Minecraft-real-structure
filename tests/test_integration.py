"""集成测试 —— 完整管线（Mock 分析 → 生成 → 导出）。"""

from pathlib import Path

import nbtlib

from src.analysis.mock_analyzer import analyze as mock_analyze
from src.exporter.nbt_exporter import export
from src.generator.block_builder import BlockBuilder
from src.models.building import MinecraftVersion


class TestFullPipeline:
    """完整管线：Mock 分析 → BlockBuilder → NBT 导出。"""

    def test_pipeline_villa(self, tmp_path: Path):
        desc = mock_analyze("villa.jpg", MinecraftVersion.JAVA_1_20)
        builder = BlockBuilder(desc)
        structure = builder.build()
        out = tmp_path / "villa.nbt"
        export(structure, out, MinecraftVersion.JAVA_1_20)

        assert out.exists()
        nbt_file = nbtlib.load(str(out))

        size = list(nbt_file["size"])
        assert size == [8, 10, 12]
        blocks = list(nbt_file["blocks"])
        assert len(blocks) < 8 * 10 * 12  # 空气方块不写入
        assert len(blocks) > 0
        assert nbt_file["DataVersion"] == 3465

    def test_pipeline_church(self, tmp_path: Path):
        desc = mock_analyze("church.jpg", MinecraftVersion.JAVA_1_17)
        builder = BlockBuilder(desc)
        structure = builder.build()
        out = tmp_path / "church.nbt"
        export(structure, out, MinecraftVersion.JAVA_1_17)

        assert out.exists()
        nbt_file = nbtlib.load(str(out))

        size = list(nbt_file["size"])
        assert size == [10, 18, 20]
        assert nbt_file["DataVersion"] == 2724

    def test_pipeline_all_templates(self, tmp_path: Path):
        """所有 Mock 模板都通过完整管线不出错。"""
        templates = ["villa", "L_villa", "church", "pagoda", "mansion"]
        for name in templates:
            desc = mock_analyze(f"{name}.jpg", MinecraftVersion.JAVA_1_20)
            builder = BlockBuilder(desc)
            structure = builder.build()
            out = tmp_path / f"{name}.nbt"
            export(structure, out, MinecraftVersion.JAVA_1_20)
            assert out.exists()
            nbt_file = nbtlib.load(str(out))
            assert len(nbt_file["blocks"]) > 0

    def test_pipeline_all_versions(self, tmp_path: Path):
        """所有 Minecraft 版本都能跑通管线。"""
        for v in MinecraftVersion:
            desc = mock_analyze("villa.jpg", v)
            builder = BlockBuilder(desc)
            structure = builder.build()
            out = tmp_path / f"villa_{v.value}.nbt"
            export(structure, out, v)
            assert out.exists()

    def test_pipeline_block_count_matches_size(self, tmp_path: Path):
        desc = mock_analyze("mansion.jpg", MinecraftVersion.JAVA_1_20)
        builder = BlockBuilder(desc)
        structure = builder.build()
        out = tmp_path / "mansion.nbt"
        export(structure, out, MinecraftVersion.JAVA_1_20)

        nbt_file = nbtlib.load(str(out))
        sx, sy, sz = list(nbt_file["size"])
        total = sx * sy * sz
        blocks = list(nbt_file["blocks"])
        assert 0 < len(blocks) < total  # 空气方块不写入
