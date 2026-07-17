"""NBT 结构文件导出器 —— 将 BlockStructure 写入 Minecraft 可识别的 .nbt 文件。

设计理由：
  1. 手写 NBT 二进制格式（而非使用 nbtlib），避免第三方库兼容性问题。
  2. Minecraft 结构文件是 GZip 压缩的 NBT (big-endian)。
  3. 结构文件中的 blocks 以"每个方块一个条目 + palette 索引"方式存储。

NBT 结构文件格式参考：
  https://minecraft.wiki/w/Structure_file
"""

from __future__ import annotations

import gzip
import struct
from pathlib import Path

from src.generator.block_builder import BlockStructure
from src.models.building import MinecraftVersion

# ── NBT 标签类型 ──
TAG_END = 0
TAG_BYTE = 1
TAG_SHORT = 2
TAG_INT = 3
TAG_LONG = 4
TAG_FLOAT = 5
TAG_DOUBLE = 6
TAG_BYTE_ARRAY = 7
TAG_STRING = 8
TAG_LIST = 9
TAG_COMPOUND = 10
TAG_INT_ARRAY = 11
TAG_LONG_ARRAY = 12


def _write_string(buf: bytearray, s: str) -> None:
    """写入 NBT 字符串：2 字节长度（大端）+ UTF-8 内容。"""
    encoded = s.encode("utf-8")
    buf.extend(struct.pack(">H", len(encoded)))
    buf.extend(encoded)


def _write_tag_header(buf: bytearray, tag_type: int, name: str) -> None:
    """写入标签头：1 字节类型 + 名字字符串。"""
    buf.append(tag_type)
    _write_string(buf, name)


def _write_int(buf: bytearray, value: int) -> None:
    """写入 4 字节大端整数。"""
    buf.extend(struct.pack(">i", value))


def _write_int_array(buf: bytearray, name: str, values: list[int]) -> None:
    """写入 TAG_IntArray。"""
    _write_tag_header(buf, TAG_INT_ARRAY, name)
    _write_int(buf, len(values))
    for v in values:
        _write_int(buf, v)


def _write_list_header(buf: bytearray, name: str, entry_type: int, length: int) -> None:
    """写入 TAG_List 头部（类型 + 名字 + 长度），不包含条目内容。"""
    _write_tag_header(buf, TAG_LIST, name)
    buf.append(entry_type)
    _write_int(buf, length)


def _write_int_list(buf: bytearray, name: str, values: list[int]) -> None:
    """写入 TAG_List[TAG_Int]（Minecraft 原版结构使用此格式而非 IntArray）。"""
    _write_list_header(buf, name, TAG_INT, len(values))
    for v in values:
        _write_int(buf, v)


def _write_compound_end(buf: bytearray) -> None:
    """写入 TAG_END 标记复合标签结束。"""
    buf.append(TAG_END)


def export(
    structure: BlockStructure,
    output_path: Path,
    version: MinecraftVersion,
) -> None:
    """将 BlockStructure 写入 .nbt 结构文件（GZip 压缩 NBT 格式）。

    Args:
        structure: 生成器输出的方块结构数据。
        output_path: 输出 .nbt 文件路径。
        version: 目标 Minecraft 版本，决定 DataVersion。
    """
    buf = bytearray()

    # ── 根复合标签（无名称） ──
    _write_tag_header(buf, TAG_COMPOUND, "")  # 根标签，名称空字符串

    # ── size: List[Int] ──
    _write_int_list(buf, "size", [structure.size_x, structure.size_y, structure.size_z])

    # ── palette: List[Compound] ──
    # 每个条目是 Compound 内容（无 0x0A 头，无 name）
    _write_list_header(buf, "palette", TAG_COMPOUND, len(structure.palette))
    for block_id in structure.palette:
        _write_tag_header(buf, TAG_STRING, "Name")
        _write_string(buf, block_id)
        _write_compound_end(buf)

    # ── blocks: List[Compound] ──
    # 每个条目是 Compound 内容（无 0x0A 头，无 name）
    _write_list_header(buf, "blocks", TAG_COMPOUND, len(structure.blocks))
    idx = 0
    for z in range(structure.size_z):
        for y in range(structure.size_y):
            for x in range(structure.size_x):
                _write_int_list(buf, "pos", [x, y, z])
                _write_tag_header(buf, TAG_INT, "state")
                _write_int(buf, structure.blocks[idx])
                _write_compound_end(buf)
                idx += 1

    # ── entities: List (empty) — 原版空列表用 TAG_End 作条目类型 ──
    _write_list_header(buf, "entities", TAG_END, 0)

    # ── DataVersion: Int ──
    data_version = {
        MinecraftVersion.JAVA_1_12: 1343,
        MinecraftVersion.JAVA_1_13: 1631,
        MinecraftVersion.JAVA_1_17: 2724,
        MinecraftVersion.JAVA_1_20: 3465,
        MinecraftVersion.BEDROCK_1_20: 0,
    }.get(version, 3465)
    _write_tag_header(buf, TAG_INT, "DataVersion")
    _write_int(buf, data_version)

    # ── 结束根复合标签 ──
    _write_compound_end(buf)

    # ── GZip 压缩写出 ──
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(str(output_path), "wb") as f:
        f.write(buf)
