"""V2 几何生成器 —— 纯函数式基础几何原语。

按 V2 技术方案"几何生成器"部分实现：
  generate_box / generate_cylinder / generate_sphere / generate_cone / generate_arch / generate_curve

设计原则：
  1. 纯函数式：接受 grid_setter callable + 边界 (w,h,l)，不耦合 BlockBuilder 内部状态
  2. 支持 hollow（空心）vs solid（实心）
  3. 支持 rotation_deg（0/90/180/270）绕 Y 轴旋转
  4. 边界保护内部做（越界坐标自动忽略）
  5. arch 支持 arch_type=semicircle/pointed/ellipse + curvature 0~1
  6. curve 支持飞檐 direction=up/outward/inward + curvature

grid 约定：与 block_builder.py 一致，grid[z][y][x]，setter 签名 setter(x, y, z, material)。
material 为字符串方块名（由调用方负责解析为 ID）。
"""
from __future__ import annotations

import math
from typing import Callable, Optional

# setter 签名：(x, y, z, material_name) -> None
GridSetter = Callable[[int, int, int, str], None]


def _in_bounds(x: int, y: int, z: int, w: int, h: int, l: int) -> bool:
    """边界保护：越界坐标忽略。"""
    return 0 <= x < w and 0 <= y < h and 0 <= z < l


# ═══════════════════════════════════════════════════════════════
#  基础几何：box
# ═══════════════════════════════════════════════════════════════

def generate_box(
    setter: GridSetter,
    x1: int, y1: int, z1: int,
    x2: int, y2: int, z2: int,
    material: str,
    hollow: bool = False,
    w: int = 256, h: int = 256, l: int = 256,
) -> None:
    """生成长方体（实心或空心外壳）。

    Args:
        setter: grid 写入函数
        x1,y1,z1: 角点1（含）
        x2,y2,z2: 角点2（含）
        material: 方块名
        hollow: True=只画6个面（外壳），False=实心
        w,h,l: 边界（越界忽略）
    """
    if x1 > x2: x1, x2 = x2, x1
    if y1 > y2: y1, y2 = y2, y1
    if z1 > z2: z1, z2 = z2, z1
    for z in range(z1, z2 + 1):
        for y in range(y1, y2 + 1):
            for x in range(x1, x2 + 1):
                if not _in_bounds(x, y, z, w, h, l):
                    continue
                if hollow:
                    # 只画外壳：6 个面之一
                    on_face = (x == x1 or x == x2 or
                               y == y1 or y == y2 or
                               z == z1 or z == z2)
                    if on_face:
                        setter(x, y, z, material)
                else:
                    setter(x, y, z, material)


# ═══════════════════════════════════════════════════════════════
#  基础几何：cylinder（垂直圆柱，沿 Y 轴）
# ═══════════════════════════════════════════════════════════════

def generate_cylinder(
    setter: GridSetter,
    cx: int, cz: int, radius: int,
    y1: int, y2: int,
    material: str,
    hollow: bool = False,
    w: int = 256, h: int = 256, l: int = 256,
) -> None:
    """生成垂直圆柱体（沿 Y 轴）。

    Args:
        cx, cz: 底面圆心 XZ
        radius: 半径
        y1, y2: Y 范围（含）
        material: 方块名
        hollow: True=只画侧面（管状），False=实心
    """
    if radius < 0:
        return
    for y in range(max(0, y1), min(h, y2 + 1)):
        for dz in range(-radius, radius + 1):
            z = cz + dz
            if z < 0 or z >= l:
                continue
            dx_max = int(math.sqrt(max(0, radius * radius - dz * dz)))
            for dx in range(-dx_max, dx_max + 1):
                x = cx + dx
                if x < 0 or x >= w:
                    continue
                if hollow:
                    # 只画圆环边缘
                    if abs(dx) == dx_max or abs(dz) == radius:
                        setter(x, y, z, material)
                else:
                    setter(x, y, z, material)


# ═══════════════════════════════════════════════════════════════
#  基础几何：sphere（球体/半球）
# ═══════════════════════════════════════════════════════════════

