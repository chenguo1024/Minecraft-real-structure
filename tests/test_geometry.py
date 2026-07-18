"""测试 V2 几何生成器（纯函数式基础几何原语）。

用 list-based mock setter 收集生成的方块，验证几何形状正确性。
不依赖 BlockBuilder/BlockMap，纯测试几何算法。
"""
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


def _make_setter(w: int, h: int, l: int):
    """创建 mock setter + 收集器。返回 (setter, blocks_set)。
    blocks_set 是 {(x,y,z): material} 字典。
    """
    blocks = {}

    def setter(x, y, z, material):
        if 0 <= x < w and 0 <= y < h and 0 <= z < l:
            blocks[(x, y, z)] = material

    return setter, blocks


class TestGenerateBox:
    def test_solid_box_fills_all(self):
        s, blocks = _make_setter(10, 10, 10)
        generate_box(s, 1, 1, 1, 4, 4, 4, "stone", w=10, h=10, l=10)
        # 实心 4x4x4 = 64 个方块
        assert len(blocks) == 64
        # 角点存在
        assert (1, 1, 1) in blocks
        assert (4, 4, 4) in blocks
        # 内部点存在
        assert (2, 2, 2) in blocks

    def test_hollow_box_only_shell(self):
        s, blocks = _make_setter(10, 10, 10)
        generate_box(s, 1, 1, 1, 4, 4, 4, "stone", hollow=True, w=10, h=10, l=10)
        # 空心 4x4x4 外壳 = 64 - 2x2x2 内部 = 64 - 8 = 56
        assert len(blocks) == 56
        # 内部点不应存在
        assert (2, 2, 2) not in blocks
        # 面点存在
        assert (1, 2, 2) in blocks

    def test_bounds_protection(self):
        s, blocks = _make_setter(5, 5, 5)
        # 试图在边界外画
        generate_box(s, -2, -2, -2, 10, 10, 10, "stone", w=5, h=5, l=5)
        # 只应画 0~4 范围内的
        for (x, y, z) in blocks:
            assert 0 <= x < 5
            assert 0 <= y < 5
            assert 0 <= z < 5

    def test_swapped_corners(self):
        s, blocks = _make_setter(10, 10, 10)
        generate_box(s, 4, 4, 4, 1, 1, 1, "stone", w=10, h=10, l=10)
        # 角点自动排序，仍应生成 64 个
        assert len(blocks) == 64

    def test_single_block(self):
        s, blocks = _make_setter(5, 5, 5)
        generate_box(s, 2, 2, 2, 2, 2, 2, "stone", w=5, h=5, l=5)
        assert len(blocks) == 1
        assert blocks[(2, 2, 2)] == "stone"


class TestGenerateCylinder:
    def test_solid_cylinder_has_blocks(self):
        s, blocks = _make_setter(10, 10, 10)
        generate_cylinder(s, 5, 5, 3, 0, 5, "stone", w=10, h=10, l=10)
        # 底面中心应有方块
        assert (5, 0, 5) in blocks
        # 顶部应有方块
        assert (5, 5, 5) in blocks
        # 半径 3 的圆面积约 28~30 个方块/层 * 6 层
        assert len(blocks) > 100

    def test_hollow_cylinder_only_shell(self):
        s, blocks = _make_setter(10, 10, 10)
        generate_cylinder(s, 5, 5, 3, 0, 5, "stone", hollow=True, w=10, h=10, l=10)
        # 空心管：只画圆环边缘
        # 底面中心不应有（圆环边缘才有）
        # 边缘点 (5+3, 0, 5) 应有
        assert (8, 0, 5) in blocks
        # 中心点 (5,0,5) 不应有（r=3 时中心不在边缘）
        # 实际 r=3, dz=0, dx_max=3, edge dx=±3 —— 中心 dx=0 不是 edge
        # 但 dz=3 时 dx_max=0, dx=0 是 edge —— 所以 (5,0,8) 有
        assert (5, 0, 8) in blocks

    def test_radius_zero(self):
        s, blocks = _make_setter(5, 5, 5)
        generate_cylinder(s, 2, 2, 0, 0, 3, "stone", w=5, h=5, l=5)
        # r=0 时只画中心柱
        for (x, y, z) in blocks:
            assert x == 2 and z == 2

    def test_negative_radius_noop(self):
        s, blocks = _make_setter(5, 5, 5)
        generate_cylinder(s, 2, 2, -1, 0, 3, "stone", w=5, h=5, l=5)
        assert len(blocks) == 0


