"""方块生成器 —— 根据 BuildingDescription 生成三维方块数据。

设计理由：
  1. 每种屋顶类型独立实现算法，通过 RoofStyle 枚举统一调度。
  2. L 形 / 十字形建筑通过"多个矩形翼板叠加"实现，
     每个翼板独立调用墙壁/窗户/屋顶逻辑，最后合并到一个 grid。
  3. 风格模板将 style 字段（如 "gothic"）映射为默认的 roof/wall/window 组合，
     这样 AI 只需要说 "style: gothic"，生成器自动选择合适的建筑特征。
"""

from __future__ import annotations

import math
import warnings
from enum import Enum

from src.generator.block_map import BlockMap
from src.models.building import BuildingDescription

# ── 材料常量 ──
MAT_AIR = "air"
MAT_WALL = "stone_bricks"
MAT_FLOOR = "oak_planks"
MAT_ROOF = "stone_bricks"
MAT_ROOF_EDGE = "polished_andesite"
MAT_WINDOW = "glass"
MAT_PILLAR = "stone_bricks"
MAT_TRIM = "polished_andesite"

# 风格 → 默认特征映射
STYLE_DEFAULTS: dict[str, dict] = {
    "modern": {
        "roof": "flat",
        "wall_pillar": False,
        "window_spacing": 3,
        "trim": True,
    },
    "gothic": {
        "roof": "gable",
        "wall_pillar": True,
        "window_spacing": 3,
        "trim": True,
    },
    "classical": {
        "roof": "hip",
        "wall_pillar": True,
        "window_spacing": 4,
        "trim": True,
    },
    "asian": {
        "roof": "pyramid",
        "wall_pillar": True,
        "window_spacing": 3,
        "trim": False,
    },
    "medieval": {
        "roof": "gable",
        "wall_pillar": True,
        "window_spacing": 4,
        "trim": False,
    },
    "brutalist": {
        "roof": "flat",
        "wall_pillar": False,
        "window_spacing": 2,
        "trim": False,
    },
}

DEFAULT_STYLE = "modern"


class RoofStyle(str, Enum):
    FLAT = "flat"
    GABLE = "gable"
    HIP = "hip"
    PYRAMID = "pyramid"
    DOME = "dome"


class BlockStructure:
    """生成后的方块结构数据。"""

    def __init__(self, palette: list[str], blocks: list[int],
                 size_x: int, size_y: int, size_z: int) -> None:
        self.palette = palette
        self.blocks = blocks
        self.size_x = size_x
        self.size_y = size_y
        self.size_z = size_z


MAX_RECOMMENDED = 128  # 结构方块加载上限 48，但 /place template 命令无限制