def generate_sphere(
    setter: GridSetter,
    cx: int, cy: int, cz: int, radius: int,
    material: str,
    half_or_full: str = "full",
    hollow: bool = False,
    w: int = 256, h: int = 256, l: int = 256,
) -> None:
    """生成球体或半球（穹顶用 half）。

    Args:
        cx, cy, cz: 球心
        radius: 半径
        material: 方块名
        half_or_full: "half"=上半球（穹顶），"full"=全球
        hollow: True=只画球壳，False=实心
    """
    if radius < 0:
        return
    r = radius
    for dy in range(-r, r + 1):
        # half 模式只画上半球
        if half_or_full == "half" and dy < 0:
            continue
        y = cy + dy
        if y < 0 or y >= h:
            continue
        # 当前 Y 层的圆半径
        ring_r = int(math.sqrt(max(0, r * r - dy * dy)))
        if ring_r == 0:
            if _in_bounds(cx, y, cz, w, h, l):
                setter(cx, y, cz, material)
            continue
        for dz in range(-ring_r, ring_r + 1):
            z = cz + dz
            if z < 0 or z >= l:
                continue
            dx_max = int(math.sqrt(max(0, ring_r * ring_r - dz * dz)))
            for dx in range(-dx_max, dx_max + 1):
                x = cx + dx
                if x < 0 or x >= w:
                    continue
                if hollow:
                    # 球壳：当前点距球心≈r
                    dist_sq = dx * dx + dy * dy + dz * dz
                    if abs(math.sqrt(dist_sq) - r) < 1.0:
                        setter(x, y, z, material)
                else:
                    setter(x, y, z, material)


# ═══════════════════════════════════════════════════════════════
#  基础几何：cone（圆锥体/圆锥壳）
# ═══════════════════════════════════════════════════════════════

def generate_cone(
    setter: GridSetter,
    cx: int, cz: int, radius: int, height: int,
    material: str,
    hollow: bool = False,
    w: int = 256, h: int = 256, l: int = 256,
) -> None:
    """生成圆锥体（哥特尖塔/塔尖用）。

    底面在 y=0（相对），顶点在 y=height。
    每层 Y 的半径线性收缩：r(y) = radius * (1 - y/height)。

    Args:
        cx, cz: 底面圆心
        radius: 底面半径
        height: 总高
        material: 方块名
        hollow: True=只画侧面壳，False=实心
    """
    if radius < 0 or height <= 0:
        return
    for y in range(0, min(h, height)):
        # 当前层半径（线性收缩）
        t = y / height
        layer_r = int(radius * (1 - t))
        if layer_r <= 0:
            # 顶点
            if _in_bounds(cx, y, cz, w, h, l):
                setter(cx, y, cz, material)
            continue
        for dz in range(-layer_r, layer_r + 1):
            z = cz + dz
            if z < 0 or z >= l:
                continue
            dx_max = int(math.sqrt(max(0, layer_r * layer_r - dz * dz)))
            for dx in range(-dx_max, dx_max + 1):
                x = cx + dx
                if x < 0 or x >= w:
                    continue
                if hollow:
                    if abs(dx) == dx_max or abs(dz) == layer_r:
                        setter(x, y, z, material)
                else:
                    setter(x, y, z, material)


# ═══════════════════════════════════════════════════════════════
#  基础几何：arch（拱形）
# ═══════════════════════════════════════════════════════════════

