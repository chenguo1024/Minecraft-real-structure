"""预训练建筑模板库 —— 参数化模板，供 AI 识别建筑类型后填充参数。

设计思路：
  对于常见建筑类型，AI 只需识别类型 + 调整少量参数（width/height/floor_count 等），
  不需要从零构造完整的 BuildingDSL。大幅降低 AI 出错概率。

使用方式：
  from src.analysis.templates import get_template
  dsl = get_template("chinese_gate", width=20, height=12, floor_count=2)
  dsl.wall_material = "red_concrete"  # AI 可进一步自定义
"""
from __future__ import annotations

from copy import deepcopy

from src.models.building import (
    BlockMaterial,
    BuildingDSL,
    Component,
    CurveSpec,
    EntranceSpec,
    MinecraftVersion,
    PillarSpec,
    RoofSpec,
    WallSpec,
    WindowItem,
    WindowSystem,
)


def _make_villa(
    width: int = 12,
    length: int = 10,
    height: int = 8,
    floor_count: int = 2,
    detail_scale: int = 2,
) -> BuildingDSL:
    """现代别墅模板：主体 box + 平屋顶 + 大面积玻璃。"""
    return BuildingDSL(
        minecraft_version=MinecraftVersion.JAVA_1_20,
        building_type="villa",
        style="modern",
        width=width,
        length=length,
        height=height,
        floor_count=floor_count,
        floor_height=max(3, height // max(1, floor_count)),
        wall_thickness=1,
        detail_scale=detail_scale,
        shape="rectangle",
        components=[
            Component(
                name="main_body", shape="box",
                width=width, length=length, height=height,
                position="center", material="white_concrete",
            ),
        ],
        roof=RoofSpec(type="flat", height=1, material="gray_concrete"),
        walls=[WallSpec(type="plain_wall", thickness=1, material="white_concrete")],
        windows=WindowSystem(
            arrangement="symmetry",
            items=[
                WindowItem(shape="square", floor=1, side="front",
                           x=0.3, width=0.2, height=2, y_offset=1,
                           glass_material="blue_stained_glass"),
                WindowItem(shape="square", floor=1, side="front",
                           x=0.7, width=0.2, height=2, y_offset=1,
                           glass_material="blue_stained_glass"),
            ] + (
                [WindowItem(shape="square", floor=2, side="front",
                            x=0.3, width=0.2, height=2, y_offset=1,
                            glass_material="blue_stained_glass"),
                 WindowItem(shape="square", floor=2, side="front",
                            x=0.7, width=0.2, height=2, y_offset=1,
                            glass_material="blue_stained_glass")]
                if floor_count >= 2 else []
            ),
        ),
        entrance=EntranceSpec(
            type="simple", position="center", side="front",
            width=2, height=min(3, height),
            door_material="dark_oak_door",
        ),
        materials=[
            BlockMaterial(name="white_concrete", color="white", percentage=60, location="wall"),
            BlockMaterial(name="gray_concrete", color="gray", percentage=20, location="roof"),
            BlockMaterial(name="blue_stained_glass", color="light_blue", percentage=15, location="window"),
            BlockMaterial(name="dark_oak_door", color="brown", percentage=5, location="door"),
        ],
        platform_material="smooth_stone",
        roof_material="gray_concrete",
        door_material="dark_oak_door",
        window_glass_material="blue_stained_glass",
        wall_material="white_concrete",
    )


def _make_chinese_gate(
    width: int = 20,
    length: int = 8,
    height: int = 12,
    floor_count: int = 2,
    detail_scale: int = 2,
) -> BuildingDSL:
    """中式城门模板：台基 + 红色主体 + 重檐 + 飞檐 + 拱门。"""
    platform_h = max(2, height // 4)
    body_h = height - platform_h
    return BuildingDSL(
        minecraft_version=MinecraftVersion.JAVA_1_20,
        building_type="gate",
        style="chinese_traditional",
        width=width,
        length=length,
        height=height,
        floor_count=floor_count,
        floor_height=max(3, body_h // max(1, floor_count)),
        wall_thickness=2,
        detail_scale=detail_scale,
        shape="rectangle",
        components=[
            Component(
                name="platform", shape="box",
                width=width, length=length, height=platform_h,
                position="center", material="stone_bricks",
            ),
            Component(
                name="main_body", shape="box",
                width=width, length=length, height=body_h,
                offset_y=platform_h, position="center", material="red_concrete",
            ),
        ],
        roof=RoofSpec(
            type="chinese_roof",
            height=max(2, height // 4),
            layer_count=2,
            overhang=2,
            has_flying_eaves=True,
            eaves_curvature=0.7,
            material="red_terracotta",
        ),
        walls=[
            WallSpec(
                type="pillar", thickness=2, material="red_concrete",
                pillars=PillarSpec(
                    count=max(2, width // 4),
                    spacing=3, width=1,
                    material="chiseled_stone_bricks",
                ),
            ),
        ],
        windows=WindowSystem(items=[
            WindowItem(
                shape="arch", floor=floor_count, side="front",
                x=0.5, width=0.15, height=2, y_offset=1,
                frame_material="dark_oak_planks", glass_material="glass",
            ),
        ]),
        entrance=EntranceSpec(
            type="portal", position="center", side="front",
            width=max(2, width // 5), height=min(4, body_h),
            curvature=1.0,
            door_material="dark_oak_door",
            frame_material="red_terracotta",
        ),
        curves=[
            CurveSpec(
                type="flying_eaves", direction="up",
                curvature=0.7, material="red_terracotta",
            ),
        ],
        materials=[
            BlockMaterial(name="red_concrete", color="red", percentage=50, location="wall"),
            BlockMaterial(name="red_terracotta", color="red", percentage=30, location="roof"),
            BlockMaterial(name="stone_bricks", color="gray", percentage=15, location="platform"),
            BlockMaterial(name="chiseled_stone_bricks", color="gray", percentage=5, location="pillar"),
        ],
        platform_material="stone_bricks",
        roof_material="red_terracotta",
        door_material="dark_oak_door",
        window_glass_material="glass",
        wall_material="red_concrete",
        pillar_material="chiseled_stone_bricks",
    )


def _make_gothic_church(
    width: int = 16,
    length: int = 30,
    height: int = 20,
    floor_count: int = 1,
    detail_scale: int = 1,
) -> BuildingDSL:
    """哥特教堂模板：主体 + 侧廊 + 尖塔 + 扶壁 + 尖拱窗。"""
    return BuildingDSL(
        minecraft_version=MinecraftVersion.JAVA_1_20,
        building_type="church",
        style="gothic",
        width=width,
        length=length,
        height=height,
        floor_count=floor_count,
        floor_height=height,
        wall_thickness=2,
        detail_scale=detail_scale,
        shape="cross",
        components=[
            Component(
                name="main_body", shape="box",
                width=width, length=max(1, length - 6), height=height,
                position="center", material="stone_bricks",
            ),
            Component(
                name="tower", shape="box",
                width=max(2, width // 4), length=max(2, width // 4),
                height=max(3, height // 3),
                offset_y=height - max(3, height // 3),
                position="center", material="deepslate_bricks",
            ),
        ],
        roof=RoofSpec(
            type="spire",
            height=max(3, height // 3),
            spire_height=max(3, height // 3),
            spire_angle=30,
            material="black_concrete",
        ),
        walls=[
            WallSpec(
                type="buttress", thickness=2, material="stone_bricks",
                pillars=PillarSpec(
                    count=max(4, length // 4),
                    spacing=3, protrusion=1,
                    material="chiseled_stone_bricks",
                ),
            ),
        ],
        windows=WindowSystem(
            arrangement="symmetry",
            items=[
                WindowItem(
                    shape="pointed_arch", floor=1, side="front",
                    x=0.5, width=0.3, height=max(3, height // 3),
                    y_offset=2,
                    frame_material="chiseled_stone_bricks",
                    glass_material="blue_stained_glass",
                ),
                WindowItem(
                    shape="pointed_arch", floor=1, side="front",
                    x=0.25, width=0.15, height=max(2, height // 4),
                    y_offset=3,
                    frame_material="chiseled_stone_bricks",
                    glass_material="red_stained_glass",
                ),
                WindowItem(
                    shape="pointed_arch", floor=1, side="front",
                    x=0.75, width=0.15, height=max(2, height // 4),
                    y_offset=3,
                    frame_material="chiseled_stone_bricks",
                    glass_material="red_stained_glass",
                ),
            ],
        ),
        entrance=EntranceSpec(
            type="portal", position="center", side="front",
            width=max(2, width // 4), height=min(6, height // 3),
            curvature=1.0,
            door_material="dark_oak_door",
            frame_material="chiseled_stone_bricks",
        ),
        curves=[
            CurveSpec(
                type="arch", arch_type="pointed",
                width=width // 2, height=height // 2,
                center_x=width // 2, center_z=0,
                material="chiseled_stone_bricks",
            ),
        ],
        materials=[
            BlockMaterial(name="stone_bricks", color="gray", percentage=70, location="wall"),
            BlockMaterial(name="black_concrete", color="black", percentage=15, location="roof"),
            BlockMaterial(name="blue_stained_glass", color="blue", percentage=10, location="window"),
            BlockMaterial(name="chiseled_stone_bricks", color="gray", percentage=5, location="pillar"),
        ],
        roof_material="black_concrete",
        wall_material="stone_bricks",
        pillar_material="chiseled_stone_bricks",
        window_glass_material="blue_stained_glass",
    )


def _make_round_tower(
    width: int = 8,
    length: int = 8,
    height: int = 15,
    floor_count: int = 4,
    detail_scale: int = 2,
) -> BuildingDSL:
    """圆塔模板：cylinder 主体 + cone 屋顶 + 拱形入口。"""
    r = max(1, min(width, length) // 2)
    return BuildingDSL(
        minecraft_version=MinecraftVersion.JAVA_1_20,
        building_type="tower",
        style="medieval",
        width=width,
        length=length,
        height=height,
        floor_count=floor_count,
        floor_height=max(2, height // max(1, floor_count)),
        wall_thickness=1,
        detail_scale=detail_scale,
        shape="circle",
        components=[
            Component(
                name="main_body", shape="cylinder",
                radius=r, height=height - 3,
                position="center", material="stone_bricks",
            ),
        ],
        roof=RoofSpec(
            type="cone", height=3, material="dark_oak_planks",
        ),
        walls=[WallSpec(type="plain_wall", thickness=1, material="stone_bricks")],
        windows=WindowSystem(items=[
            WindowItem(
                shape="arch", floor=2, side="front",
                x=0.5, width=0.15, height=2, y_offset=1,
                glass_material="glass",
            ),
        ]),
        entrance=EntranceSpec(
            type="arch", position="center", side="front",
            width=2, height=min(3, height),
            curvature=1.0,
            door_material="dark_oak_door",
        ),
        materials=[
            BlockMaterial(name="stone_bricks", color="gray", percentage=80, location="wall"),
            BlockMaterial(name="dark_oak_planks", color="brown", percentage=15, location="roof"),
            BlockMaterial(name="glass", color="transparent", percentage=5, location="window"),
        ],
        roof_material="dark_oak_planks",
        wall_material="stone_bricks",
        door_material="dark_oak_door",
        window_glass_material="glass",
    )


def _make_classical_temple(
    width: int = 12,
    length: int = 12,
    height: int = 10,
    floor_count: int = 1,
    detail_scale: int = 2,
) -> BuildingDSL:
    """古典庙宇模板：方殿 + 柱廊 + 穹顶。"""
    r = max(1, min(width, length) // 2 - 1)
    return BuildingDSL(
        minecraft_version=MinecraftVersion.JAVA_1_20,
        building_type="temple",
        style="classical",
        width=width,
        length=length,
        height=height,
        floor_count=floor_count,
        floor_height=max(2, height - r),
        wall_thickness=1,
        detail_scale=detail_scale,
        shape="square",
        components=[
            Component(
                name="main_body", shape="box",
                width=width, length=length, height=height - r,
                position="center", material="quartz_block",
            ),
        ],
        roof=RoofSpec(type="dome", height=r, material="terracotta"),
        walls=[
            WallSpec(
                type="pillar", thickness=1, material="quartz_block",
                pillars=PillarSpec(
                    count=max(4, width // 2),
                    spacing=1, width=1,
                    material="quartz_pillar",
                ),
            ),
        ],
        windows=WindowSystem(items=[]),
        entrance=EntranceSpec(
            type="column_entrance", position="center", side="front",
            width=3, height=min(4, height - r),
            has_columns=True, column_count=4,
            has_roof_cover=True,
            door_material="oak_door",
            frame_material="quartz_block",
        ),
        curves=[
            CurveSpec(
                type="dome", radius=r,
                center_x=width // 2, center_y=height - r, center_z=length // 2,
                material="terracotta",
            ),
        ],
        materials=[
            BlockMaterial(name="quartz_block", color="white", percentage=60, location="wall"),
            BlockMaterial(name="terracotta", color="orange", percentage=25, location="roof"),
            BlockMaterial(name="quartz_pillar", color="white", percentage=15, location="pillar"),
        ],
        platform_material="smooth_stone",
        roof_material="terracotta",
        wall_material="quartz_block",
        pillar_material="quartz_pillar",
    )


def _make_baroque_palace(
    width: int = 24,
    length: int = 16,
    height: int = 14,
    floor_count: int = 3,
    detail_scale: int = 2,
) -> BuildingDSL:
    """巴洛克宫殿模板：主体 + 中央穹顶 + 曲墙 + 多柱入口。"""
    return BuildingDSL(
        minecraft_version=MinecraftVersion.JAVA_1_20,
        building_type="palace",
        style="baroque",
        width=width,
        length=length,
        height=height,
        floor_count=floor_count,
        floor_height=max(3, height // max(1, floor_count)),
        wall_thickness=2,
        detail_scale=detail_scale,
        shape="rectangle",
        components=[
            Component(
                name="main_body", shape="box",
                width=width, length=length, height=height,
                position="center", material="white_concrete",
            ),
        ],
        roof=RoofSpec(
            type="dome", height=max(2, height // 4),
            material="gold_block",
        ),
        walls=[
            WallSpec(
                type="pilaster", thickness=2, material="white_concrete",
                pillars=PillarSpec(
                    count=max(4, width // 3),
                    spacing=3, width=1,
                    material="quartz_pillar",
                ),
            ),
        ],
        windows=WindowSystem(
            arrangement="grid",
            items=[
                WindowItem(
                    shape="arch", floor=1, side="front",
                    x=0.2, width=0.12, height=2, y_offset=1,
                    frame_material="quartz_block",
                    glass_material="blue_stained_glass",
                ),
                WindowItem(
                    shape="arch", floor=2, side="front",
                    x=0.5, width=0.12, height=2, y_offset=1,
                    frame_material="quartz_block",
                    glass_material="blue_stained_glass",
                ),
                WindowItem(
                    shape="arch", floor=1, side="front",
                    x=0.8, width=0.12, height=2, y_offset=1,
                    frame_material="quartz_block",
                    glass_material="blue_stained_glass",
                ),
            ],
        ),
        entrance=EntranceSpec(
            type="column_entrance", position="center", side="front",
            width=4, height=min(5, height // 2),
            has_columns=True, column_count=4,
            has_stairs=True, stair_count=3,
            has_roof_cover=True,
            door_material="oak_door",
            frame_material="quartz_block",
        ),
        curves=[
            CurveSpec(
                type="baroque_wall", curvature=0.3,
                material="white_concrete",
            ),
            CurveSpec(
                type="dome", radius=max(2, width // 4),
                center_x=width // 2, center_y=height, center_z=length // 2,
                material="gold_block",
            ),
        ],
        materials=[
            BlockMaterial(name="white_concrete", color="white", percentage=55, location="wall"),
            BlockMaterial(name="gold_block", color="gold", percentage=15, location="roof"),
            BlockMaterial(name="quartz_block", color="white", percentage=20, location="decoration"),
            BlockMaterial(name="blue_stained_glass", color="blue", percentage=10, location="window"),
        ],
        roof_material="gold_block",
        wall_material="white_concrete",
        pillar_material="quartz_pillar",
        window_glass_material="blue_stained_glass",
        door_material="oak_door",
    )


def _make_brutalist_building(
    width: int = 14,
    length: int = 14,
    height: int = 16,
    floor_count: int = 4,
    detail_scale: int = 2,
) -> BuildingDSL:
    """粗野主义模板：灰色混凝土 + 暴露结构 + 大窗洞。"""
    return BuildingDSL(
        minecraft_version=MinecraftVersion.JAVA_1_20,
        building_type="house",
        style="brutalist",
        width=width,
        length=length,
        height=height,
        floor_count=floor_count,
        floor_height=max(3, height // max(1, floor_count)),
        wall_thickness=2,
        detail_scale=detail_scale,
        shape="rectangle",
        components=[
            Component(
                name="main_body", shape="box",
                width=width, length=length, height=height,
                position="center", material="gray_concrete",
            ),
            Component(
                name="canopy", shape="box",
                width=max(2, width // 3), length=max(2, length // 3),
                height=2, offset_y=height - 2,
                position="center", material="exposed_copper",
            ),
        ],
        roof=RoofSpec(type="flat", height=1, material="gray_concrete"),
        walls=[
            WallSpec(type="rustication", thickness=2, material="gray_concrete"),
        ],
        windows=WindowSystem(
            arrangement="vertical_repeat",
            items=[
                WindowItem(
                    shape="glass_wall", floor=1, side="front",
                    x=0.35, width=0.3, height=max(2, height // 4),
                    y_offset=1,
                    glass_material="glass",
                ),
                WindowItem(
                    shape="glass_wall", floor=2, side="front",
                    x=0.35, width=0.3, height=max(2, height // 4),
                    y_offset=1,
                    glass_material="glass",
                ),
            ],
        ),
        entrance=EntranceSpec(
            type="simple", position="center", side="front",
            width=2, height=min(3, height),
            has_stairs=True, stair_count=3,
            door_material="iron_door",
        ),
        materials=[
            BlockMaterial(name="gray_concrete", color="gray", percentage=80, location="wall"),
            BlockMaterial(name="glass", color="transparent", percentage=15, location="window"),
            BlockMaterial(name="exposed_copper", color="teal", percentage=5, location="decoration"),
        ],
        roof_material="gray_concrete",
        wall_material="gray_concrete",
        window_glass_material="glass",
        door_material="iron_door",
    )


# ═══════════════════════════════════════════════════════
#  模板注册表
# ═══════════════════════════════════════════════════════

# 风格 → 模板函数映射
STYLE_TEMPLATES: dict[str, dict] = {
    # 现代风格
    "modern": {
        "func": _make_villa,
        "keywords": ["villa", "house", "residence", "contemporary"],
    },
    # 中式传统
    "chinese_traditional": {
        "func": _make_chinese_gate,
        "keywords": ["gate", "palace", "temple", "chinese", "pagoda"],
    },
    # 哥特
    "gothic": {
        "func": _make_gothic_church,
        "keywords": ["church", "cathedral", "gothic", "basilica"],
    },
    # 中世纪
    "medieval": {
        "func": _make_round_tower,
        "keywords": ["tower", "castle", "fortress", "keep"],
    },
    # 古典
    "classical": {
        "func": _make_classical_temple,
        "keywords": ["temple", "rotunda", "pantheon"],
    },
    # 巴洛克
    "baroque": {
        "func": _make_baroque_palace,
        "keywords": ["palace", "baroque", "mansion"],
    },
    # 粗野主义
    "brutalist": {
        "func": _make_brutalist_building,
        "keywords": ["modern", "concrete", "brutalist"],
    },
}


# 建筑类型 → 风格映射（fallback）
TYPE_STYLE_MAP: dict[str, str] = {
    "villa": "modern",
    "house": "modern",
    "gate": "chinese_traditional",
    "church": "gothic",
    "cathedral": "gothic",
    "tower": "medieval",
    "castle": "medieval",
    "temple": "classical",
    "palace": "baroque",
    "pagoda": "chinese_traditional",
    "skyscraper": "brutalist",
}


def get_template(
    style: str = "modern",
    building_type: str = "house",
    width: int = 12,
    length: int = 10,
    height: int = 8,
    floor_count: int = 2,
    detail_scale: int = 2,
) -> BuildingDSL:
    """根据风格/类型获取参数化模板。

    Args:
        style: 建筑风格
        building_type: 建筑类型
        width/length/height: 尺寸参数
        floor_count: 楼层数
        detail_scale: 精细度

    Returns:
        已填充参数的 BuildingDSL
    """
    # 先按 style 找
    entry = STYLE_TEMPLATES.get(style)
    if entry is None:
        # 按 building_type 找 style
        mapped_style = TYPE_STYLE_MAP.get(building_type, "modern")
        entry = STYLE_TEMPLATES.get(mapped_style, STYLE_TEMPLATES["modern"])

    dsl = entry["func"](
        width=width,
        length=length,
        height=height,
        floor_count=floor_count,
        detail_scale=detail_scale,
    )
    dsl.building_type = building_type
    dsl.style = style
    return dsl