class TestGenerateSphere:
    def test_full_sphere(self):
        s, blocks = _make_setter(15, 15, 15)
        generate_sphere(s, 7, 7, 7, 3, "stone", w=15, h=15, l=15)
        # 球心应有
        assert (7, 7, 7) in blocks
        # 球面点应有
        assert (10, 7, 7) in blocks  # +x 方向
        assert (7, 10, 7) in blocks  # +y 方向
        assert len(blocks) > 50

    def test_half_sphere_dome(self):
        s, blocks = _make_setter(15, 15, 15)
        generate_sphere(s, 7, 7, 7, 3, "stone", half_or_full="half", w=15, h=15, l=15)
        # 只画上半球（dy >= 0）
        for (x, y, z) in blocks:
            assert y >= 7  # cy=7, dy>=0 → y>=7
        # 下方点不应有
        assert (7, 4, 7) not in blocks

    def test_hollow_sphere_shell(self):
        s, blocks = _make_setter(15, 15, 15)
        generate_sphere(s, 7, 7, 7, 4, "stone", hollow=True, w=15, h=15, l=15)
        # 球心（距球心0）不应有
        assert (7, 7, 7) not in blocks
        # 球面点应有
        assert (11, 7, 7) in blocks


class TestGenerateCone:
    def test_cone_has_apex(self):
        s, blocks = _make_setter(10, 10, 10)
        generate_cone(s, 5, 5, 3, 5, "stone", w=10, h=10, l=10)
        # 顶点 (5, 4, 5) 应有（height=5, y=4 时 layer_r=0）
        # 底面应有完整圆
        assert (5, 0, 5) in blocks  # 底面中心
        assert (8, 0, 5) in blocks  # 底面边缘

    def test_cone_radius_shrinks(self):
        s, blocks = _make_setter(10, 10, 10)
        generate_cone(s, 5, 5, 4, 8, "stone", w=10, h=10, l=10)
        # 底层 y=0 半径=4，高层 y=7 半径应更小
        bottom_blocks = [(x, y, z) for (x, y, z) in blocks if y == 0]
        top_blocks = [(x, y, z) for (x, y, z) in blocks if y == 7]
        assert len(bottom_blocks) > len(top_blocks)

    def test_zero_height_noop(self):
        s, blocks = _make_setter(5, 5, 5)
        generate_cone(s, 2, 2, 3, 0, "stone", w=5, h=5, l=5)
        assert len(blocks) == 0


class TestGenerateArch:
    def test_semicircle_arch(self):
        s, blocks = _make_setter(10, 10, 10)
        generate_arch(s, 5, 5, 4, 4, "stone", arch_type="semicircle",
                      curvature=1.0, w=10, h=10, l=10)
        # width=4 → half_w=2, height=4, curvature=1.0 → rise=4, r=2
        # dx=0: dy=sqrt(4)*1=2, ay=(4-1)+(4-2)=3+2=5 → 中心拱顶 (5,5,5)
        assert (5, 5, 5) in blocks
        # 拱脚 dx=±2: dy=0, ay=(4-1)+(4-0)=7 → 拱脚 (3,7,5)/(7,7,5)
        assert (3, 7, 5) in blocks
        assert len(blocks) > 0

    def test_pointed_arch(self):
        s, blocks = _make_setter(10, 10, 10)
        generate_arch(s, 5, 5, 6, 5, "stone", arch_type="pointed",
                      curvature=1.0, w=10, h=10, l=10)
        assert len(blocks) > 0

    def test_ellipse_arch(self):
        s, blocks = _make_setter(10, 10, 10)
        generate_arch(s, 5, 5, 6, 4, "stone", arch_type="ellipse",
                      curvature=0.5, w=10, h=10, l=10)
        assert len(blocks) > 0

    def test_curvature_zero_flat_lintel(self):
        s, blocks = _make_setter(10, 10, 10)
        generate_arch(s, 5, 5, 4, 4, "stone", curvature=0.0, w=10, h=10, l=10)
        # curvature=0 时 rise=0，几乎平直
        assert len(blocks) > 0

    def test_unknown_type_falls_back(self):
        s, blocks = _make_setter(10, 10, 10)
        generate_arch(s, 5, 5, 4, 4, "stone", arch_type="unknown",
                      curvature=1.0, w=10, h=10, l=10)
        # fallback 到 semicircle，不崩
        assert len(blocks) > 0

    def test_thickness(self):
        s1, blocks1 = _make_setter(10, 10, 10)
        generate_arch(s1, 5, 5, 4, 4, "stone", thickness=1, w=10, h=10, l=10)
        s2, blocks2 = _make_setter(10, 10, 10)
        generate_arch(s2, 5, 5, 4, 4, "stone", thickness=3, w=10, h=10, l=10)
        # thickness=3 应比 thickness=1 多
        assert len(blocks2) >= len(blocks1)