def generate_arch(
    setter: GridSetter,
    cx: int, cz: int, width: int, height: int,
    material: str,
    arch_type: str = "semicircle",
    curvature: float = 1.0,
    thickness: int = 1,
    w: int = 256, h: int = 256, l: int = 256,
) -> None:
    """生成拱形（门拱/窗拱/走廊拱）。

    Args:
        cx, cz: 拱中心点 XZ
        width: 拱宽
        height: 拱高
        material: 方块名
        arch_type: semicircle（半圆拱）/ pointed（尖拱）/ ellipse（扁拱）
        curvature: 0~1，0=直角过梁，1=完整半圆，0.5=扁拱
        thickness: 拱厚度（方块数）
    """
    if width <= 0 or height <= 0:
        return
    half_w = width // 2
    rise = int(height * curvature)
    # 拱顶在 y = (height-1) + rise（最高），拱脚在 y = height-1（门洞顶）
    # dx=0 → dy=rise（最高），dx=±half_w → dy=0（拱脚）
    if arch_type == "semicircle":
        # 半圆拱：r = half_w
        r = half_w
        for dx in range(-half_w, half_w + 1):
            dy = int(math.sqrt(max(0, r * r - dx * dx)) * curvature)
            ay = (height - 1) + (rise - dy) if rise > 0 else (height - 1)
            if 0 <= ay < h:
                for t in range(thickness):
                    if _in_bounds(cx + dx, ay, cz + t, w, h, l):
                        setter(cx + dx, ay, cz + t, material)
                    if _in_bounds(cx + dx, ay, cz - t, w, h, l):
                        setter(cx + dx, ay, cz - t, material)
    elif arch_type == "pointed":
        # 尖拱：两个半圆交汇于顶点
        r = half_w
        apex_y = height - 1 + rise
        # 左半圆心在 (cx - half_w + r, ?) —— 简化用两个圆心
        left_cx = cx - half_w + r
        right_cx = cx + half_w - r
        for dx in range(-half_w, half_w + 1):
            # 左侧用左圆心，右侧用右圆心
            if dx <= 0:
                ref_cx = left_cx
            else:
                ref_cx = right_cx
            ddx = dx - (ref_cx - cx)
            dy = int(math.sqrt(max(0, r * r - ddx * ddx)) * curvature)
            ay = (height - 1) + (rise - dy) if rise > 0 else (height - 1)
            if 0 <= ay < h:
                for t in range(thickness):
                    if _in_bounds(cx + dx, ay, cz + t, w, h, l):
                        setter(cx + dx, ay, cz + t, material)
                    if _in_bounds(cx + dx, ay, cz - t, w, h, l):
                        setter(cx + dx, ay, cz - t, material)
    elif arch_type == "ellipse":
        # 扁拱：椭圆上半
        a = half_w  # 水平半轴
        b = max(1, rise)  # 垂直半轴
        for dx in range(-a, a + 1):
            # 椭圆方程：(dx/a)^2 + (dy/b)^2 = 1
            dy = int(b * math.sqrt(max(0, 1 - (dx / a) ** 2)))
            ay = (height - 1) + (rise - dy) if rise > 0 else (height - 1)
            if 0 <= ay < h:
                for t in range(thickness):
                    if _in_bounds(cx + dx, ay, cz + t, w, h, l):
                        setter(cx + dx, ay, cz + t, material)
                    if _in_bounds(cx + dx, ay, cz - t, w, h, l):
                        setter(cx + dx, ay, cz - t, material)
    else:
        # 未知 arch_type，fallback 到 semicircle
        generate_arch(setter, cx, cz, width, height, material,
                      arch_type="semicircle", curvature=curvature,
                      thickness=thickness, w=w, h=h, l=l)


# ═══════════════════════════════════════════════════════════════
#  基础几何：curve（自由曲线，飞檐/曲墙）
# ═══════════════════════════════════════════════════════════════

def generate_curve(
    setter: GridSetter,
    x1: int, y1: int, z1: int,
    x2: int, y2: int, z2: int,
    material: str,
    direction: str = "up",
    curvature: float = 0.5,
    w: int = 256, h: int = 256, l: int = 256,
) -> None:
    """生成自由曲线（飞檐/曲墙）。

    沿 (x1,y1,z1) → (x2,y2,z2) 画一条曲线，按 direction 和 curvature 调整弧度。

    Args:
        x1,y1,z1: 起点
        x2,y2,z2: 终点
        material: 方块名
        direction: up（向上翘起）/ outward（向外凸出）/ inward（向内凹）
        curvature: 0~1，0=直线，1=强弧
    """
    dx = x2 - x1
    dy = y2 - y1
    dz = z2 - z1
    length = max(1, int(math.sqrt(dx * dx + dy * dy + dz * dz)))
    steps = length * 2  # 采样密度
    for i in range(steps + 1):
        t = i / steps
        # 线性插值
        x = int(x1 + dx * t)
        y = int(y1 + dy * t)
        z = int(z1 + dz * t)
        # 弧度偏移：sin 曲线，中点最大
        offset = math.sin(math.pi * t) * curvature * length * 0.3
        if direction == "up":
            y += int(offset)
        elif direction == "outward":
            # 向外凸：垂直于线段方向偏移（简化用 z 偏移）
            z += int(offset)
        elif direction == "inward":
            z -= int(offset)
        if _in_bounds(x, y, z, w, h, l):
            setter(x, y, z, material)


