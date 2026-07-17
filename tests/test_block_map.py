"""测试方块 ID 映射（版本适配、fallback 链）。"""

import pytest

from src.generator.block_map import BlockMap
from src.models.building import MinecraftVersion


class TestBlockMap:
    def test_version_has_required_blocks(self):
        """每个版本至少要有核心方块。"""
        for v in MinecraftVersion:
            bm = BlockMap(v)
            for block in ("air", "stone", "stone_bricks", "glass"):
                bid = bm.get_block_id(block)
                assert bid is not None, f"{v} 缺少方块 {block}"
                assert bid != ""

    def test_version_specific_id(self):
        """1.12 使用数字 ID，1.13+ 使用命名空间 ID。"""
        bm_12 = BlockMap(MinecraftVersion.JAVA_1_12)
        bm_20 = BlockMap(MinecraftVersion.JAVA_1_20)

        assert bm_12.get_block_id("stone") == "1"
        assert bm_20.get_block_id("stone") == "minecraft:stone"

        assert bm_12.get_block_id("glass") == "20"
        assert bm_20.get_block_id("glass") == "minecraft:glass"

    def test_fallback_to_newer_versions(self):
        """Bedrock 没有 copper_block → fallback 到 1.20 找到 (minecraft:copper_block)。"""
        bm = BlockMap(MinecraftVersion.BEDROCK_1_20)
        bid = bm.get_block_id("copper_block")
        assert bid == "minecraft:copper_block"

    def test_unknown_material_fallback_to_current_version_stone(self):
        """完全未知的材料 → 返回当前版本的 stone_bricks。"""
        bm = BlockMap(MinecraftVersion.JAVA_1_20)
        bid = bm.get_block_id("nonexistent_material_xyz")
        assert bid == "minecraft:stone_bricks"

    def test_bedrock_fallback_for_nonexistent(self):
        """Bedrock 对未知材料 → 返回当前版本的 stonebrick（stone_bricks 的 Bedrock 名）。"""
        bm = BlockMap(MinecraftVersion.BEDROCK_1_20)
        bid = bm.get_block_id("nonexistent_material_xyz")
        assert bid == "minecraft:stonebrick"

    def test_all_versions_have_oak_planks(self):
        """oak_planks 是所有版本的基本方块。"""
        for v in MinecraftVersion:
            bm = BlockMap(v)
            bid = bm.get_block_id("oak_planks")
            assert bid is not None

    def test_12_fallback_for_deepslate(self):
        """1.12 没有 deepslate_bricks → fallback 到 1.17 找到 minecraft:deepslate_bricks。"""
        bm_12 = BlockMap(MinecraftVersion.JAVA_1_12)
        bid = bm_12.get_block_id("deepslate_bricks")
        assert bid == "minecraft:deepslate_bricks"

    def test_17_specific_blocks_present(self):
        """1.17 有自己的深板岩方块。"""
        bm_17 = BlockMap(MinecraftVersion.JAVA_1_17)
        assert bm_17.get_block_id("deepslate_bricks") == "minecraft:deepslate_bricks"
        assert bm_17.get_block_id("calcite") == "minecraft:calcite"

    def test_palette_lazy_init(self):
        """Palette 只初始化一次（ClassVar 机制）。"""
        BlockMap._PALETTE = {}
        bm1 = BlockMap(MinecraftVersion.JAVA_1_20)
        palette_ref = BlockMap._PALETTE
        bm2 = BlockMap(MinecraftVersion.JAVA_1_12)
        assert BlockMap._PALETTE is palette_ref


