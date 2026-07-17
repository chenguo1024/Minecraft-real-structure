from __future__ import annotations

import math
import random
import warnings
from enum import Enum

from src.generator.block_map import BlockMap
from src.models.building import BuildingDescription


# ── 默认材料常量（被 AI materials 列表覆盖） ──
MAT_AIR = "air"
MAT_WALL = "stone_bricks"
MAT_FLOOR = "oak_planks"
MAT_ROOF = "stone_bricks"
MAT_WINDOW = "glass"
MAT_PILLAR = "chiseled_stone_bricks"

# 风格 → 默认特征映射
STYLE_DEFAULTS: dict[str, dict] = {
    "modern": {"roof": "flat", "wall_pillar": False, "window_spacing": 3, "trim": True},
    "gothic": {"roof": "gable", "wall_pillar": True, "window_spacing": 3, "trim": True},
    "classical": {"roof": "hip", "wall_pillar": True, "window_spacing": 4, "trim": True},
    "asian": {"roof": "pyramid", "wall_pillar": True, "window_spacing": 3, "trim": False},
    "medieval": {"roof": "gable", "wall_pillar": True, "window_spacing": 4, "trim": False},
    "brutalist": {"roof": "flat", "wall_pillar": False, "window_spacing": 2, "trim": False},
    "chinese": {"roof": "pyramid", "wall_pillar": True, "window_spacing": 3, "trim": False},
}
DEFAULT_STYLE = "modern"


class BlockStructure:
    def __init__(self, palette: list[str], blocks: list[int],
                 size_x: int, size_y: int, size_z: int) -> None:
        self.palette = palette
        self.blocks = blocks
        self.size_x = size_x
        self.size_y = size_y
        self.size_z = size_z


# Minecraft 1.20+ /place template 命令支持最大 128×128×128
# 结构方块（LOAD 模式）限制 48×48×48，超过自动提示用命令
MAX_STRUCTURE_BLOCK = 128
STRUCTURE_BLOCK_LIMIT = 48  # 结构方块上限，仅用于提示
MAX_RECOMMENDED = 128