# ═══════════════════════════════════════════════════════════════
#  辅助：旋转坐标变换（绕 Y 轴）
# ═══════════════════════════════════════════════════════════════

def rotate_y(x: int, z: int, rotation_deg: int) -> tuple[int, int]:
    """绕 Y 轴旋转坐标（0/90/180/270 度）。

    Returns:
        (new_x, new_z)
    """
    if rotation_deg == 0:
        return x, z
    elif rotation_deg == 90:
        return -z, x
    elif rotation_deg == 180:
        return -x, -z
    elif rotation_deg == 270:
        return z, -x
    return x, z


# ═══════════════════════════════════════════════════════════════
#  辅助：棱柱（prism，用于屋顶山花/楔形组件）
# ═══════════════════════════════════════════════════════════════

def generate_prism(
    setter: GridSetter,
    x1: int, y1: int, z1: int,
    x2: int, y2: int, z2: int,
    material: str,
    taper_axis: str = "z",
    w: int = 256, h: int = 256, l: int = 256,
) -> None:
    """生成棱柱（一端宽一端窄，用于楔形组件/山花）。

    taper_axis 指定沿哪个轴收缩：x/y/z。
    沿 taper_axis 从全截面线性收缩到 0。
    """
    if x1 > x2: x1, x2 = x2, x1
    if y1 > y2: y1, y2 = y2, y1
    if z1 > z2: z1, z2 = z2, z1
    if taper_axis == "z":
        total = z2 - z1
        for z in range(z1, z2 + 1):
            t = (z - z1) / max(1, total)
            shrink = int((x2 - x1) * t / 2)
            cx = (x1 + x2) // 2
            nx1 = cx - (x2 - x1) // 2 + shrink
            nx2 = cx + (x2 - x1) // 2 - shrink
            for y in range(y1, y2 + 1):
                for x in range(nx1, nx2 + 1):
                    if _in_bounds(x, y, z, w, h, l):
                        setter(x, y, z, material)
    elif taper_axis == "x":
        total = x2 - x1
        for x in range(x1, x2 + 1):
            t = (x - x1) / max(1, total)
            shrink = int((z2 - z1) * t / 2)
            cz = (z1 + z2) // 2
            nz1 = cz - (z2 - z1) // 2 + shrink
            nz2 = cz + (z2 - z1) // 2 - shrink
            for y in range(y1, y2 + 1):
                for z in range(nz1, nz2 + 1):
                    if _in_bounds(x, y, z, w, h, l):
                        setter(x, y, z, material)
    elif taper_axis == "y":
        total = y2 - y1
        for y in range(y1, y2 + 1):
            t = (y - y1) / max(1, total)
            shrink_x = int((x2 - x1) * t / 2)
            shrink_z = int((z2 - z1) * t / 2)
            cx = (x1 + x2) // 2
            cz = (z1 + z2) // 2
            nx1 = cx - (x2 - x1) // 2 + shrink_x
            nx2 = cx + (x2 - x1) // 2 - shrink_x
            nz1 = cz - (z2 - z1) // 2 + shrink_z
            nz2 = cz + (z2 - z1) // 2 - shrink_z
            for z in range(nz1, nz2 + 1):
                for x in range(nx1, nx2 + 1):
                    if _in_bounds(x, y, z, w, h, l):
                        setter(x, y, z, material)