class BlockBuilder:
    """将 BuildingDescription 转为三维方块数组。"""

    def __init__(self, description: BuildingDescription) -> None:
        self.desc = description
        self.block_map = BlockMap(description.minecraft_version)

        # 精细度缩放
        scale = max(1, description.detail_scale)
        self.w = description.width * scale
        self.h = description.height * scale
        self.l = description.length * scale

        # 尺寸警告
        oversized = [dim for dim, val in
                     [("width", self.w), ("height", self.h), ("length", self.l)]
                     if val > MAX_RECOMMENDED]
        if oversized:
            warnings.warn(
                f"尺寸大于结构方块推荐上限 ({MAX_RECOMMENDED}): "
                f"{', '.join(oversized)}。"
                f"可用 /place template 命令放置更大结构。"
            )
        self.shape = description.shape
        self.floors = max(1, self.h // 4)

        # 风格映射
        self.style_cfg = STYLE_DEFAULTS.get(description.style, STYLE_DEFAULTS[DEFAULT_STYLE])

        # 从 features 中解析屋顶类型
        self.roof_type = self._resolve_roof_type()

        # 三维数组
        self._grid: list[list[list[int]]] = []
        self._block_to_idx: dict[str, int] = {}
        self._palette_list: list[str] = []

    # ── 工具方法 ──

    def _resolve(self, material_name: str) -> str:
        return self.block_map.get_block_id(material_name)

    def _idx(self, material_name: str) -> int:
        bid = self._resolve(material_name)
        if bid not in self._block_to_idx:
            self._block_to_idx[bid] = len(self._palette_list)
            self._palette_list.append(bid)
        return self._block_to_idx[bid]

    def _set(self, x: int, y: int, z: int, mat: str) -> None:
        if 0 <= x < self.w and 0 <= y < self.h and 0 <= z < self.l:
            self._grid[z][y][x] = self._idx(mat)

    def _get(self, x: int, y: int, z: int) -> int:
        if 0 <= x < self.w and 0 <= y < self.h and 0 <= z < self.l:
            return self._grid[z][y][x]
        return self._idx(MAT_AIR)

    def _fill(self, x1: int, y1: int, z1: int, x2: int, y2: int, z2: int, mat: str) -> None:
        for z in range(max(0, z1), min(self.l, z2 + 1)):
            for y in range(max(0, y1), min(self.h, y2 + 1)):
                for x in range(max(0, x1), min(self.w, x2 + 1)):
                    self._grid[z][y][x] = self._idx(mat)

    def _hollow_fill(self, x1: int, y1: int, z1: int, x2: int, y2: int, z2: int, mat: str) -> None:
        """只填充立方体表面（空心）。"""
        for z in range(max(0, z1), min(self.l, z2 + 1)):
            for y in range(max(0, y1), min(self.h, y2 + 1)):
                for x in range(max(0, x1), min(self.w, x2 + 1)):
                    if x == x1 or x == x2 or y == y1 or y == y2 or z == z1 or z == z2:
                        self._grid[z][y][x] = self._idx(mat)

    def _is_air(self, x: int, y: int, z: int) -> bool:
        return self._get(x, y, z) == self._idx(MAT_AIR)

    # ── 屋顶类型推断 ──

    def _resolve_roof_type(self) -> str:
        """从 features 和 style 推断屋顶类型。"""
        for f in self.desc.features:
            if f.feature_type == "roof":
                return f.position or self.style_cfg["roof"]
        return self.style_cfg["roof"]

    # ── 地板 ──

    def _build_floor(self) -> None:
        for floor in range(self.floors):
            y = floor * (self.h // self.floors)
            self._fill(0, y, 0, self.w - 1, y, self.l - 1, MAT_FLOOR)

    # ── 墙壁（按翼板构建） ──

    def _build_wing_walls(self, wx1: int, wz1: int, wx2: int, wz2: int) -> None:
        """在指定矩形区域内建造墙壁。"""
        wy1, wy2 = 1, self.h - 2
        # 前后墙
        for z in (wz1, wz2):
            self._hollow_fill(wx1, wy1, z, wx2, wy2, z, MAT_WALL)
        # 左右墙（去掉与前后墙重叠的角）
        for x in (wx1, wx2):
            self._hollow_fill(x, wy1, wz1 + 1, x, wy2, wz2 - 1, MAT_WALL)

    def _build_wing_windows(self, wx1: int, wz1: int, wx2: int, wz2: int, spacing: int) -> None:
        """在翼板的墙上开窗。"""
        win_h = min(2, self.h // self.floors - 1)
        # 前墙
        count = max(1, (wx2 - wx1) // spacing)
        for i in range(count):
            x = wx1 + 1 + (i + 1) * (wx2 - wx1 - 2) // (count + 2)
            for f in range(self.floors):
                yb = 1 + f * (self.h // self.floors)
                for dy in range(win_h):
                    self._set(x, yb + dy, wz1, MAT_WINDOW)
        # 后墙
        for i in range(count):
            x = wx1 + 1 + (i + 1) * (wx2 - wx1 - 2) // (count + 2)
            for f in range(self.floors):
                yb = 1 + f * (self.h // self.floors)
                for dy in range(win_h):
                    self._set(x, yb + dy, wz2, MAT_WINDOW)
        # 左墙
        side_count = max(1, (wz2 - wz1) // spacing)
        for i in range(side_count):
            z = wz1 + 1 + (i + 1) * (wz2 - wz1 - 2) // (side_count + 2)
            for f in range(self.floors):
                yb = 1 + f * (self.h // self.floors)
                for dy in range(win_h):
                    self._set(wx1, yb + dy, z, MAT_WINDOW)
        # 右墙
        for i in range(side_count):
            z = wz1 + 1 + (i + 1) * (wz2 - wz1 - 2) // (side_count + 2)
            for f in range(self.floors):
                yb = 1 + f * (self.h // self.floors)
                for dy in range(win_h):
                    self._set(wx2, yb + dy, z, MAT_WINDOW)

    def _build_wing_pillars(self, wx1: int, wz1: int, wx2: int, wz2: int) -> None:
        """翼板四角加柱。"""
        wy2 = self.h - 2
        for cx, cz in [(wx1, wz1), (wx2, wz1), (wx1, wz2), (wx2, wz2)]:
            for y in range(1, wy2 + 1):
                self._set(cx, y, cz, MAT_PILLAR)

    def _build_wing_trim(self, wx1: int, wz1: int, wx2: int, wz2: int) -> None:
        """翼板的水平装饰线。"""
        for floor in range(1, self.floors):
            y = floor * (self.h // self.floors)
            for z in range(wz1, wz2 + 1):
                for x in range(wx1, wx2 + 1):
                    if (x == wx1 or x == wx2 or z == wz1 or z == wz2):
                        self._set(x, y, z, MAT_TRIM)

    # ── 门 ──

    def _add_door(self) -> None:
        has_door = any(f.feature_type == "door" for f in self.desc.features)
        if not has_door:
            return
        dx = self.w // 2 - 1
        for dy in range(2):
            for dw in range(2):
                self._set(dx + dw, 1 + dy, 0, MAT_AIR)

    # ── 屋顶（按类型） ──

    def _add_roof(self) -> None:
        rt = self.roof_type
        if rt == "gable":
            self._add_gable_roof()
        elif rt == "hip":
            self._add_hip_roof()
        elif rt == "pyramid":
            self._add_pyramid_roof()
        elif rt == "dome":
            self._add_dome_roof()
        else:
            self._add_flat_roof()

    def _add_flat_roof(self) -> None:
        self._fill(0, self.h - 1, 0, self.w - 1, self.h - 1, self.l - 1, MAT_ROOF)
        for x in range(self.w):
            self._set(x, self.h - 1, 0, MAT_ROOF_EDGE)
            self._set(x, self.h - 1, self.l - 1, MAT_ROOF_EDGE)
        for z in range(self.l):
            self._set(0, self.h - 1, z, MAT_ROOF_EDGE)
            self._set(self.w - 1, self.h - 1, z, MAT_ROOF_EDGE)

    def _add_gable_roof(self) -> None:
        """三角人字顶（沿 Z 轴起脊）。"""
        half = self.l // 2
        for z in range(self.l):
            dist = abs(z - half)
            rise = max(0, half - dist)
            ty = self.h - 1 + rise
            if ty >= self.h:
                continue
            for x in range(self.w):
                self._set(x, ty, z, MAT_ROOF)
                if ty > self.h - 1:
                    self._set(x, ty - 1, z, MAT_ROOF)

    def _add_hip_roof(self) -> None:
        """四坡顶：四个方向同时向内收缩。"""
        cx, cz = self.w // 2, self.l // 2
        max_rise = min(cx, cz, (self.h - 1) // 2)
        for level in range(max_rise + 1):
            y = self.h - 1 + level
            if y >= self.h:
                break
            shrink = level
            x1, z1 = shrink, shrink
            x2, z2 = self.w - 1 - shrink, self.l - 1 - shrink
            if x1 > x2 or z1 > z2:
                break
            for x in range(x1, x2 + 1):
                for z in range(z1, z2 + 1):
                    self._set(x, y, z, MAT_ROOF)

    def _add_pyramid_roof(self) -> None:
        """金字塔顶：每层向内缩 1 格。"""
        cx, cz = self.w // 2, self.l // 2
        max_level = min(cx, cz) + 1
        for level in range(max_level):
            y = self.h - 1 + level
            if y >= self.h:
                break
            x1 = max(0, level)
            z1 = max(0, level)
            x2 = min(self.w - 1, self.w - 1 - level)
            z2 = min(self.l - 1, self.l - 1 - level)
            for x in range(x1, x2 + 1):
                for z in range(z1, z2 + 1):
                    self._set(x, y, z, MAT_ROOF)
            # 顶点装饰
            if x1 == x2 and z1 == z2:
                self._set(x1, y, z1, MAT_ROOF_EDGE)

    def _add_dome_roof(self) -> None:
        cx, cz = self.w // 2, self.l // 2
        r = min(self.w, self.l) // 2
        base_y = self.h - 1
        for z in range(self.l):
            for x in range(self.w):
                dx, dz = x - cx, z - cz
                dist = math.sqrt(dx * dx + dz * dz)
                if dist > r:
                    continue
                rise = int(math.sqrt(r * r - dist * dist))
                y = base_y + rise
                if y < self.h:
                    self._set(x, y, z, MAT_ROOF)
                    for fy in range(base_y + 1, y):
                        self._set(x, fy, z, MAT_ROOF)
        tx, tz = cx, cz
        ty = base_y + r
        if ty < self.h:
            self._set(tx, ty, tz, MAT_ROOF_EDGE)

    # ── 支撑柱 ──

    def _add_support_columns(self) -> None:
        if self.w < 6 or self.l < 6:
            return
        cx, cz = self.w // 2, self.l // 2
        for y in range(1, self.h - 2):
            for dx, dz in [(0, 0), (1, 0), (0, 1), (1, 1)]:
                self._set(cx + dx, y, cz + dz, MAT_PILLAR)

    # ── 翼板元组（用于 L / Cross 形状） ──

    def _get_wings(self) -> list[tuple[int, int, int, int]]:
        """返回 [(x1, z1, x2, z2), ...] 每个翼板的矩形范围。"""
        shape = self.shape
        if shape == "L":
            # 主翼: 全宽 x 大部分长；侧翼: 大部分宽 x 完整长
            mw = self.w // 2
            ml = self.l * 2 // 3
            return [
                (0, 0, self.w - 1, ml - 1),
                (0, 0, mw - 1, self.l - 1),
            ]
        elif shape == "cross":
            # 十字：横翼 + 纵翼
            cw = self.w // 3
            cl = self.l // 3
            return [
                (0, cl, self.w - 1, self.l - 1 - cl),
                (cw, 0, self.w - 1 - cw, self.l - 1),
            ]
        elif shape == "T":
            tw = self.w * 2 // 3
            tl = self.l // 3
            return [
                (0, tl, self.w - 1, self.l - 1),
                ((self.w - tw) // 2, 0, (self.w - tw) // 2 + tw - 1, tl - 1),
            ]
        else:
            return [(0, 0, self.w - 1, self.l - 1)]

    # ── 主构建入口 ──

    def build(self) -> BlockStructure:
        self._grid = [
            [[self._idx(MAT_AIR) for _ in range(self.w)] for _ in range(self.h)]
            for _ in range(self.l)
        ]

        wings = self._get_wings()
        spacing = self.style_cfg.get("window_spacing", 3)
        has_pillars = self.style_cfg.get("wall_pillar", False)
        has_trim = self.style_cfg.get("trim", True)

        self._build_floor()

        for wing in wings:
            x1, z1, x2, z2 = wing
            self._build_wing_walls(x1, z1, x2, z2)
            self._build_wing_windows(x1, z1, x2, z2, spacing)
            if has_pillars:
                self._build_wing_pillars(x1, z1, x2, z2)
            if has_trim:
                self._build_wing_trim(x1, z1, x2, z2)

        # 门和屋顶在整个建筑范围上处理
        self._add_door()

        # 屋顶只处理非凹陷区域
        self._add_roof()
        self._add_support_columns()

        # 展平 Z→Y→X
        flat: list[int] = []
        for z in range(self.l):
            for y in range(self.h):
                for x in range(self.w):
                    flat.append(self._grid[z][y][x])

        return BlockStructure(
            palette=self._palette_list,
            blocks=flat,
            size_x=self.w,
            size_y=self.h,
            size_z=self.l,
        )