class BlockBuilder:
    def __init__(self, description: BuildingDescription) -> None:
        self.desc = description
        self.block_map = BlockMap(description.minecraft_version)

        scale = max(1, description.detail_scale)
        self.w = min(description.width * scale, MAX_STRUCTURE_BLOCK)
        self.h = min(description.height * scale, MAX_STRUCTURE_BLOCK)
        self.l = min(description.length * scale, MAX_STRUCTURE_BLOCK)



        if self.w > STRUCTURE_BLOCK_LIMIT or self.h > STRUCTURE_BLOCK_LIMIT or self.l > STRUCTURE_BLOCK_LIMIT:
            warnings.warn(f"结构({self.w}x{self.h}x{self.l})超出结构方块上限({STRUCTURE_BLOCK_LIMIT}^3)，请用 /place template 命令放置")

        oversized = [dim for dim, val in
                     [("width", self.w), ("height", self.h), ("length", self.l)]
                     if val > MAX_RECOMMENDED]
        if oversized:
            warnings.warn(f"结构尺寸较大 ({', '.join(oversized)})，可用 /place template 命令放置")

        self.shape = description.shape
        self.floors = max(1, self.h // 4)
        self.style_cfg = STYLE_DEFAULTS.get(description.style, STYLE_DEFAULTS[DEFAULT_STYLE])

        # 从 AI materials 列表中选取主材料
        self._init_materials()

        # 从 features 中解析屋顶类型
        self.roof_type = self._resolve_roof_type()

        self._grid: list[list[list[int]]] = []
        self._block_to_idx: dict[str, int] = {}
        self._palette_list: list[str] = []

    # ── 材料选择 ──

    def _init_materials(self) -> None:
        materials = self.desc.materials
        if materials:
            sorted_mats = sorted(materials, key=lambda m: m.fraction or 0, reverse=True)
            primary = sorted_mats[0].name
            self.mat_wall = primary
            self.mat_roof = sorted_mats[1].name if len(sorted_mats) > 1 else primary
            self.mat_floor = sorted_mats[-1].name if len(sorted_mats) > 1 else "oak_planks"
            self.mat_trim = sorted_mats[1].name if len(sorted_mats) > 1 else "polished_andesite"
            self.mat_pillar = primary
            # 选择对比材料做装饰
            accent = sorted_mats[-1].name if len(sorted_mats) > 2 else "polished_andesite"
            self.mat_accent = accent
            self.mat_detail = sorted_mats[1].name if len(sorted_mats) > 1 else primary
        else:
            self.mat_wall = MAT_WALL
            self.mat_roof = MAT_ROOF
            self.mat_floor = MAT_FLOOR
            self.mat_trim = "polished_andesite"
            self.mat_pillar = MAT_PILLAR
            self.mat_accent = "polished_andesite"
            self.mat_detail = MAT_WALL

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
        for z in range(max(0, z1), min(self.l, z2 + 1)):
            for y in range(max(0, y1), min(self.h, y2 + 1)):
                for x in range(max(0, x1), min(self.w, x2 + 1)):
                    if x == x1 or x == x2 or y == y1 or y == y2 or z == z1 or z == z2:
                        self._grid[z][y][x] = self._idx(mat)

    def _line_x(self, x1: int, x2: int, y: int, z: int, mat: str) -> None:
        for x in range(min(x1, x2), max(x1, x2) + 1):
            self._set(x, y, z, mat)

    def _line_z(self, z1: int, z2: int, x: int, y: int, mat: str) -> None:
        for z in range(min(z1, z2), max(z1, z2) + 1):
            self._set(x, y, z, mat)

    def _line_y(self, y1: int, y2: int, x: int, z: int, mat: str) -> None:
        for y in range(min(y1, y2), max(y1, y2) + 1):
            self._set(x, y, z, mat)

    def _is_air(self, x: int, y: int, z: int) -> bool:
        return self._get(x, y, z) == self._idx(MAT_AIR)

    # ═══════════════════════════════════════════════════════════════
    #  曲线/圆形辅助方法
    # ═══════════════════════════════════════════════════════════════

    def _circle_xz(self, cx: int, cz: int, r: int, y: int, mat: str,
                   fill: bool = False) -> None:
        """在 XZ 平面画一个圆环（或实心圆）。
        
        Args:
            cx, cz: 圆心坐标
            r: 半径
            y: Y 高度
            mat: 方块材料
            fill: True=实心圆, False=空心圆环
        """
        for dz in range(-r, r + 1):
            z = cz + dz
            if z < 0 or z >= self.l:
                continue
            dx_max = int(math.sqrt(max(0, r * r - dz * dz)))
            for dx in range(-dx_max, dx_max + 1):
                x = cx + dx
                if x < 0 or x >= self.w:
                    continue
                if fill or abs(dx) == dx_max or abs(dz) == r:
                    self._set(x, y, z, mat)

    def _cylinder_y(self, cx: int, cz: int, r: int,
                    y1: int, y2: int, mat: str, fill: bool = False) -> None:
        """构建垂直圆柱体。"""
        for y in range(max(0, y1), min(self.h, y2 + 1)):
            self._circle_xz(cx, cz, r, y, mat, fill=fill)

    def _arch_curve(self, cx: int, cz: int, r: int,
                    y_base: int, height: int, mat: str, thick: int = 1) -> None:
        """构建拱形曲线（半圆拱）。
        
        Args:
            cx, cz: 拱的中心点 XZ
            r: 拱的半径
            y_base: 拱底 Y
            height: 拱高
            mat: 材料
            thick: 厚度
        """
        for angle in range(0, 181, 5):
            rad = math.radians(angle)
            dy = int(height * math.sin(rad))
            dx = int(r * math.cos(rad))
            y = y_base + dy
            if y >= self.h:
                break
            for t in range(thick):
                self._set(cx + dx + t, y, cz, mat)
                self._set(cx - dx - t, y, cz, mat)

    # ── 屋顶类型 ──

    def _resolve_roof_type(self) -> str:
        for f in self.desc.features:
            if f.feature_type == "roof":
                return f.position or self.style_cfg["roof"]
        return self.style_cfg["roof"]

    # ── 地板 ──

    def _build_floor(self) -> None:
        for floor in range(self.floors):
            y = floor * (self.h // self.floors)
            self._fill(0, y, 0, self.w - 1, y, self.l - 1, self.mat_floor)

    # ═══════════════════════════════════════════════════════════════
    #  按建筑类型构建
    # ═══════════════════════════════════════════════════════════════

    def build(self) -> BlockStructure:
        self._grid = [
            [[self._idx(MAT_AIR) for _ in range(self.w)] for _ in range(self.h)]
            for _ in range(self.l)
        ]

        # 如果 AI 提供了逐面描述，使用 facade 生成器（覆盖所有建筑类型）
        if self.desc.facades:
            self._build_from_facades()
        else:
            btype = self.desc.building_type
            if btype == "gate":
                self._build_gate()
            elif btype == "arch":
                self._build_arch()
            elif btype == "tower":
                self._build_tower()
            elif btype == "pagoda":
                self._build_pagoda()
            elif btype == "bridge":
                self._build_bridge()
            else:
                self._build_generic()

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

    # ─── 大门 / 牌坊 ───

    def _build_gate(self) -> None:
        """大门建筑：多开间柱列 + 台基 + 重檐屋顶。"""
        bays = self.desc.bays or max(1, self.w // 4)
        column_rows = self.l // 3 if self.l > 2 else 1
        platform_h = min(self.desc.platform_height or max(1, self.h // 6), self.h // 3)
        roof_tiers = self.desc.roof_tiers or 1
        column_w = max(1, self.w // (bays * 3 + 2))
        bay_w = (self.w - column_w) // bays if bays > 0 else self.w

        # 1. 台基（平台）
        if platform_h > 0:
            self._fill(0, 0, 0, self.w - 1, platform_h - 1, self.l - 1, self.mat_wall)
            # 台基边缘装饰
            for z in range(self.l):
                self._set(0, platform_h - 1, z, self.mat_trim)
                self._set(self.w - 1, platform_h - 1, z, self.mat_trim)
            for x in range(self.w):
                self._set(x, platform_h - 1, 0, self.mat_trim)
                self._set(x, platform_h - 1, self.l - 1, self.mat_trim)
            # 台基上的栏杆柱
            for x in range(0, self.w, max(2, bay_w // 2)):
                for z in range(0, self.l, max(2, self.l - 1)):
                    self._set(x, platform_h, z, self.mat_accent)

        # 2. 多开间柱列
        pillar_top = self.h - (roof_tiers * (self.h - platform_h) // (roof_tiers + 1))
        for col_row in range(column_rows):
            z = col_row * (self.l - 1) // max(1, column_rows - 1) if column_rows > 1 else self.l // 2
            for bay_idx in range(bays + 1):
                x = bay_idx * bay_w
                if x >= self.w:
                    x = self.w - 1
                for y in range(platform_h, pillar_top):
                    self._set(x, y, z, self.mat_pillar)

        # 3. 柱顶横梁（阑额/普拍枋）
        beam_y = pillar_top - 1
        if beam_y > platform_h:
            for col_row in range(column_rows):
                z = col_row * (self.l - 1) // max(1, column_rows - 1) if column_rows > 1 else self.l // 2
                self._line_x(0, self.w - 1, beam_y, z, self.mat_trim)
                self._line_x(0, self.w - 1, beam_y + 1, z, self.mat_accent)

        # 4. 屋顶
        for tier in range(roof_tiers):
            tier_top = self.h - 1 - tier
            if tier_top < platform_h:
                break
            overhang = tier * 2
            x1 = max(0, overhang)
            z1 = max(0, overhang)
            x2 = self.w - 1 - overhang
            z2 = self.l - 1 - overhang
            if x1 > x2 or z1 > z2:
                break
            roof_y = tier_top - (tier * 2)
            if roof_y < platform_h:
                roof_y = platform_h + 1
            self._fill(x1, roof_y, z1, x2, roof_y, z2, self.mat_roof)
            # 屋顶边缘装饰（滴水瓦当）
            for x in range(x1, x2 + 1):
                self._set(x, roof_y, z1, self.mat_accent)
                self._set(x, roof_y, z2, self.mat_accent)
            for z in range(z1, z2 + 1):
                self._set(x1, roof_y, z, self.mat_accent)
                self._set(x2, roof_y, z, self.mat_accent)

        # 5. 门洞（底部中央清空）
        if bays > 0:
            center_bay = bays // 2
            door_x1 = center_bay * bay_w + column_w
            door_x2 = door_x1 + bay_w - column_w
            if door_x2 > self.w - 1:
                door_x2 = self.w - 1
            door_h = max(2, platform_h + (self.h - platform_h) // 3)
            for z in range(self.l):
                for x in range(door_x1, door_x2 + 1):
                    for y in range(platform_h, door_h):
                        self._set(x, y, z, MAT_AIR)

    # ─── 拱门 ───

    def _build_arch(self) -> None:
        pillar_w = max(2, self.w // 5)
        opening = self.w - 2 * pillar_w
        arch_top = max(3, self.h * 2 // 3)
        for z in range(self.l):
            for y in range(self.h):
                for x in range(self.w):
                    if x < pillar_w or x >= self.w - pillar_w:
                        self._set(x, y, z, self.mat_pillar)
                    elif y >= arch_top:
                        self._set(x, y, z, self.mat_wall)
        # 拱圈
        cx = self.w // 2
        r = opening // 2
        for z in range(self.l):
            for dx in range(-r, r + 1):
                dy = int(math.sqrt(max(0, r * r - dx * dx)))
                y = arch_top - dy
                if y >= 0:
                    self._set(cx + dx, y, z, self.mat_accent)

    # ─── 塔楼 ───

    def _build_tower(self) -> None:
        bw = min(self.w, self.l)
        for z in range(self.l):
            for y in range(self.h):
                for x in range(self.w):
                    # 外墙
                    if x == 0 or x == self.w - 1 or z == 0 or z == self.l - 1:
                        self._set(x, y, z, self.mat_wall)
                    # 角落柱
                    if (x == 0 or x == self.w - 1) and (z == 0 or z == self.l - 1):
                        self._set(x, y, z, self.mat_pillar)

        # 窗户 - 每面墙开窗
        spacing = self.style_cfg.get("window_spacing", 3)
        for y in range(2, self.h - 2, spacing):
            for z in range(2, self.l - 2, spacing):
                self._set(0, y, z, MAT_WINDOW)
                self._set(self.w - 1, y, z, MAT_WINDOW)
            for x in range(2, self.w - 2, spacing):
                self._set(x, y, 0, MAT_WINDOW)
                self._set(x, y, self.l - 1, MAT_WINDOW)

        # 楼层分割线
        for floor in range(1, self.floors):
            y = floor * (self.h // self.floors)
            for z in range(self.l):
                for x in range(self.w):
                    if x == 0 or x == self.w - 1 or z == 0 or z == self.l - 1:
                        self._set(x, y, z, self.mat_trim)

        # 屋顶雉堞（城垛）
        if self.w > 2 and self.l > 2:
            for cx in range(0, self.w, 2):
                for cz in range(0, self.l, 2):
                    if cx < self.w and cz < self.l:
                        self._set(cx, self.h - 1, cz, self.mat_accent)
                        if cz + 1 < self.l:
                            self._set(cx, self.h - 2, cz + 1, self.mat_roof)

    # ─── 塔 / 阁 ───

    def _build_pagoda(self) -> None:
        """中式塔楼：多层屋檐、每层内缩"""
        layers = max(3, self.floors * 2)
        h_per = self.h // layers
        for layer in range(layers):
            shrink = layer
            y1 = layer * h_per
            y2 = min(y1 + h_per - 1, self.h - 1)
            x1, z1 = shrink, shrink
            x2, z2 = self.w - 1 - shrink, self.l - 1 - shrink
            if x1 >= x2 or z1 >= z2:
                break
            for z in range(z1, z2 + 1):
                for y in range(y1, y2 + 1):
                    for x in range(x1, x2 + 1):
                        if x == x1 or x == x2 or z == z1 or z == z2:
                            self._set(x, y, z, self.mat_wall)
            # 每层檐
            if x1 > 0 and z1 > 0:
                overhang = 1
                for z in range(z1 - overhang, z2 + 1 + overhang):
                    for x in range(x1 - overhang, x2 + 1 + overhang):
                        if (x < x1 or x > x2 or z < z1 or z > z2) and y2 < self.h:
                            self._set(x, y2, z, self.mat_roof)

    # ─── 桥 ───

    def _build_bridge(self) -> None:
        mid = self.h // 2
        for z in range(self.l):
            for x in range(self.w):
                # 桥面
                self._set(x, mid, z, self.mat_floor)
                # 栏杆
                if x == 0 or x == self.w - 1:
                    for y in range(mid + 1, min(mid + 3, self.h)):
                        self._set(x, y, z, self.mat_pillar)
                # 桥拱
                if self.w > 3:
                    cx = self.w // 2
                    for dx in range(-(self.w // 3), self.w // 3 + 1):
                        y = mid - int(abs(dx) * 0.5)
                        if y >= 0:
                            self._set(cx + dx, y, z, self.mat_wall)

    # ─── 通用建筑 ───

    def _build_generic(self) -> None:
        spacing = self.style_cfg.get("window_spacing", 3)
        has_pillars = self.style_cfg.get("wall_pillar", False)
        has_trim = self.style_cfg.get("trim", True)
        has_windows = any(f.feature_type == "window" for f in self.desc.features)

        self._build_floor()

        wings = self._get_wings()
        for wing in wings:
            x1, z1, x2, z2 = wing
            self._build_wing_walls(x1, z1, x2, z2)
            if has_windows:
                self._build_wing_windows(x1, z1, x2, z2, spacing)
            if has_pillars:
                self._build_wing_pillars(x1, z1, x2, z2)
            if has_trim:
                self._build_wing_trim(x1, z1, x2, z2)

        if self.desc.facades:
            self._build_from_facades()
            return

        self._add_door()
        self._add_roof()
        self._add_support_columns()
        self._build_interior()
        self._apply_features_decorations()

    def _build_from_facades(self) -> None:
        """根据 AI 输出的逐面描述构建建筑（取代对称默认逻辑）。"""
        self._build_floor()
        facades = {f.face: f for f in self.desc.facades}
        for face_name in ("front", "back", "left", "right"):
            self._build_facade_wall(face_name, facades.get(face_name))
        for face_name in ("front", "back", "left", "right"):
            facade = facades.get(face_name)
            if facade:
                self._add_facade_windows(facade, face_name)
                self._add_facade_openings(facade, face_name)
                if facade.railings:
                    self._add_facade_railings(facade, face_name)
        self._add_roof()
        self._apply_features_decorations()

    def _face_fixed(self, face_name: str) -> int:
        return {"front": 0, "back": self.l - 1, "left": 0, "right": self.w - 1}[face_name]

    def _face_fixed_axis(self, face_name: str) -> str:
        return {"front": "z", "back": "z", "left": "x", "right": "x"}[face_name]

    def _face_span_max(self, face_name: str) -> int:
        return {"front": self.w - 1, "back": self.w - 1, "left": self.l - 1, "right": self.l - 1}[face_name]

    def _build_facade_wall(self, face_name: str, facade) -> None:
        """构建单个立面的实心墙（不含窗户/开口）。"""
        fixed = self._face_fixed(face_name)
        span_max = self._face_span_max(face_name)
        material = facade.material if (facade and facade.material) else self.mat_wall
        wy1, wy2 = 1, self.h - 2
        axis = self._face_fixed_axis(face_name)
        if axis == "z":
            for z in (fixed,):
                self._hollow_fill(0, wy1, z, span_max, wy2, z, material)
        else:
            for x in (fixed,):
                self._hollow_fill(x, wy1, 0, x, wy2, span_max, material)
        # 立柱
        if facade and facade.columns:
            for col_f in facade.columns:
                col_pos = int(col_f * span_max)
                if axis == "z":
                    for y in range(wy1, wy2 + 1):
                        self._set(col_pos, y, fixed, self.mat_pillar)
                else:
                    for y in range(wy1, wy2 + 1):
                        self._set(fixed, y, col_pos, self.mat_pillar)
        # 檐口线脚
        if facade and facade.cornice:
            if axis == "z":
                self._line_x(0, span_max, wy2 + 1, fixed, self.mat_trim)
            else:
                self._line_z(0, span_max, fixed, wy2 + 1, self.mat_trim)

    def _add_facade_windows(self, facade, face_name: str) -> None:
        """在立面上开窗。"""
        fixed = self._face_fixed(face_name)
        span_max = self._face_span_max(face_name)
        axis = self._face_fixed_axis(face_name)
        for win in facade.windows:
            wx = int(win.x * span_max)
            if wx < 1 or wx >= span_max:
                continue
            for dy in range(win.height):
                wy = win.y_offset + dy
                if wy >= self.h - 1:
                    break
                if axis == "z":
                    self._set(wx, wy, fixed, MAT_WINDOW)
                else:
                    self._set(fixed, wy, wx, MAT_WINDOW)

    def _add_facade_openings(self, facade, face_name: str) -> None:
        """在立面上开门洞/拱门。"""
        fixed = self._face_fixed(face_name)
        span_max = self._face_span_max(face_name)
        axis = self._face_fixed_axis(face_name)
        for opening in facade.openings:
            ox = int(opening.x * span_max)
            ow = max(1, int(opening.width * span_max))
            ox1 = max(0, ox - ow // 2)
            ox2 = min(span_max, ox + ow // 2)
            for oy in range(opening.height):
                if oy >= self.h:
                    break
                for oxx in range(ox1, ox2 + 1):
                    if axis == "z":
                        self._set(oxx, oy, fixed, MAT_AIR)
                    else:
                        self._set(fixed, oy, oxx, MAT_AIR)
            # 拱门样式
            if opening.style == "arch":
                r = ow // 2
                for dx in range(-r, r + 1):
                    dy = int(math.sqrt(max(0, r * r - dx * dx)))
                    ay = opening.height - dy
                    ax = ox + dx
                    if axis == "z":
                        self._set(ax, ay, fixed, self.mat_accent)
                    else:
                        self._set(fixed, ay, ax, self.mat_accent)

    def _add_facade_railings(self, facade, face_name: str) -> None:
        """在立面上加栏杆。"""
        fixed = self._face_fixed(face_name)
        span_max = self._face_span_max(face_name)
        axis = self._face_fixed_axis(face_name)
        rail_y = self.h // 2
        step = max(2, span_max // 6)
        for i in range(0, span_max + 1, step):
            if axis == "z":
                self._set(i, rail_y, fixed, self.mat_accent)
                self._set(i, rail_y + 1, fixed, self.mat_trim)
            else:
                self._set(fixed, rail_y, i, self.mat_accent)
                self._set(fixed, rail_y + 1, i, self.mat_trim)

    # ── 墙壁 ──

    def _build_wing_walls(self, wx1: int, wz1: int, wx2: int, wz2: int) -> None:
        wy1, wy2 = 1, self.h - 2
        for z in (wz1, wz2):
            self._hollow_fill(wx1, wy1, z, wx2, wy2, z, self.mat_wall)
        for x in (wx1, wx2):
            self._hollow_fill(x, wy1, wz1 + 1, x, wy2, wz2 - 1, self.mat_wall)

    def _build_wing_windows(self, wx1: int, wz1: int, wx2: int, wz2: int, spacing: int) -> None:
        win_h = min(2, self.h // self.floors - 1)
        count = max(1, (wx2 - wx1) // spacing)
        for i in range(count):
            x = wx1 + 1 + (i + 1) * (wx2 - wx1 - 2) // (count + 2)
            for f in range(self.floors):
                yb = 1 + f * (self.h // self.floors)
                for dy in range(win_h):
                    self._set(x, yb + dy, wz1, MAT_WINDOW)
                    self._set(x, yb + dy, wz2, MAT_WINDOW)
        side_count = max(1, (wz2 - wz1) // spacing)
        for i in range(side_count):
            z = wz1 + 1 + (i + 1) * (wz2 - wz1 - 2) // (side_count + 2)
            for f in range(self.floors):
                yb = 1 + f * (self.h // self.floors)
                for dy in range(win_h):
                    self._set(wx1, yb + dy, z, MAT_WINDOW)
                    self._set(wx2, yb + dy, z, MAT_WINDOW)

    def _build_wing_pillars(self, wx1: int, wz1: int, wx2: int, wz2: int) -> None:
        wy2 = self.h - 2
        for cx, cz in [(wx1, wz1), (wx2, wz1), (wx1, wz2), (wx2, wz2)]:
            for y in range(1, wy2 + 1):
                self._set(cx, y, cz, self.mat_pillar)

    def _build_wing_trim(self, wx1: int, wz1: int, wx2: int, wz2: int) -> None:
        for floor in range(1, self.floors):
            y = floor * (self.h // self.floors)
            for z in range(wz1, wz2 + 1):
                for x in range(wx1, wx2 + 1):
                    if x == wx1 or x == wx2 or z == wz1 or z == wz2:
                        self._set(x, y, z, self.mat_trim)

    # ── 门 ──

    def _add_door(self) -> None:
        has_door = any(f.feature_type == "door" for f in self.desc.features)
        if not has_door:
            return
        dx = self.w // 2 - 1
        for dy in range(2):
            for dw in range(2):
                self._set(dx + dw, 1 + dy, 0, MAT_AIR)

    # ── 屋顶 ──

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
        elif rt == "xieshan":
            self._add_xieshan_roof()
        elif rt == "curved":
            self._add_curved_roof()
        elif rt == "eaved":
            self._add_eaved_roof()
        else:
            self._add_flat_roof()

    def _add_flat_roof(self) -> None:
        self._fill(0, self.h - 1, 0, self.w - 1, self.h - 1, self.l - 1, self.mat_roof)
        for x in range(self.w):
            self._set(x, self.h - 1, 0, self.mat_accent)
            self._set(x, self.h - 1, self.l - 1, self.mat_accent)
        for z in range(self.l):
            self._set(0, self.h - 1, z, self.mat_accent)
            self._set(self.w - 1, self.h - 1, z, self.mat_accent)

    def _add_gable_roof(self) -> None:
        half = self.l // 2
        for z in range(self.l):
            dist = abs(z - half)
            rise = max(0, half - dist)
            ty = self.h - 1 + rise
            if ty >= self.h:
                continue
            for x in range(self.w):
                self._set(x, ty, z, self.mat_roof)

    def _add_hip_roof(self) -> None:
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
                    self._set(x, y, z, self.mat_roof)

    def _add_pyramid_roof(self) -> None:
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
                    self._set(x, y, z, self.mat_roof)
            if x1 == x2 and z1 == z2:
                self._set(x1, y, z1, self.mat_accent)

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
                    self._set(x, y, z, self.mat_roof)
                    for fy in range(base_y + 1, y):
                        self._set(x, fy, z, self.mat_roof)
        tx, tz = cx, cz
        ty = base_y + r
        if ty < self.h:
            self._set(tx, ty, tz, self.mat_accent)

    def _add_xieshan_roof(self) -> None:
        """歇山顶：山花 + 四坡结合的混合式屋顶。"""
        half = self.l // 2
        hip_depth = self.l // 4
        for z in range(self.l):
            dist = abs(z - half)
            if dist <= hip_depth:
                rise = self.w // 4
                level = int(rise * (1 - dist / hip_depth))
                for x in range(level, self.w - level):
                    self._set(x, self.h - 1, z, self.mat_roof)
                for x in range(level):
                    rel_x = x
                    for dz in range(-1, 2):
                        if 0 <= z + dz < self.l:
                            self._set(rel_x, self.h - 1, z + dz, self.mat_roof)
                            self._set(self.w - 1 - rel_x, self.h - 1, z + dz, self.mat_roof)
            else:
                ridge = max(1, self.w - 2 * (dist - hip_depth))
                x1 = (self.w - ridge) // 2
                for x in range(x1, x1 + ridge):
                    self._set(x, self.h - 1, z, self.mat_roof)
        # 正脊（顶部中脊线）
        ridge_y = self.h - 1
        for x in range(1, self.w - 1):
            self._set(x, ridge_y, half, self.mat_accent)

    def _add_curved_roof(self) -> None:
        """卷棚顶式曲面屋顶：类似中式弧线屋顶。"""
        half = self.l // 2
        curve = max(1, self.l // 6)
        for z in range(self.l):
            dist = abs(z - half)
            offset = int(curve * math.sin(math.pi * dist / half)) if half > 0 else 0
            shrink = int(dist * 0.3)
            x1 = shrink
            x2 = self.w - 1 - shrink
            for x in range(x1, x2 + 1):
                ty = self.h - 1 + offset
                if ty < self.h:
                    self._set(x, ty, z, self.mat_roof)

    def _add_eaved_roof(self) -> None:
        """重檐风格：多层屋檐出挑。"""
        tiers = self.desc.roof_tiers or 2
        for tier in range(tiers):
            y = self.h - 1 - tier * (self.h // (tiers + 1))
            if y < self.h // 3:
                break
            overhang = tier + 1
            x1 = max(0, overhang)
            z1 = max(0, overhang)
            x2 = self.w - 1 - overhang
            z2 = self.l - 1 - overhang
            if x1 > x2 or z1 > z2:
                break
            self._fill(x1, y, z1, x2, y, z2, self.mat_roof)
            for x in range(x1, x2 + 1):
                self._set(x, y, z1, self.mat_accent)
                self._set(x, y, z2, self.mat_accent)
            for z in range(z1, z2 + 1):
                self._set(x1, y, z, self.mat_accent)
                self._set(x2, y, z, self.mat_accent)

    # ── 支撑柱 ──

    def _add_support_columns(self) -> None:
        if self.w < 6 or self.l < 6:
            return
        cx, cz = self.w // 2, self.l // 2
        for y in range(1, self.h - 2):
            for dx, dz in [(0, 0), (1, 0), (0, 1), (1, 1)]:
                self._set(cx + dx, y, cz + dz, self.mat_pillar)

    # ── 内部结构 ──

    def _build_interior(self) -> None:
        """根据 AI 特征创建内部结构（楼梯、隔墙、家具）。"""
        has_stairs = any(f.feature_type == "stairs" for f in self.desc.features)
        if has_stairs:
            self._add_stairs()

        has_rooms = any(f.feature_type == "room" for f in self.desc.features)
        if has_rooms:
            self._add_room_partitions()

        has_furniture = any(f.feature_type == "furniture" for f in self.desc.features)
        if has_furniture:
            self._add_furniture()

    def _add_stairs(self) -> None:
        """在建筑内部一侧添加楼梯。"""
        if self.floors <= 1 or self.h < 6 or self.w < 4:
            return
        stair_x = max(1, self.w - 3)
        stair_z = 1
        for floor in range(self.floors - 1):
            y_base = 1 + floor * (self.h // self.floors)
            for step in range(min(4, self.h // self.floors - 1)):
                for dx in range(2):
                    for dz in range(step + 1):
                        z = stair_z + dz
                        if z < self.l - 1:
                            self._set(stair_x + dx, y_base + step, z, self.mat_floor)

    def _add_room_partitions(self) -> None:
        """在建筑内添加隔墙（中心十字墙）。"""
        if self.w < 5 or self.l < 5 or self.h < 3:
            return
        cx, cz = self.w // 2, self.l // 2
        for y in range(1, self.h - 2):
            for x in range(self.w):
                if abs(x - cx) <= 0:
                    self._set(x, y, cz, self.mat_wall)
            for z in range(self.l):
                if abs(z - cz) <= 0:
                    self._set(cx, y, z, self.mat_wall)

    def _add_furniture(self) -> None:
        """在建筑内添加简单家具（桌子、椅子、书架）。"""
        cx, cz = self.w // 2, self.l // 2
        table_y = 1
        for dx in range(2):
            for dz in range(2):
                self._set(cx + dx, table_y, cz + dz, self.mat_floor)
        self._set(cx, table_y + 1, cz, self.mat_accent)

    # ── 装饰特征 ──

    def _apply_features_decorations(self) -> None:
        for f in self.desc.features:
            ft = f.feature_type
            if ft == "column" or ft == "pillar":
                self._decorate_pillar(f)
            elif ft == "arch":
                self._decorate_arch(f)
            elif ft == "balcony":
                self._decorate_balcony(f)
            elif ft == "tower":
                self._decorate_turret(f)

    def _decorate_pillar(self, feature) -> None:
        pos = feature.position or "front"
        count = min(feature.count, 4)
        step = max(2, self.w // (count + 1))
        for i in range(count):
            x = (i + 1) * step
            if x >= self.w - 1:
                x = self.w - 2
            z = 0 if pos in ("front", "center") else self.l - 1
            for y in range(1, min(self.h - 2, 6)):
                self._set(x, y, z, self.mat_accent)

    def _decorate_arch(self, feature) -> None:
        cx = self.w // 2
        r = min(self.w, self.l) // 4
        z = 0
        for dx in range(-r, r + 1):
            dy = int(math.sqrt(max(0, r * r - dx * dx)))
            for dz in range(min(2, self.l)):
                y = self.h // 2
                self._set(cx + dx, y + dy, dz, self.mat_accent)

    def _decorate_balcony(self, feature) -> None:
        y = self.h // 2
        for x in range(1, self.w - 1):
            self._set(x, y, 0, self.mat_floor)
            self._set(x, y + 1, 0, self.mat_accent)

    def _decorate_turret(self, feature) -> None:
        for dz in range(min(2, self.l)):
            for dx in range(min(2, self.w)):
                cx = self.w - 1 - dx
                cz = self.l - 1 - dz
                for y in range(self.h - 3, self.h):
                    self._set(cx, y, cz, self.mat_pillar)

    # ── 翼板 ──

    def _get_wings(self) -> list[tuple[int, int, int, int]]:
        shape = self.shape
        if shape == "L":
            mw = self.w // 2
            ml = self.l * 2 // 3
            return [(0, 0, self.w - 1, ml - 1), (0, 0, mw - 1, self.l - 1)]
        elif shape == "cross":
            cw = self.w // 3
            cl = self.l // 3
            return [(0, cl, self.w - 1, self.l - 1 - cl), (cw, 0, self.w - 1 - cw, self.l - 1)]
        elif shape == "T":
            tw = self.w * 2 // 3
            tl = self.l // 3
            return [(0, tl, self.w - 1, self.l - 1), ((self.w - tw) // 2, 0, (self.w - tw) // 2 + tw - 1, tl - 1)]
        else:
            return [(0, 0, self.w - 1, self.l - 1)]
