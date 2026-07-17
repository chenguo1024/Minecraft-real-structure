"""方块 ID 映射表 —— 按 Minecraft 版本管理方块 ID 映射。

设计理由：
  不同 Minecraft 版本的方块 ID 体系不同（1.12 数字 ID vs 1.13+ 命名空间 ID），
  且低版本缺少高版本的新方块。集中管理映射关系，生成器只需引用材料名称，
  由 block_map 负责版本适配和自动 fallback。

数据来源：
  Minecraft Wiki - Java Edition 1.13/Flattening
  https://minecraft.wiki/w/Java_Edition_1.13/Flattening
"""

from __future__ import annotations

from typing import ClassVar

from src.models.building import MinecraftVersion


class BlockMap:
    """按版本查询方块 ID，并提供低版本 fallback 机制。"""

    _PALETTE: ClassVar[dict[str, dict[str, str]]] = {}

    @classmethod
    def _init_palettes(cls) -> None:
        """懒初始化所有版本的方块映射表。"""
        if cls._PALETTE:
            return

        # ── 1.12 及以前：数字 ID ──
        v1_12 = {
            # 基础功能
            "air": "0",

            # ── 石头及其变种 (id=1, data=0..6) ──
            "stone": "1",              # data=0
            "granite": "1:1",
            "polished_granite": "1:2",
            "diorite": "1:3",
            "polished_diorite": "1:4",
            "andesite": "1:5",
            "polished_andesite": "1:6",

            # ── 泥土 (id=3) ──
            "dirt": "3",
            "coarse_dirt": "3:1",
            "podzol": "3:2",
            "grass_block": "2",

            # ── 圆石 (id=4) ──
            "cobblestone": "4",
            "mossy_cobblestone": "48",

            # ── 木板 (id=5, data=0..5) ──
            "oak_planks": "5:0",
            "spruce_planks": "5:1",
            "birch_planks": "5:2",
            "jungle_planks": "5:3",
            "acacia_planks": "5:4",
            "dark_oak_planks": "5:5",

            # ── 原木 (id=17, 162) ──
            "oak_log": "17:0",
            "spruce_log": "17:1",
            "birch_log": "17:2",
            "jungle_log": "17:3",
            "acacia_log": "162:0",
            "dark_oak_log": "162:1",

            # ── 树叶 (id=18, 161) ──
            "oak_leaves": "18:0",
            "spruce_leaves": "18:1",
            "birch_leaves": "18:2",
            "jungle_leaves": "18:3",
            "acacia_leaves": "161:0",
            "dark_oak_leaves": "161:1",

            # ── 砂岩 (id=24) ──
            "sandstone": "24:0",
            "chiseled_sandstone": "24:1",
            "cut_sandstone": "24:2",
            "sandstone_stairs": "128",
            "smooth_sandstone": "24",   # 1.13+ renamed

            # ── 红砂岩 (id=179) ──
            "red_sandstone": "179:0",
            "chiseled_red_sandstone": "179:1",
            "cut_red_sandstone": "179:2",

            # ── 玻璃 (id=20) ──
            "glass": "20",
            "glass_pane": "102",

            # ── 染色玻璃 (id=95, data=0..15) ──
            "white_stained_glass": "95:0",
            "orange_stained_glass": "95:1",
            "magenta_stained_glass": "95:2",
            "light_blue_stained_glass": "95:3",
            "yellow_stained_glass": "95:4",
            "lime_stained_glass": "95:5",
            "pink_stained_glass": "95:6",
            "gray_stained_glass": "95:7",
            "light_gray_stained_glass": "95:8",
            "cyan_stained_glass": "95:9",
            "purple_stained_glass": "95:10",
            "blue_stained_glass": "95:11",
            "brown_stained_glass": "95:12",
            "green_stained_glass": "95:13",
            "red_stained_glass": "95:14",
            "black_stained_glass": "95:15",

            # ── 染色玻璃板 (id=160, data=0..15) ──
            "white_stained_glass_pane": "160:0",
            "orange_stained_glass_pane": "160:1",
            "magenta_stained_glass_pane": "160:2",
            "light_blue_stained_glass_pane": "160:3",
            "yellow_stained_glass_pane": "160:4",
            "lime_stained_glass_pane": "160:5",
            "pink_stained_glass_pane": "160:6",
            "gray_stained_glass_pane": "160:7",
            "light_gray_stained_glass_pane": "160:8",
            "cyan_stained_glass_pane": "160:9",
            "purple_stained_glass_pane": "160:10",
            "blue_stained_glass_pane": "160:11",
            "brown_stained_glass_pane": "160:12",
            "green_stained_glass_pane": "160:13",
            "red_stained_glass_pane": "160:14",
            "black_stained_glass_pane": "160:15",

            # ── 羊毛 (id=35, data=0..15) ──
            "white_wool": "35:0",
            "orange_wool": "35:1",
            "magenta_wool": "35:2",
            "light_blue_wool": "35:3",
            "yellow_wool": "35:4",
            "lime_wool": "35:5",
            "pink_wool": "35:6",
            "gray_wool": "35:7",
            "light_gray_wool": "35:8",
            "cyan_wool": "35:9",
            "purple_wool": "35:10",
            "blue_wool": "35:11",
            "brown_wool": "35:12",
            "green_wool": "35:13",
            "red_wool": "35:14",
            "black_wool": "35:15",

            # ── 陶瓦 (id=159, data=0..15) + 普通陶瓦 (id=172) ──
            "terracotta": "172",
            "white_terracotta": "159:0",
            "orange_terracotta": "159:1",
            "magenta_terracotta": "159:2",
            "light_blue_terracotta": "159:3",
            "yellow_terracotta": "159:4",
            "lime_terracotta": "159:5",
            "pink_terracotta": "159:6",
            "gray_terracotta": "159:7",
            "light_gray_terracotta": "159:8",
            "cyan_terracotta": "159:9",
            "purple_terracotta": "159:10",
            "blue_terracotta": "159:11",
            "brown_terracotta": "159:12",
            "green_terracotta": "159:13",
            "red_terracotta": "159:14",
            "black_terracotta": "159:15",

            # ── 带釉陶瓦 (id=228..235 略有偏移，用近似值) ──
            # 1.12 实际用 block state 映射，这里简化
            "white_glazed_terracotta": "235",
            "orange_glazed_terracotta": "236",
            "magenta_glazed_terracotta": "237",
            "light_blue_glazed_terracotta": "238",
            "yellow_glazed_terracotta": "239",
            "lime_glazed_terracotta": "240",
            "pink_glazed_terracotta": "241",
            "gray_glazed_terracotta": "242",
            "light_gray_glazed_terracotta": "243",
            "cyan_glazed_terracotta": "244",
            "purple_glazed_terracotta": "245",
            "blue_glazed_terracotta": "246",
            "brown_glazed_terracotta": "247",
            "green_glazed_terracotta": "248",
            "red_glazed_terracotta": "249",
            "black_glazed_terracotta": "250",

            # ── 砖 (id=45) ──
            "bricks": "45",
            "brick_stairs": "108",

            # ── 石砖 (id=98, data=0..3) ──
            "stone_bricks": "98:0",
            "mossy_stone_bricks": "98:1",
            "cracked_stone_bricks": "98:2",
            "chiseled_stone_bricks": "98:3",
            "stone_brick_stairs": "109",

            # ── 海晶石 (id=168, data=0..2) ──
            "prismarine": "168:0",
            "prismarine_bricks": "168:1",
            "dark_prismarine": "168:2",
            "sea_lantern": "169",

            # ── 石英 (id=155, data=0..2) ──
            "quartz_block": "155:0",
            "chiseled_quartz_block": "155:1",
            "quartz_pillar": "155:2",
            "quartz_stairs": "156",

            # ── 地狱砖 (id=112) ──
            "nether_bricks": "112",
            "nether_brick_fence": "113",
            "nether_brick_stairs": "114",
            "netherrack": "87",
            "soul_sand": "88",
            "glowstone": "89",

            # ── 末地 ──
            "end_stone": "121",
            "end_stone_bricks": "121",

            # ── 金属块 ──
            "iron_block": "42",
            "gold_block": "41",
            "diamond_block": "57",
            "emerald_block": "133",
            "lapis_block": "22",
            "redstone_block": "152",
            "coal_block": "173",

            # ── 矿物 ──
            "iron_ore": "15",
            "gold_ore": "14",
            "coal_ore": "16",
            "diamond_ore": "56",
            "emerald_ore": "129",
            "lapis_ore": "21",
            "redstone_ore": "73",

            # ── 自然方块 ──
            "gravel": "13",
            "sand": "12",
            "red_sand": "12:1",
            "clay": "82",
            "ice": "79",
            "packed_ice": "174",
            "blue_ice": "174",
            "snow_block": "80",
            "snow": "78",
            "obsidian": "49",
            "bedrock": "7",
            "sponge": "19:0",
            "wet_sponge": "19:1",

            # ── 门 ──
            "oak_door": "64",
            "iron_door": "71",
            "spruce_door": "427",
            "birch_door": "428",
            "jungle_door": "429",
            "acacia_door": "430",
            "dark_oak_door": "431",

            # ── 活板门 ──
            "oak_trapdoor": "96",
            "iron_trapdoor": "167",

            # ── 栅栏 ──
            "oak_fence": "85",
            "nether_brick_fence": "113",
            "oak_fence_gate": "107",

            # ── 地毯 (id=171, data=0..15) ──
            "white_carpet": "171:0",
            "orange_carpet": "171:1",
            "magenta_carpet": "171:2",
            "light_blue_carpet": "171:3",
            "yellow_carpet": "171:4",
            "lime_carpet": "171:5",
            "pink_carpet": "171:6",
            "gray_carpet": "171:7",
            "light_gray_carpet": "171:8",
            "cyan_carpet": "171:9",
            "purple_carpet": "171:10",
            "blue_carpet": "171:11",
            "brown_carpet": "171:12",
            "green_carpet": "171:13",
            "red_carpet": "171:14",
            "black_carpet": "171:15",

            # ── 书架 / 工作台 / TNT ──
            "bookshelf": "47",
            "crafting_table": "58",
            "tnt": "46",

            # ── 混凝土 (粉末) — 1.12 有粉末但无固体混凝土块
            # 用对应的 terracotta 近似
            "white_concrete": "159:0",
            "orange_concrete": "159:1",
            "magenta_concrete": "159:2",
            "light_blue_concrete": "159:3",
            "yellow_concrete": "159:4",
            "lime_concrete": "159:5",
            "pink_concrete": "159:6",
            "gray_concrete": "159:7",
            "light_gray_concrete": "159:8",
            "cyan_concrete": "159:9",
            "purple_concrete": "159:10",
            "blue_concrete": "159:11",
            "brown_concrete": "159:12",
            "green_concrete": "159:13",
            "red_concrete": "159:14",
            "black_concrete": "159:15",

            # ── 楼梯（部分） ──
            "oak_stairs": "53",
            "spruce_stairs": "134",
            "birch_stairs": "135",
            "jungle_stairs": "136",
            "acacia_stairs": "163",
            "dark_oak_stairs": "164",
            "cobblestone_stairs": "67",
            "stone_brick_stairs": "109",
        }

        # ── 1.13+：命名空间 ID ──
        v1_13 = {k: f"minecraft:{k}" for k in v1_12}
        v1_13["air"] = "minecraft:air"

        # 1.13 flattening 后名称有变化的特殊映射
        v1_13_overrides = {
            # 石头变种: 1.13 后与主 ID 相同即可
            "polished_andesite": "minecraft:polished_andesite",
            "granite": "minecraft:granite",
            "polished_granite": "minecraft:polished_granite",
            "diorite": "minecraft:diorite",
            "polished_diorite": "minecraft:polished_diorite",
            "andesite": "minecraft:andesite",
            "coarse_dirt": "minecraft:coarse_dirt",
            "podzol": "minecraft:podzol",
            "grass_block": "minecraft:grass_block",
            "mossy_cobblestone": "minecraft:mossy_cobblestone",
            "cobblestone_stairs": "minecraft:cobblestone_stairs",
            # 1.12→1.13 flattening 重命名
            "smooth_sandstone": "minecraft:smooth_sandstone",
            "red_sand": "minecraft:red_sand",
            "blue_ice": "minecraft:packed_ice",
            "sponge": "minecraft:sponge",
            "wet_sponge": "minecraft:wet_sponge",
            "sea_lantern": "minecraft:sea_lantern",
            "netherrack": "minecraft:netherrack",
            "soul_sand": "minecraft:soul_sand",
            "glowstone": "minecraft:glowstone",
            "end_stone": "minecraft:end_stone",
            "end_stone_bricks": "minecraft:end_stone_bricks",
            "bookshelf": "minecraft:bookshelf",
            "crafting_table": "minecraft:crafting_table",
            "tnt": "minecraft:tnt",
            "snow_block": "minecraft:snow_block",
            "snow": "minecraft:snow",
            "obsidian": "minecraft:obsidian",
            "bedrock": "minecraft:bedrock",
            "clay": "minecraft:clay",
            "ice": "minecraft:ice",
            "packed_ice": "minecraft:packed_ice",
            "oak_stairs": "minecraft:oak_stairs",
            "spruce_stairs": "minecraft:spruce_stairs",
            "birch_stairs": "minecraft:birch_stairs",
            "jungle_stairs": "minecraft:jungle_stairs",
            "acacia_stairs": "minecraft:acacia_stairs",
            "dark_oak_stairs": "minecraft:dark_oak_stairs",
            "stone_brick_stairs": "minecraft:stone_brick_stairs",
            "sandstone_stairs": "minecraft:sandstone_stairs",
            "brick_stairs": "minecraft:brick_stairs",
            "nether_brick_stairs": "minecraft:nether_brick_stairs",
            "quartz_stairs": "minecraft:quartz_stairs",
            "coal_block": "minecraft:coal_block",
            # 陶瓦
            "terracotta": "minecraft:terracotta",
            # 混凝土 — 1.13 开始有真混凝土
            "white_concrete": "minecraft:white_concrete",
            "orange_concrete": "minecraft:orange_concrete",
            "magenta_concrete": "minecraft:magenta_concrete",
            "light_blue_concrete": "minecraft:light_blue_concrete",
            "yellow_concrete": "minecraft:yellow_concrete",
            "lime_concrete": "minecraft:lime_concrete",
            "pink_concrete": "minecraft:pink_concrete",
            "gray_concrete": "minecraft:gray_concrete",
            "light_gray_concrete": "minecraft:light_gray_concrete",
            "cyan_concrete": "minecraft:cyan_concrete",
            "purple_concrete": "minecraft:purple_concrete",
            "blue_concrete": "minecraft:blue_concrete",
            "brown_concrete": "minecraft:brown_concrete",
            "green_concrete": "minecraft:green_concrete",
            "red_concrete": "minecraft:red_concrete",
            "black_concrete": "minecraft:black_concrete",
            # 简化映射（保持向下兼容）
            "concrete": "minecraft:white_concrete",
            "steel": "minecraft:iron_block",
            # 1.12→1.13 重命名的几个
            "oak_door": "minecraft:oak_door",
            "iron_door": "minecraft:iron_door",
            "spruce_door": "minecraft:spruce_door",
            "birch_door": "minecraft:birch_door",
            "jungle_door": "minecraft:jungle_door",
            "acacia_door": "minecraft:acacia_door",
            "dark_oak_door": "minecraft:dark_oak_door",
            "oak_trapdoor": "minecraft:oak_trapdoor",
            "iron_trapdoor": "minecraft:iron_trapdoor",
            "oak_fence": "minecraft:oak_fence",
            "oak_fence_gate": "minecraft:oak_fence_gate",
        }
        v1_13.update(v1_13_overrides)

        # ── 1.17+：洞穴与山崖 ──
        v1_17 = {**v1_13}
        v1_17.update({
            "copper_block": "minecraft:copper_block",
            "cut_copper": "minecraft:cut_copper",
            "exposed_copper": "minecraft:exposed_copper",
            "weathered_copper": "minecraft:weathered_copper",
            "oxidized_copper": "minecraft:oxidized_copper",
            "waxed_copper_block": "minecraft:waxed_copper_block",
            "deepslate": "minecraft:deepslate",
            "cobbled_deepslate": "minecraft:cobbled_deepslate",
            "polished_deepslate": "minecraft:polished_deepslate",
            "deepslate_bricks": "minecraft:deepslate_bricks",
            "deepslate_tiles": "minecraft:deepslate_tiles",
            "chiseled_deepslate": "minecraft:chiseled_deepslate",
            "cracked_deepslate_bricks": "minecraft:cracked_deepslate_bricks",
            "cracked_deepslate_tiles": "minecraft:cracked_deepslate_tiles",
            "calcite": "minecraft:calcite",
            "tuff": "minecraft:tuff",
            "smooth_basalt": "minecraft:smooth_basalt",
            "amethyst_block": "minecraft:amethyst_block",
            "budding_amethyst": "minecraft:budding_amethyst",
            "raw_iron_block": "minecraft:raw_iron_block",
            "raw_gold_block": "minecraft:raw_gold_block",
            "raw_copper_block": "minecraft:raw_copper_block",
            "dripstone_block": "minecraft:dripstone_block",
            "moss_block": "minecraft:moss_block",
            "rooted_dirt": "minecraft:rooted_dirt",
            "mud": "minecraft:mud",
            "packed_mud": "minecraft:packed_mud",
            "mud_bricks": "minecraft:mud_bricks",
        })

        # ── 1.20+：樱花竹筏更新 ──
        v1_20 = {**v1_17}
        v1_20.update({
            "cherry_planks": "minecraft:cherry_planks",
            "cherry_log": "minecraft:cherry_log",
            "cherry_leaves": "minecraft:cherry_leaves",
            "cherry_door": "minecraft:cherry_door",
            "cherry_trapdoor": "minecraft:cherry_trapdoor",
            "cherry_fence": "minecraft:cherry_fence",
            "cherry_stairs": "minecraft:cherry_stairs",
            "cherry_slab": "minecraft:cherry_slab",
            "bamboo_planks": "minecraft:bamboo_planks",
            "bamboo_block": "minecraft:bamboo_block",
            "bamboo_mosaic": "minecraft:bamboo_mosaic",
            "bamboo_door": "minecraft:bamboo_door",
            "bamboo_trapdoor": "minecraft:bamboo_trapdoor",
            "bamboo_fence": "minecraft:bamboo_fence",
            "chiseled_bookshelf": "minecraft:chiseled_bookshelf",
            "decorated_pot": "minecraft:decorated_pot",
            "sniffer_egg": "minecraft:sniffer_egg",
        })

        # ── Bedrock 1.20 ──
        bedrock = {
            "air": "minecraft:air",
            "stone": "minecraft:stone",
            "granite": "minecraft:stone:1",
            "diorite": "minecraft:stone:3",
            "andesite": "minecraft:stone:5",
            "polished_andesite": "minecraft:stone:6",
            "cobblestone": "minecraft:cobblestone",
            "mossy_cobblestone": "minecraft:mossy_cobblestone",
            "oak_planks": "minecraft:planks:0",
            "spruce_planks": "minecraft:planks:1",
            "birch_planks": "minecraft:planks:2",
            "jungle_planks": "minecraft:planks:3",
            "acacia_planks": "minecraft:planks:4",
            "dark_oak_planks": "minecraft:planks:5",
            "cherry_planks": "minecraft:cherry_planks",
            "glass": "minecraft:glass",
            "glass_pane": "minecraft:glass_pane",
            "white_stained_glass": "minecraft:stained_glass:0",
            "orange_stained_glass": "minecraft:stained_glass:1",
            "magenta_stained_glass": "minecraft:stained_glass:2",
            "light_blue_stained_glass": "minecraft:stained_glass:3",
            "yellow_stained_glass": "minecraft:stained_glass:4",
            "lime_stained_glass": "minecraft:stained_glass:5",
            "pink_stained_glass": "minecraft:stained_glass:6",
            "gray_stained_glass": "minecraft:stained_glass:7",
            "light_gray_stained_glass": "minecraft:stained_glass:8",
            "cyan_stained_glass": "minecraft:stained_glass:9",
            "purple_stained_glass": "minecraft:stained_glass:10",
            "blue_stained_glass": "minecraft:stained_glass:11",
            "brown_stained_glass": "minecraft:stained_glass:12",
            "green_stained_glass": "minecraft:stained_glass:13",
            "red_stained_glass": "minecraft:stained_glass:14",
            "black_stained_glass": "minecraft:stained_glass:15",
            "white_wool": "minecraft:wool:0",
            "orange_wool": "minecraft:wool:1",
            "magenta_wool": "minecraft:wool:2",
            "light_blue_wool": "minecraft:wool:3",
            "yellow_wool": "minecraft:wool:4",
            "lime_wool": "minecraft:wool:5",
            "pink_wool": "minecraft:wool:6",
            "gray_wool": "minecraft:wool:7",
            "light_gray_wool": "minecraft:wool:8",
            "cyan_wool": "minecraft:wool:9",
            "purple_wool": "minecraft:wool:10",
            "blue_wool": "minecraft:wool:11",
            "brown_wool": "minecraft:wool:12",
            "green_wool": "minecraft:wool:13",
            "red_wool": "minecraft:wool:14",
            "black_wool": "minecraft:wool:15",
            "stone_bricks": "minecraft:stonebrick",
            "mossy_stone_bricks": "minecraft:stonebrick:1",
            "cracked_stone_bricks": "minecraft:stonebrick:2",
            "chiseled_stone_bricks": "minecraft:stonebrick:3",
            "bricks": "minecraft:brick",
            "terracotta": "minecraft:hardened_clay",
            "white_terracotta": "minecraft:stained_hardened_clay:0",
            "red_terracotta": "minecraft:stained_hardened_clay:14",
            "oak_door": "minecraft:wooden_door",
            "iron_door": "minecraft:iron_door",
            "oak_trapdoor": "minecraft:trapdoor",
            "iron_trapdoor": "minecraft:iron_trapdoor",
            "oak_fence": "minecraft:fence",
            "oak_fence_gate": "minecraft:fence_gate",
            "netherrack": "minecraft:netherrack",
            "soul_sand": "minecraft:soul_sand",
            "glowstone": "minecraft:glowstone",
            "end_stone": "minecraft:end_stone",
            "end_stone_bricks": "minecraft:end_bricks",
            "bookshelf": "minecraft:bookshelf",
            "crafting_table": "minecraft:crafting_table",
            "tnt": "minecraft:tnt",
            "iron_block": "minecraft:iron_block",
            "gold_block": "minecraft:gold_block",
            "diamond_block": "minecraft:diamond_block",
            "emerald_block": "minecraft:emerald_block",
            "obsidian": "minecraft:obsidian",
            "gravel": "minecraft:gravel",
            "sand": "minecraft:sand",
            "red_sand": "minecraft:sand:1",
            "clay": "minecraft:clay",
            "ice": "minecraft:ice",
            "packed_ice": "minecraft:packed_ice",
            "snow_block": "minecraft:snow",
            "bedrock": "minecraft:bedrock",
            "grass_block": "minecraft:grass",
            "dirt": "minecraft:dirt",
            "coarse_dirt": "minecraft:dirt:1",
            "podzol": "minecraft:dirt:2",
            "sandstone": "minecraft:sandstone:0",
            "chiseled_sandstone": "minecraft:sandstone:1",
            "cut_sandstone": "minecraft:sandstone:2",
            "white_concrete": "minecraft:concrete:0",
            "orange_concrete": "minecraft:concrete:1",
            "magenta_concrete": "minecraft:concrete:2",
            "light_blue_concrete": "minecraft:concrete:3",
            "yellow_concrete": "minecraft:concrete:4",
            "lime_concrete": "minecraft:concrete:5",
            "pink_concrete": "minecraft:concrete:6",
            "gray_concrete": "minecraft:concrete:7",
            "light_gray_concrete": "minecraft:concrete:8",
            "cyan_concrete": "minecraft:concrete:9",
            "purple_concrete": "minecraft:concrete:10",
            "blue_concrete": "minecraft:concrete:11",
            "brown_concrete": "minecraft:concrete:12",
            "green_concrete": "minecraft:concrete:13",
            "red_concrete": "minecraft:concrete:14",
            "black_concrete": "minecraft:concrete:15",
            "concrete": "minecraft:concrete:0",
            "steel": "minecraft:iron_block",
        }

        cls._PALETTE = {
            MinecraftVersion.JAVA_1_12.value: v1_12,
            MinecraftVersion.JAVA_1_13.value: v1_13,
            MinecraftVersion.JAVA_1_17.value: v1_17,
            MinecraftVersion.JAVA_1_20.value: v1_20,
            MinecraftVersion.BEDROCK_1_20.value: bedrock,
        }

    def __init__(self, version: MinecraftVersion) -> None:
        self._init_palettes()
        self.version = version

    def get_block_id(self, material_name: str) -> str:
        """返回材料对应的方块 ID。如果当前版本没有，自动 fallback。"""
        key = material_name.lower().strip()
        current_palette = self._PALETTE.get(self.version.value, {})

        # 先尝试精确查找
        block_id = current_palette.get(key)
        if block_id is not None:
            return block_id

        # 未找到时，归一化 AI 通用名再查
        ALIASES = {
            "wood": "oak_planks",
            "wooden planks": "oak_planks",
            "timber": "oak_planks",
            "planks": "oak_planks",
            "stone": "stone_bricks",
            "marble": "quartz_block",
            "granite": "polished_granite",
            "steel": "iron_block",
            "metal": "iron_block",
            "concrete": "white_concrete",
            "brick": "bricks",
            "glass": "glass",
            "glass pane": "glass_pane",
            "cobblestone": "cobblestone",
            "sand stone": "sandstone",
            "red brick": "bricks",
            "dark wood": "dark_oak_planks",
            "light wood": "birch_planks",
            "white marble": "quartz_block",
            "roof tile": "stone_bricks",
            "wall": "stone_bricks",
            "floor": "oak_planks",
        }
        aliased = ALIASES.get(key)
        if aliased:
            block_id = current_palette.get(aliased)
            if block_id is not None:
                return block_id

        # ── Fallback 链：按版本从新到旧查找 ──
        fallback_order = [
            MinecraftVersion.JAVA_1_20,
            MinecraftVersion.JAVA_1_17,
            MinecraftVersion.JAVA_1_13,
            MinecraftVersion.JAVA_1_12,
        ]

        for fb in fallback_order:
            if fb == self.version:
                continue
            palette = self._PALETTE.get(fb.value, {})
            block_id = palette.get(aliased or key)
            if block_id is not None:
                return block_id

        return current_palette.get("stone_bricks", self._PALETTE[MinecraftVersion.JAVA_1_12.value]["stone_bricks"])
