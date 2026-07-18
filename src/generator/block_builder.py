"""V2 方块生成器 —— 按 BuildingDSL 的 component 级几何渲染。

取代旧 BlockBuilder（按 building_type 分发 + facade 对称逻辑）。
新设计：
  1. 接受 BuildingDSL（V2 schema）
  2. build() 按 components 列表逐个渲染（每个 component 用 geometry.py 纯函数）
  3. 再叠加 roof / walls / windows / entrance / curves
  4. 输出 BlockStructure（NBT exporter 不变）

保留：BlockStructure 类、BlockMap 集成、grid 约定 [z][y][x]
"""
from __future__ import annotations

import math
import warnings

from src.generator.block_map import BlockMap
from src.generator.geometry import (
    generate_arch,
    generate_box,
    generate_cone,
    generate_curve,
    generate_cylinder,
    generate_prism,
    generate_sphere,
    rotate_y,
)
from src.models.building import BuildingDSL, Component


# Minecraft 1.20+ /place template 命令支持最大 128×128×128
MAX_STRUCTURE_BLOCK = 128
STRUCTURE_BLOCK_LIMIT = 48  # 结构方块上限，仅用于提示


class BlockStructure:
    """生成结果 —— 与 NBT exporter 接口不变。"""

    def __init__(self, palette: list[str], blocks: list[int],
                 size_x: int, size_y: int, size_z: int) -> None:
        self.palette = palette
        self.blocks = blocks
        self.size_x = size_x
        self.size_y = size_y
        self.size_z = size_z