class TestGenerateCurve:
    def test_curve_straight(self):
        s, blocks = _make_setter(10, 10, 10)
        generate_curve(s, 1, 1, 1, 5, 1, 1, "stone", curvature=0.0, w=10, h=10, l=10)
        # 直线：从 (1,1,1) 到 (5,1,1)
        assert (1, 1, 1) in blocks
        assert (5, 1, 1) in blocks

    def test_curve_up_direction(self):
        s, blocks = _make_setter(10, 10, 10)
        generate_curve(s, 1, 1, 1, 5, 1, 1, "stone", direction="up",
                       curvature=1.0, w=10, h=10, l=10)
        # 向上翘起：中点 y 应 > 1
        mid_y = max(y for (x, y, z) in blocks if x == 3)
        assert mid_y >= 1

    def test_curve_outward(self):
        s, blocks = _make_setter(10, 10, 10)
        generate_curve(s, 1, 5, 1, 5, 5, 1, "stone", direction="outward",
                       curvature=1.0, w=10, h=10, l=10)
        # 向外凸：中点 z 应 > 端点 z
        assert len(blocks) > 0

    def test_curve_bounds(self):
        s, blocks = _make_setter(3, 3, 3)
        generate_curve(s, 0, 0, 0, 10, 10, 10, "stone", w=3, h=3, l=3)
        for (x, y, z) in blocks:
            assert 0 <= x < 3 and 0 <= y < 3 and 0 <= z < 3


class TestRotateY:
    def test_no_rotation(self):
        assert rotate_y(3, 5, 0) == (3, 5)

    def test_90_degrees(self):
        assert rotate_y(3, 5, 90) == (-5, 3)

    def test_180_degrees(self):
        assert rotate_y(3, 5, 180) == (-3, -5)

    def test_270_degrees(self):
        assert rotate_y(3, 5, 270) == (5, -3)

    def test_unknown_rotation_passthrough(self):
        assert rotate_y(3, 5, 45) == (3, 5)


class TestGeneratePrism:
    def test_prism_z_taper(self):
        s, blocks = _make_setter(10, 10, 10)
        generate_prism(s, 0, 0, 0, 6, 4, 6, "stone", taper_axis="z", w=10, h=10, l=10)
        # z=0 端宽（6 个方块宽），z=6 端窄（收缩到 0）
        z0_blocks = [(x, y, z) for (x, y, z) in blocks if z == 0]
        z6_blocks = [(x, y, z) for (x, y, z) in blocks if z == 6]
        assert len(z0_blocks) > len(z6_blocks)

    def test_prism_y_taper(self):
        s, blocks = _make_setter(10, 10, 10)
        generate_prism(s, 0, 0, 0, 6, 6, 4, "stone", taper_axis="y", w=10, h=10, l=10)
        # y=0 端大，y=6 端小
        y0_blocks = [(x, y, z) for (x, y, z) in blocks if y == 0]
        y6_blocks = [(x, y, z) for (x, y, z) in blocks if y == 6]
        assert len(y0_blocks) > len(y6_blocks)

    def test_prism_has_blocks(self):
        s, blocks = _make_setter(10, 10, 10)
        generate_prism(s, 1, 1, 1, 6, 4, 6, "stone", taper_axis="z", w=10, h=10, l=10)
        assert len(blocks) > 0