class TestBlockMapEdgeCases:
    def test_empty_string_returns_current_stone(self):
        bm = BlockMap(MinecraftVersion.JAVA_1_20)
        bid = bm.get_block_id("")
        assert bid == "minecraft:stone_bricks"

    def test_unknown_material_in_bedrock(self):
        bm = BlockMap(MinecraftVersion.BEDROCK_1_20)
        bid = bm.get_block_id("")
        assert bid == "minecraft:stonebrick"

    def test_concrete_and_steel(self):
        """提示词中添加的额外材料映射。"""
        bm = BlockMap(MinecraftVersion.JAVA_1_20)
        assert bm.get_block_id("concrete") == "minecraft:white_concrete"
        assert bm.get_block_id("steel") == "minecraft:iron_block"

    def test_polished_andesite_mapping(self):
        """1.12 和 1.13+ 的 polished_andesite 映射不同。"""
        bm_12 = BlockMap(MinecraftVersion.JAVA_1_12)
        bm_13 = BlockMap(MinecraftVersion.JAVA_1_13)
        assert bm_12.get_block_id("polished_andesite") == "1:6"
        assert bm_13.get_block_id("polished_andesite") == "minecraft:polished_andesite"

    def test_all_16_wool_colors_present_12(self):
        bm = BlockMap(MinecraftVersion.JAVA_1_12)
        for color in ["white", "orange", "magenta", "light_blue", "yellow", "lime",
                       "pink", "gray", "light_gray", "cyan", "purple", "blue",
                       "brown", "green", "red", "black"]:
            bid = bm.get_block_id(f"{color}_wool")
            assert bid is not None, f"缺少 {color}_wool"
            assert ":" in bid  # data value format

    def test_all_16_wool_colors_present_20(self):
        bm = BlockMap(MinecraftVersion.JAVA_1_20)
        for color in ["white", "orange", "magenta", "light_blue", "yellow", "lime",
                       "pink", "gray", "light_gray", "cyan", "purple", "blue",
                       "brown", "green", "red", "black"]:
            bid = bm.get_block_id(f"{color}_wool")
            assert bid is not None, f"缺少 {color}_wool"

    def test_all_16_concrete_colors_13(self):
        """1.13+ 有真混凝土。"""
        bm = BlockMap(MinecraftVersion.JAVA_1_13)
        for color in ["white", "orange", "magenta", "light_blue", "yellow", "lime",
                       "pink", "gray", "light_gray", "cyan", "purple", "blue",
                       "brown", "green", "red", "black"]:
            bid = bm.get_block_id(f"{color}_concrete")
            assert bid is not None, f"缺少 {color}_concrete"
            assert bid.startswith("minecraft:")

    def test_planks_all_6_types_12(self):
        bm = BlockMap(MinecraftVersion.JAVA_1_12)
        for wood in ["oak", "spruce", "birch", "jungle", "acacia", "dark_oak"]:
            bid = bm.get_block_id(f"{wood}_planks")
            assert bid is not None, f"缺少 {wood}_planks"

    def test_planks_all_6_types_20(self):
        bm = BlockMap(MinecraftVersion.JAVA_1_20)
        for wood in ["oak", "spruce", "birch", "jungle", "acacia", "dark_oak", "cherry"]:
            bid = bm.get_block_id(f"{wood}_planks")
            assert bid is not None, f"缺少 {wood}_planks"

    def test_logs_6_types(self):
        bm = BlockMap(MinecraftVersion.JAVA_1_20)
        for wood in ["oak", "spruce", "birch", "jungle", "acacia", "dark_oak"]:
            bid = bm.get_block_id(f"{wood}_log")
            assert bid is not None, f"缺少 {wood}_log"

    def test_stone_variants_12(self):
        bm = BlockMap(MinecraftVersion.JAVA_1_12)
        for variant in ["stone", "granite", "diorite", "andesite",
                         "polished_granite", "polished_diorite", "polished_andesite"]:
            bid = bm.get_block_id(variant)
            assert bid is not None, f"缺少 {variant}"

    def test_stone_brick_variants(self):
        bm = BlockMap(MinecraftVersion.JAVA_1_20)
        for v in ["stone_bricks", "mossy_stone_bricks", "cracked_stone_bricks", "chiseled_stone_bricks"]:
            assert bm.get_block_id(v) is not None, f"缺少 {v}"

    def test_terracotta_16_colors_20(self):
        bm = BlockMap(MinecraftVersion.JAVA_1_20)
        for color in ["white", "orange", "magenta", "light_blue", "yellow", "lime",
                       "pink", "gray", "light_gray", "cyan", "purple", "blue",
                       "brown", "green", "red", "black"]:
            bid = bm.get_block_id(f"{color}_terracotta")
            assert bid is not None, f"缺少 {color}_terracotta"

    def test_deepslate_variants_17(self):
        bm = BlockMap(MinecraftVersion.JAVA_1_17)
        for v in ["deepslate", "cobbled_deepslate", "polished_deepslate",
                   "deepslate_bricks", "deepslate_tiles", "chiseled_deepslate"]:
            assert bm.get_block_id(v) is not None, f"缺少 {v}"

    def test_copper_variants_17(self):
        bm = BlockMap(MinecraftVersion.JAVA_1_17)
        for v in ["copper_block", "cut_copper", "exposed_copper", "weathered_copper"]:
            assert bm.get_block_id(v) is not None, f"缺少 {v}"

    def test_cherry_and_bamboo_20(self):
        bm = BlockMap(MinecraftVersion.JAVA_1_20)
        assert bm.get_block_id("cherry_planks") == "minecraft:cherry_planks"
        assert bm.get_block_id("bamboo_planks") == "minecraft:bamboo_planks"

    def test_prismarine_variants(self):
        bm = BlockMap(MinecraftVersion.JAVA_1_13)
        for v in ["prismarine", "prismarine_bricks", "dark_prismarine"]:
            assert bm.get_block_id(v) is not None, f"缺少 {v}"

    def test_nether_blocks(self):
        bm = BlockMap(MinecraftVersion.JAVA_1_20)
        for v in ["netherrack", "nether_bricks", "soul_sand", "glowstone"]:
            assert bm.get_block_id(v) is not None, f"缺少 {v}"

    def test_doors_all_types(self):
        bm = BlockMap(MinecraftVersion.JAVA_1_20)
        for wood in ["oak", "spruce", "birch", "jungle", "acacia", "dark_oak"]:
            assert bm.get_block_id(f"{wood}_door") is not None, f"缺少 {wood}_door"

    def test_version_count(self):
        """确认所有版本都有数百个方块映射。"""
        for v in MinecraftVersion:
            bm = BlockMap(v)
            palette = BlockMap._PALETTE.get(v.value, {})
            assert len(palette) > 100, f"{v} 只有 {len(palette)} 种方块，期望 > 100"