class BlockBuilder:
    """V2 生成器：BuildingDSL → BlockStructure。

    按 component 级几何渲染，每个 component 用 geometry.py 纯函数生成基础几何，
    再叠加 roof/walls/windows/entrance/curves 子系统。
    """

    def __init__(self, description: BuildingDSL) -> None:
        self.desc = description
        self.block_map = BlockMap(description.minecraft_version)

        scale = max(1, description.detail_scale)
        self.w = min(description.width * scale, MAX_STRUCTURE_BLOCK)
        self.h = min(description.height * scale, MAX_STRUCTURE_BLOCK)
        self.l = min(description.length * scale, MAX_STRUCTURE_BLOCK)

        if self.w > STRUCTURE_BLOCK_LIMIT or self.h > STRUCTURE_BLOCK_LIMIT or self.l > STRUCTURE_BLOCK_LIMIT:
            warnings.warn(
                f"结构({self.w}x{self.h}x{self.l})超出结构方块上限({STRUCTURE_BLOCK_LIMIT}^3)，"
                f"请用 /place template 命令放置"
            )

        # ── 全局部位材质（从 DSL 直接取，已有默认值）──
        self.mat_wall = description.wall_material
        self.mat_roof = description.roof_material
        self.mat_door = description.door_material
        self.mat_window = description.window_glass_material
        self.mat_pillar = description.pillar_material
        self.mat_trim = description.trim_material
        self.mat_railing = description.railing_material
        self.mat_cornice = description.cornice_material
        self.mat_platform = description.platform_material
        self.mat_foundation = description.foundation_material

        self._grid: list[list[list[int]]] = []
        self._block_to_idx: dict[str, int] = {}
        self._palette_list: list[str] = []

    # ── 方块索引管理 ──

    def _resolve(self, material_name: str) -> str:
        return self.block_map.get_block_id(material_name)

    def _idx(self, material_name: str) -> int:
        bid = self._resolve(material_name)
        if bid not in self._block_to_idx:
            self._block_to_idx[bid] = len(self._palette_list)
            self._palette_list.append(bid)
        return self._block_to_idx[bid]

    def _set(self, x: int, y: int, z: int, mat: str) -> None:
        """grid setter —— 兼容 geometry.py 的 GridSetter 签名。"""
        if 0 <= x < self.w and 0 <= y < self.h and 0 <= z < self.l:
            self._grid[z][y][x] = self._idx(mat)

    # ═══════════════════════════════════════════════════════════════
    #  主入口
    # ═══════════════════════════════════════════════════════════════

    def build(self) -> BlockStructure:
        """按 BuildingDSL 渲染建筑。"""
        # 初始化 air grid
        air_idx = self._idx("air")
        self._grid = [
            [[air_idx for _ in range(self.w)] for _ in range(self.h)]
            for _ in range(self.l)
        ]

        # 1. 渲染所有 components（主体/侧翼/塔楼/屋顶/入口/阳台等）
        for comp in self.desc.components:
            self._render_component(comp)

        # 2. 如果没 components，至少画一个主体 box（fallback）
        if not self.desc.components:
            self._render_main_body_fallback()

        # 3. 渲染屋顶
        self._render_roof()

        # 4. 渲染墙体（覆盖 components 的墙，加柱子/扶壁等）
        for wall in self.desc.walls:
            self._render_wall(wall)

        # 5. 渲染窗户
        self._render_windows()

        # 6. 渲染入口
        self._render_entrance()

        # 7. 渲染曲线结构（圆塔/穹顶/拱/飞檐等独立几何）
        for curve in self.desc.curves:
            self._render_curve(curve)

        # 8. 平铺到一维
        flat: list[int] = []
        for z in range(self.l):
            for y in range(self.h):
                for x in range(self.w):
                    flat.append(self._grid[z][y][x])

        return BlockStructure(
            palette=self._palette_list,
            blocks=flat,
            size_x=self.w, size_y=self.h, size_z=self.l,
        )

    # ═══════════════════════════════════════════════════════════════
    #  Component 渲染（按 shape 分发到 geometry.py）
    # ═══════════════════════════════════════════════════════════════

    def _resolve_position(self, position: str, comp_w: int, comp_l: int) -> tuple[int, int]:
        """把 position 标签解析为 (x_offset, z_offset)。"""
        cx = (self.w - comp_w) // 2
        cz = (self.l - comp_l) // 2
        offsets = {
            "center": (cx, cz),
            "front": (cx, 0),
            "back": (cx, self.l - comp_l),
            "left": (0, cz),
            "right": (self.w - comp_w, cz),
            "front_left_corner": (0, 0),
            "front_right_corner": (self.w - comp_w, 0),
            "back_left_corner": (0, self.l - comp_l),
            "back_right_corner": (self.w - comp_w, self.l - comp_l),
            "top": (cx, cz),
        }
        return offsets.get(position, (cx, cz))

    def _render_component(self, comp: Component) -> None:
        """按 component.shape 分发到 geometry.py 纯函数。"""
        mat = comp.material or self.mat_wall
        # cylinder/sphere/cone 用 radius 推尺寸，box/prism 用 width/length
        if comp.shape in ("cylinder", "sphere", "cone"):
            eff_w = max(1, comp.radius * 2)
            eff_l = max(1, comp.radius * 2)
        else:
            eff_w = max(1, comp.width)
            eff_l = max(1, comp.length)
        ox, oz = self._resolve_position(comp.position, eff_w, eff_l)
        ox += comp.offset_x
        oz += comp.offset_z
        oy = comp.offset_y

        shape = comp.shape
        if shape == "box":
            w = max(1, comp.width)
            l = max(1, comp.length)
            h = max(1, comp.height)
            generate_box(self._set, ox, oy, oz, ox + w - 1, oy + h - 1, oz + l - 1,
                         mat, hollow=False, w=self.w, h=self.h, l=self.l)
        elif shape == "cylinder":
            r = max(1, comp.radius)
            h = max(1, comp.height)
            cx = ox + r
            cz = oz + r
            generate_cylinder(self._set, cx, cz, r, oy, oy + h - 1,
                              mat, hollow=False, w=self.w, h=self.h, l=self.l)
        elif shape == "sphere":
            r = max(1, comp.radius)
            cx = ox + r
            cy = oy + r
            cz = oz + r
            generate_sphere(self._set, cx, cy, cz, r, mat,
                            half_or_full="full", hollow=False,
                            w=self.w, h=self.h, l=self.l)
        elif shape == "cone":
            r = max(1, comp.radius)
            h = max(1, comp.height)
            cx = ox + r
            cz = oz + r
            generate_cone(self._set, cx, cz, r, h, mat,
                          hollow=False, w=self.w, h=self.h, l=self.l)
        elif shape == "prism":
            w = max(1, comp.width)
            l = max(1, comp.length)
            h = max(1, comp.height)
            generate_prism(self._set, ox, oy, oz, ox + w - 1, oy + h - 1, oz + l - 1,
                           mat, taper_axis="y", w=self.w, h=self.h, l=self.l)
        elif shape == "arch":
            w = max(1, comp.width)
            h = max(1, comp.height)
            cx = ox + w // 2
            generate_arch(self._set, cx, oz, w, h, mat,
                          arch_type="semicircle", curvature=1.0,
                          w=self.w, h=self.h, l=self.l)
        elif shape == "curve":
            x2 = ox + max(1, comp.width) - 1
            y2 = oy + max(1, comp.height) - 1
            z2 = oz + max(1, comp.length) - 1
            generate_curve(self._set, ox, oy, oz, x2, y2, z2, mat,
                           direction="up", curvature=0.5,
                           w=self.w, h=self.h, l=self.l)
        # custom 类型不处理（由 curves 列表单独渲染）

    def _render_main_body_fallback(self) -> None:
        """无 components 时画一个主体 box。"""
        generate_box(self._set, 0, 0, 0, self.w - 1, self.h - 1, self.l - 1,
                     self.mat_wall, hollow=False,
                     w=self.w, h=self.h, l=self.l)

    # ═══════════════════════════════════════════════════════════════
    #  屋顶渲染
    # ═══════════════════════════════════════════════════════════════

    def _render_roof(self) -> None:
        """按 roof.type 渲染屋顶。"""
        roof = self.desc.roof
        mat = roof.material or self.mat_roof
        rt = roof.type
        rh = max(1, roof.height) if roof.height else max(1, self.h // 4)
        overhang = roof.overhang

        if rt == "flat":
            self._render_flat_roof(mat)
        elif rt == "gable":
            self._render_gable_roof(mat, rh)
        elif rt == "hip":
            self._render_hip_roof(mat, rh)
        elif rt == "pyramid":
            self._render_pyramid_roof(mat, rh)
        elif rt == "dome":
            self._render_dome_roof(mat, rh)
        elif rt == "mansard":
            self._render_mansard_roof(mat, rh)
        elif rt == "barrel":
            self._render_barrel_roof(mat, rh)
        elif rt == "spire":
            self._render_spire_roof(mat, rh)
        elif rt in ("chinese_roof", "xieshan", "curved", "eaved"):
            self._render_chinese_roof(mat, rh, roof)
        else:
            self._render_flat_roof(mat)

    def _render_flat_roof(self, mat: str) -> None:
        generate_box(self._set, 0, self.h - 1, 0, self.w - 1, self.h - 1, self.l - 1,
                     mat, w=self.w, h=self.h, l=self.l)

    def _render_gable_roof(self, mat: str, rh: int) -> None:
        half = self.l // 2
        for z in range(self.l):
            dist = abs(z - half)
            rise = max(0, half - dist)
            ty = self.h - 1 + rise
            if ty < self.h:
                for x in range(self.w):
                    self._set(x, ty, z, mat)

    def _render_hip_roof(self, mat: str, rh: int) -> None:
        cx, cz = self.w // 2, self.l // 2
        max_rise = min(cx, cz, rh)
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
                    self._set(x, y, z, mat)

    def _render_pyramid_roof(self, mat: str, rh: int) -> None:
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
                    self._set(x, y, z, mat)

    def _render_dome_roof(self, mat: str, rh: int) -> None:
        cx, cz = self.w // 2, self.l // 2
        r = min(self.w, self.l) // 2
        cy = self.h - 1
        generate_sphere(self._set, cx, cy, cz, r, mat,
                        half_or_full="half", hollow=False,
                        w=self.w, h=self.h, l=self.l)

    def _render_mansard_roof(self, mat: str, rh: int) -> None:
        """曼萨德式屋顶：下部陡坡，上部缓坡（双折）。"""
        lower_h = rh // 2
        upper_h = rh - lower_h
        # 下部陡坡：从墙顶向外扩 1 格
        for y in range(lower_h):
            yy = self.h - 1 + y
            if yy >= self.h:
                break
            shrink = y
            x1, z1 = shrink, shrink
            x2, z2 = self.w - 1 - shrink, self.l - 1 - shrink
            if x1 > x2:
                break
            for x in range(x1, x2 + 1):
                for z in range(z1, z2 + 1):
                    self._set(x, yy, z, mat)
        # 上部缓坡：缓收缩
        base_y = self.h - 1 + lower_h
        for y in range(upper_h):
            yy = base_y + y
            if yy >= self.h:
                break
            shrink = lower_h + y * 2
            x1, z1 = shrink, shrink
            x2, z2 = self.w - 1 - shrink, self.l - 1 - shrink
            if x1 > x2:
                break
            for x in range(x1, x2 + 1):
                for z in range(z1, z2 + 1):
                    self._set(x, yy, z, mat)

    def _render_barrel_roof(self, mat: str, rh: int) -> None:
        """筒形屋顶：沿一个方向的半圆柱。"""
        cx = self.w // 2
        r = min(self.w // 2, rh)
        for z in range(self.l):
            for dx in range(-r, r + 1):
                dy = int(math.sqrt(max(0, r * r - dx * dx)))
                y = self.h - 1 + (rh - dy)
                if y < self.h:
                    self._set(cx + dx, y, z, mat)

    def _render_spire_roof(self, mat: str, rh: int) -> None:
        """哥特尖塔：圆锥。"""
        cx, cz = self.w // 2, self.l // 2
        r = min(self.w, self.l) // 2
        generate_cone(self._set, cx, cz, r, rh, mat,
                      hollow=False, w=self.w, h=self.h, l=self.l)

    def _render_chinese_roof(self, mat: str, rh: int, roof) -> None:
        """中式屋顶：四坡顶 + 飞檐翘角 + 屋脊。"""
        # 基础四坡
        self._render_hip_roof(mat, rh)
        # 飞檐翘角：四角向上翘起
        if roof.has_flying_eaves:
            eaves_y = self.h - 1 + rh
            corners = [(0, 0), (self.w - 1, 0), (0, self.l - 1), (self.w - 1, self.l - 1)]
            for cx, cz in corners:
                # 翘起方块
                for dy in range(1, int(3 * roof.eaves_curvature) + 1):
                    if eaves_y + dy < self.h:
                        self._set(cx, eaves_y + dy, cz, mat)
        # 屋脊（正脊）：顶部中脊线
        ridge_y = self.h - 1 + rh - 1
        if ridge_y < self.h:
            half_z = self.l // 2
            for x in range(1, self.w - 1):
                self._set(x, ridge_y, half_z, mat)
        # 重檐：多层屋檐
        if roof.layer_count > 1:
            for tier in range(1, roof.layer_count):
                tier_y = self.h - 1 - tier * (self.h // (roof.layer_count + 1))
                if tier_y > 0:
                    overhang = tier
                    x1, z1 = overhang, overhang
                    x2, z2 = self.w - 1 - overhang, self.l - 1 - overhang
                    if x1 < x2 and z1 < z2:
                        generate_box(self._set, x1, tier_y, z1, x2, tier_y, z2,
                                     mat, w=self.w, h=self.h, l=self.l)

    # ═══════════════════════════════════════════════════════════════
    #  墙体渲染
    # ═══════════════════════════════════════════════════════════════

    def _render_wall(self, wall) -> None:
        """渲染墙体（加柱子/扶壁等）。"""
        mat = wall.material or self.mat_wall
        # 墙体本身由 component box 的外壳覆盖，这里主要加柱子/扶壁
        if wall.type in ("pillar", "pilaster"):
            self._render_pillars(wall.pillars, mat)
        elif wall.type == "buttress":
            self._render_buttresses(wall.pillars, mat)
        elif wall.type == "arcade":
            self._render_arcade(wall.pillars, mat)

    def _render_pillars(self, pillars, mat: str) -> None:
        """渲染柱列。"""
        if pillars.count == 0:
            return
        pmat = pillars.material or self.mat_pillar
        spacing = max(1, pillars.spacing)
        # 沿正面均匀分布
        total_span = self.w - 2
        for i in range(pillars.count):
            x = 1 + (i * total_span) // max(1, pillars.count - 1) if pillars.count > 1 else self.w // 2
            for y in range(1, self.h - 1):
                for dx in range(pillars.width):
                    self._set(x + dx, y, 0, pmat)
                    self._set(x + dx, y, self.l - 1, pmat)

    def _render_buttresses(self, pillars, mat: str) -> None:
        """渲染扶壁（凸出墙面的支撑柱）。"""
        if pillars.count == 0:
            return
        pmat = pillars.material or self.mat_pillar
        protrusion = max(1, pillars.protrusion)
        for i in range(pillars.count):
            x = 1 + (i * (self.w - 2)) // max(1, pillars.count - 1) if pillars.count > 1 else self.w // 2
            for y in range(1, self.h - 1):
                for dz in range(protrusion):
                    self._set(x, y, -1 - dz if False else max(0, -dz), mat)
                    # 扶壁在墙外侧，但边界保护会忽略负值，改在内侧
                    self._set(x, y, 0, pmat)
                    self._set(x, y, self.l - 1, pmat)

    def _render_arcade(self, pillars, mat: str) -> None:
        """渲染券柱式（柱 + 拱）。"""
        if pillars.count == 0:
            return
        pmat = pillars.material or self.mat_pillar
        spacing = max(1, pillars.spacing)
        # 柱子
        for i in range(pillars.count):
            x = 1 + i * spacing
            if x >= self.w - 1:
                break
            for y in range(1, self.h - 1):
                self._set(x, y, 0, pmat)
        # 柱间拱
        for i in range(pillars.count - 1):
            x1 = 1 + i * spacing
            x2 = 1 + (i + 1) * spacing
            cx = (x1 + x2) // 2
            arch_w = x2 - x1
            arch_h = min(arch_w // 2, self.h // 3)
            generate_arch(self._set, cx, 0, arch_w, arch_h, pmat,
                          arch_type="semicircle", curvature=1.0,
                          w=self.w, h=self.h, l=self.l)

    # ═══════════════════════════════════════════════════════════════
    #  窗户渲染
    # ═══════════════════════════════════════════════════════════════

    def _render_windows(self) -> None:
        """渲染窗户系统。"""
        ws = self.desc.windows
        for win in ws.items:
            self._render_window_item(win)

    def _render_window_item(self, win) -> None:
        """渲染单个窗户（含重复排列）。"""
        glass = win.glass_material or self.mat_window
        frame = win.frame_material or self.mat_trim
        side = win.side
        # 立面对应的 fixed 坐标
        fixed = {"front": 0, "back": self.l - 1, "left": 0, "right": self.w - 1}.get(side, 0)
        span_max = {"front": self.w - 1, "back": self.w - 1, "left": self.l - 1, "right": self.l - 1}.get(side, self.w - 1)
        axis = "z" if side in ("front", "back") else "x"

        wx_base = int(win.x * span_max)
        y_offset = win.y_offset + (win.floor - 1) * self.desc.floor_height
        for rep in range(win.count):
            wx = wx_base + rep * win.spacing
            if wx < 1 or wx > span_max:
                continue
            # 玻璃
            for dy in range(win.height):
                wy = y_offset + dy
                if wy >= self.h - 1:
                    break
                if axis == "z":
                    self._set(wx, wy, fixed, glass)
                    if wx > 0:
                        self._set(wx - 1, wy, fixed, frame)
                    if wx < span_max:
                        self._set(wx + 1, wy, fixed, frame)
                else:
                    self._set(fixed, wy, wx, glass)
                    if wx > 0:
                        self._set(fixed, wy, wx - 1, frame)
                    if wx < span_max:
                        self._set(fixed, wy, wx + 1, frame)
            # 拱形窗顶
            if win.shape in ("arch", "pointed_arch"):
                arch_type = "pointed" if win.shape == "pointed_arch" else "semicircle"
                r = max(1, int(win.width * span_max / 2))
                for dx in range(-r, r + 1):
                    dy = int(math.sqrt(max(0, r * r - dx * dx)))
                    ay = y_offset + win.height - 1 + dy
                    if 0 <= ay < self.h - 1:
                        if axis == "z":
                            self._set(wx + dx, ay, fixed, frame)
                        else:
                            self._set(fixed, ay, wx + dx, frame)
            elif win.shape == "circle":
                r = max(1, win.height // 2)
                cy = y_offset + win.height // 2
                for dx in range(-r, r + 1):
                    dy = int(math.sqrt(max(0, r * r - dx * dx)))
                    for ay in (cy - dy, cy + dy):
                        if 0 <= ay < self.h - 1:
                            if axis == "z":
                                self._set(wx + dx, ay, fixed, frame)
                            else:
                                self._set(fixed, ay, wx + dx, frame)

    # ═══════════════════════════════════════════════════════════════
    #  入口渲染
    # ═══════════════════════════════════════════════════════════════

    def _render_entrance(self) -> None:
        """渲染入口系统。"""
        ent = self.desc.entrance
        if ent.width == 0 or ent.height == 0:
            return
        side = ent.side
        fixed = {"front": 0, "back": self.l - 1, "left": 0, "right": self.w - 1}.get(side, 0)
        span_max = {"front": self.w - 1, "back": self.w - 1, "left": self.l - 1, "right": self.l - 1}.get(side, self.w - 1)
        axis = "z" if side in ("front", "back") else "x"
        door_mat = ent.door_material or self.mat_door
        frame_mat = ent.frame_material or self.mat_trim

        ex = int(ent.position == "left") * (span_max // 4) if ent.position != "center" else span_max // 2
        ex_center = span_max // 2 if ent.position == "center" else (span_max // 4 if ent.position == "left" else 3 * span_max // 4)
        ow = ent.width
        ex1 = max(0, ex_center - ow // 2)
        ex2 = min(span_max, ex_center + ow // 2)

        # 门洞（空气）
        for oy in range(ent.height):
            if oy >= self.h:
                break
            for oxx in range(ex1, ex2 + 1):
                if axis == "z":
                    self._set(oxx, oy, fixed, "air")
                else:
                    self._set(fixed, oy, oxx, "air")
            # 门框两侧
            if axis == "z":
                if ex1 > 0:
                    self._set(ex1 - 1, oy, fixed, frame_mat)
                if ex2 < span_max:
                    self._set(ex2 + 1, oy, fixed, frame_mat)
            else:
                if ex1 > 0:
                    self._set(fixed, oy, ex1 - 1, frame_mat)
                if ex2 < span_max:
                    self._set(fixed, oy, ex2 + 1, frame_mat)

        # 拱形门顶
        if ent.type in ("arch", "portal") or ent.curvature > 0:
            arch_type = "semicircle"
            generate_arch(self._set, ex_center, fixed, ow, ent.height, frame_mat,
                          arch_type=arch_type, curvature=ent.curvature,
                          w=self.w, h=self.h, l=self.l)

        # 门板（在门洞底部放一行门方块）
        if door_mat:
            for oxx in range(ex1, ex2 + 1):
                if axis == "z":
                    self._set(oxx, 0, fixed, door_mat)
                else:
                    self._set(fixed, 0, oxx, door_mat)

        # 台阶
        if ent.has_stairs and ent.stair_count > 0:
            for step in range(ent.stair_count):
                sy = ent.stair_count - step - 1
                if axis == "z":
                    for sx in range(ex1, ex2 + 1):
                        self._set(sx, sy, max(0, fixed - step - 1), self.mat_foundation)
                else:
                    for sz in range(ex1, ex2 + 1):
                        self._set(max(0, fixed - step - 1), sy, sz, self.mat_foundation)

        # 门廊柱
        if ent.has_columns and ent.column_count > 0:
            col_mat = self.mat_pillar
            for i in range(ent.column_count):
                cx = ex1 - 1 - i * 2 if i % 2 == 0 else ex2 + 2 + (i - 1) * 2
                for y in range(1, min(self.h, ent.height + 3)):
                    if axis == "z":
                        self._set(max(0, cx), y, max(0, fixed - 1), col_mat)
                    else:
                        self._set(max(0, fixed - 1), y, max(0, cx), col_mat)

        # 门廊屋顶
        if ent.has_roof_cover:
            ry = ent.height + 2
            if axis == "z" and ry < self.h:
                for sx in range(max(0, ex1 - 1), min(self.w, ex2 + 2)):
                    self._set(sx, ry, max(0, fixed - 1), self.mat_roof)
            elif ry < self.h:
                for sz in range(max(0, ex1 - 1), min(self.l, ex2 + 2)):
                    self._set(max(0, fixed - 1), ry, sz, self.mat_roof)

    # ═══════════════════════════════════════════════════════════════
    #  曲线渲染
    # ═══════════════════════════════════════════════════════════════

    def _render_curve(self, curve) -> None:
        """渲染曲线结构（圆塔/穹顶/拱/飞檐等）。"""
        mat = curve.material or self.mat_wall
        ct = curve.type

        if ct == "cylinder":
            generate_cylinder(self._set, curve.center_x, curve.center_z, curve.radius,
                              curve.center_y, curve.center_y + curve.height - 1,
                              mat, hollow=False, w=self.w, h=self.h, l=self.l)
        elif ct in ("dome", "sphere"):
            half = "half" if ct == "dome" else "full"
            generate_sphere(self._set, curve.center_x, curve.center_y, curve.center_z,
                            curve.radius, mat, half_or_full=half, hollow=False,
                            w=self.w, h=self.h, l=self.l)
        elif ct == "arch":
            generate_arch(self._set, curve.center_x, curve.center_z, curve.width, curve.height,
                          mat, arch_type=curve.arch_type, curvature=curve.curvature,
                          w=self.w, h=self.h, l=self.l)
        elif ct == "flying_eaves":
            # 飞檐：沿屋顶边缘画曲线
            direction = curve.direction
            curvature = curve.curvature
            # 简化：沿四个屋顶边缘画曲线
            roof_y = self.h - 1 + (self.desc.roof.height or self.h // 4)
            # 正面边缘 (z=0)
            generate_curve(self._set, 0, roof_y, 0, self.w - 1, roof_y, 0, mat,
                           direction=direction, curvature=curvature,
                           w=self.w, h=self.h, l=self.l)
            # 背面边缘 (z=l-1)
            generate_curve(self._set, 0, roof_y, self.l - 1, self.w - 1, roof_y, self.l - 1, mat,
                           direction=direction, curvature=curvature,
                           w=self.w, h=self.h, l=self.l)
        elif ct == "baroque_wall":
            # 巴洛克曲墙：墙面起伏（简化用 outward direction）
            generate_curve(self._set, 0, 0, 0, self.w - 1, self.h - 1, 0, mat,
                           direction="outward", curvature=curve.curvature,
                           w=self.w, h=self.h, l=self.l)
        elif ct == "free_curve":
            generate_curve(self._set, curve.center_x, curve.center_y, curve.center_z,
                           curve.center_x + curve.width, curve.center_y + curve.height,
                           curve.center_z + curve.depth, mat,
                           direction=curve.direction, curvature=curve.curvature,
                           w=self.w, h=self.h, l=self.l)
