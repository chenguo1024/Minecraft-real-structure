"""测试 NBT 导出器（文件生成、数据结构、版本兼容）。"""

from pathlib import Path

import nbtlib
import pytest

from src.exporter.nbt_exporter import export
from src.generator.block_builder import BlockStructure
from src.models.building import MinecraftVersion


class TestDataVersion:
    def test_known_versions(self):
        """通过检查导出文件中的 DataVersion 验证版本映射。"""
        from pathlib import Path
        import tempfile, shutil
        import gzip, nbtlib

        def dv(version, tmp_path):
            s = BlockStructure(palette=["minecraft:stone"], blocks=[0], size_x=1, size_y=1, size_z=1)
            out = Path(tmp_path) / f"{version.value}.nbt"
            from src.exporter.nbt_exporter import export
            export(s, out, version)
            f = nbtlib.load(str(out), gzipped=True)
            return int(f["DataVersion"])

        tmp = tempfile.mkdtemp()
        try:
            assert dv(MinecraftVersion.JAVA_1_12, tmp) == 1343
            assert dv(MinecraftVersion.JAVA_1_13, tmp) == 1631
            assert dv(MinecraftVersion.JAVA_1_17, tmp) == 2724
            assert dv(MinecraftVersion.JAVA_1_20, tmp) == 3465
            assert dv(MinecraftVersion.BEDROCK_1_20, tmp) == 0
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestNBTExport:
    def _small_structure(self) -> BlockStructure:
        return BlockStructure(
            palette=["minecraft:stone", "minecraft:glass"],
            blocks=[0, 1, 0, 1, 1, 0, 0, 1, 1],
            size_x=3, size_y=1, size_z=3,
        )

    def test_export_creates_file(self, tmp_path: Path):
        s = self._small_structure()
        out = tmp_path / "test.nbt"
        export(s, out, MinecraftVersion.JAVA_1_20)
        assert out.exists()
        assert out.stat().st_size > 0

    def test_nbt_has_correct_structure(self, tmp_path: Path):
        s = self._small_structure()
        out = tmp_path / "test.nbt"
        export(s, out, MinecraftVersion.JAVA_1_20)

        nbt_file = nbtlib.load(str(out))

        assert "size" in nbt_file
        assert "palette" in nbt_file
        assert "blocks" in nbt_file
        assert "DataVersion" in nbt_file
        assert "entities" in nbt_file

        assert list(nbt_file["size"]) == [3, 1, 3]
        assert nbt_file["DataVersion"] == 3465
        assert len(nbt_file["palette"]) == 2
        assert str(nbt_file["palette"][0]["Name"]) == "minecraft:stone"
        assert len(nbt_file["blocks"]) == 9

        first = nbt_file["blocks"][0]
        assert list(first["pos"]) == [0, 0, 0]
        assert first["state"] == 0

    def test_version_affects_data_version(self, tmp_path: Path):
        s = self._small_structure()
        out12 = tmp_path / "test_12.nbt"
        out20 = tmp_path / "test_20.nbt"

        export(s, out12, MinecraftVersion.JAVA_1_12)
        export(s, out20, MinecraftVersion.JAVA_1_20)

        nbt12 = nbtlib.load(str(out12))
        nbt20 = nbtlib.load(str(out20))

        assert nbt12["DataVersion"] == 1343
        assert nbt20["DataVersion"] == 3465

    def test_size_matches_blocks_count(self, tmp_path: Path):
        s = self._small_structure()
        out = tmp_path / "test.nbt"
        export(s, out, MinecraftVersion.JAVA_1_20)

        nbt_file = nbtlib.load(str(out))
        blocks = nbt_file["blocks"]
        sx, sy, sz = list(nbt_file["size"])
        assert len(blocks) == sx * sy * sz

    def test_large_structure_exports(self, tmp_path: Path):
        palette = ["minecraft:air", "minecraft:stone"]
        blocks = [i % 2 for i in range(10 * 10 * 10)]
        s = BlockStructure(palette=palette, blocks=blocks, size_x=10, size_y=10, size_z=10)
        out = tmp_path / "large.nbt"
        export(s, out, MinecraftVersion.JAVA_1_20)
        assert out.exists()
        assert out.stat().st_size > 100

    def test_export_overwrites_existing(self, tmp_path: Path):
        s = self._small_structure()
        out = tmp_path / "test.nbt"
        export(s, out, MinecraftVersion.JAVA_1_20)
        size1 = out.stat().st_size
        export(s, out, MinecraftVersion.JAVA_1_20)
        size2 = out.stat().st_size
        assert size2 > 0

    def test_nbt_binary_format(self, tmp_path: Path):
        """验证输出是 GZip 压缩的 NBT 格式（Minecraft 需要 GZip）。"""
        s = self._small_structure()
        out = tmp_path / "test.nbt"
        export(s, out, MinecraftVersion.JAVA_1_20)

        with open(str(out), "rb") as f:
            magic = f.read(2)

        assert magic == b'\x1f\x8b', f"应为 GZip 格式 (1f8b)，实际为 {magic.hex()}"
