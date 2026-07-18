"""V2 Mock 分析器 —— 输出 BuildingDSL 模板用于测试（不调真实 API）。

覆盖多种建筑风格/形状/屋顶/component 组合，供集成测试和 CLI mock 模式用。
"""
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


# ── 模板 1：现代别墅 ──
_MODERN_VILLA = BuildingDSL(
    minecraft_version=MinecraftVersion.JAVA_1_20,
    building_name="",
    building_type="villa",
    style="modern",
    location="",
    width=12, length=10, height=8,
    floor_count=2, floor_height=4, wall_thickness=1,
    detail_scale=2,
    shape="rectangle",
    components=[
        Component(name="main_body", shape="box", width=12, length=10, height=8,
                  position="center", material="white_concrete"),
    ],
    roof=RoofSpec(type="flat", height=1, material="gray_concrete"),
    walls=[WallSpec(type="plain_wall", thickness=1, material="white_concrete")],
    windows=WindowSystem(
        arrangement="symmetry",
        items=[
            WindowItem(shape="square", floor=1, side="front", x=0.3, width=0.15, height=2, y_offset=1),
            WindowItem(shape="square", floor=1, side="front", x=0.7, width=0.15, height=2, y_offset=1),
            WindowItem(shape="square", floor=2, side="front", x=0.3, width=0.15, height=2, y_offset=1),
            WindowItem(shape="square", floor=2, side="front", x=0.7, width=0.15, height=2, y_offset=1),
        ],
    ),
    entrance=EntranceSpec(type="simple", position="center", side="front",
                          width=2, height=3, door_material="dark_oak_door"),
    materials=[
        BlockMaterial(name="white_concrete", color="white", percentage=60, location="wall"),
        BlockMaterial(name="gray_concrete", color="gray", percentage=20, location="roof"),
        BlockMaterial(name="glass", color="light_blue", percentage=15, location="window"),
        BlockMaterial(name="dark_oak_door", color="brown", percentage=5, location="door"),
    ],
    platform_material="smooth_stone",
    roof_material="gray_concrete",
    door_material="dark_oak_door",
    window_glass_material="glass",
    wall_material="white_concrete",
    description="Two-story modern villa with flat roof, white concrete walls, large windows.",
)

# ── 模板 2：中式城门（天安门风格）──
_CHINESE_GATE = BuildingDSL(
    minecraft_version=MinecraftVersion.JAVA_1_20,
    building_name="城门",
    building_type="gate",
    style="chinese_traditional",
    location="Beijing, China",
    width=20, length=8, height=12,
    floor_count=2, floor_height=4, wall_thickness=2,
    detail_scale=2,
    shape="rectangle",
    components=[
        Component(name="platform", shape="box", width=20, length=8, height=4,
                  position="center", material="stone_bricks"),
        Component(name="main_body", shape="box", width=20, length=8, height=6,
                  offset_y=4, position="center", material="red_concrete"),
    ],
    roof=RoofSpec(type="chinese_roof", height=3, layer_count=2, overhang=2,
                  has_flying_eaves=True, eaves_curvature=0.7,
                  material="red_terracotta"),
    walls=[WallSpec(type="pillar", thickness=2, material="red_concrete",
                    pillars=PillarSpec(count=6, spacing=3, width=1,
                                       material="chiseled_stone_bricks"))],
    windows=WindowSystem(items=[
        WindowItem(shape="arch", floor=2, side="front", x=0.5, width=0.2, height=2, y_offset=1),
    ]),
    entrance=EntranceSpec(type="portal", position="center", side="front",
                          width=4, height=4, curvature=1.0,
                          door_material="dark_oak_door",
                          frame_material="red_terracotta"),
    curves=[
        CurveSpec(type="flying_eaves", direction="up", curvature=0.7,
                  material="red_terracotta"),
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
    wall_material="red_concrete",
    pillar_material="chiseled_stone_bricks",
    description="Chinese gate tower with red walls, stone platform, and flying eaves roof.",
    keywords=["城门", "Chinese gate"],
)

# ── 模板 3：哥特教堂 ──
_GOTHIC_CHURCH = BuildingDSL(
    minecraft_version=MinecraftVersion.JAVA_1_20,
    building_name="",
    building_type="church",
    style="gothic",
    width=16, length=30, height=20,
    floor_count=1, floor_height=18, wall_thickness=2,
    detail_scale=1,
    shape="cross",
    components=[
        Component(name="main_body", shape="box", width=16, length=24, height=18,
                  position="center", material="stone_bricks"),
        Component(name="spire", shape="cone", radius=3, height=12,
                  position="top", material="black_concrete"),
    ],
    roof=RoofSpec(type="spire", height=12, spire_height=12, spire_angle=30,
                  material="black_concrete"),
    walls=[WallSpec(type="buttress", thickness=2, material="stone_bricks",
                    pillars=PillarSpec(count=8, spacing=3, protrusion=1,
                                       material="chiseled_stone_bricks"))],
    windows=WindowSystem(
        arrangement="symmetry",
        items=[
            WindowItem(shape="pointed_arch", floor=1, side="front", x=0.5,
                       width=0.3, height=6, y_offset=2,
                       frame_material="chiseled_stone_bricks",
                       glass_material="blue_stained_glass"),
        ],
    ),
    entrance=EntranceSpec(type="portal", position="center", side="front",
                          width=4, height=6, curvature=1.0,
                          frame_material="chiseled_stone_bricks",
                          door_material="dark_oak_door"),
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
    description="Gothic church with stone walls, flying buttresses, pointed arch windows, and spire.",
)

# ── 模板 4：圆塔 ──
_ROUND_TOWER = BuildingDSL(
    minecraft_version=MinecraftVersion.JAVA_1_20,
    building_type="tower",
    style="medieval",
    width=8, length=8, height=15,
    floor_count=4, floor_height=3, wall_thickness=1,
    detail_scale=2,
    shape="circle",
    components=[
        Component(name="main_body", shape="cylinder", radius=4, height=12,
                  position="center", material="stone_bricks"),
    ],
    roof=RoofSpec(type="cone", height=3, material="dark_oak_planks"),
    walls=[WallSpec(type="plain_wall", thickness=1, material="stone_bricks")],
    windows=WindowSystem(items=[
        WindowItem(shape="arch", floor=2, side="front", x=0.5, width=0.15, height=2, y_offset=1),
    ]),
    entrance=EntranceSpec(type="arch", position="center", side="front",
                          width=2, height=3, curvature=1.0,
                          door_material="dark_oak_door"),
    materials=[
        BlockMaterial(name="stone_bricks", color="gray", percentage=80, location="wall"),
        BlockMaterial(name="dark_oak_planks", color="brown", percentage=15, location="roof"),
        BlockMaterial(name="glass", color="transparent", percentage=5, location="window"),
    ],
    roof_material="dark_oak_planks",
    wall_material="stone_bricks",
    description="Medieval round tower with cylinder body and cone roof.",
)

# ── 模板 5：古典庙宇（穹顶）──
_CLASSICAL_TEMPLE = BuildingDSL(
    minecraft_version=MinecraftVersion.JAVA_1_20,
    building_type="temple",
    style="classical",
    width=12, length=12, height=10,
    floor_count=1, floor_height=8, wall_thickness=1,
    detail_scale=2,
    shape="square",
    components=[
        Component(name="main_body", shape="box", width=12, length=12, height=8,
                  position="center", material="quartz_block"),
        Component(name="dome", shape="sphere", radius=5, height=5,
                  offset_y=8, position="top", material="terracotta"),
    ],
    roof=RoofSpec(type="dome", height=5, material="terracotta"),
    walls=[WallSpec(type="pillar", thickness=1, material="quartz_block",
                    pillars=PillarSpec(count=8, spacing=1, width=1,
                                       material="quartz_pillar"))],
    windows=WindowSystem(items=[]),
    entrance=EntranceSpec(type="column_entrance", position="center", side="front",
                          width=3, height=4, has_columns=True, column_count=4,
                          has_roof_cover=True,
                          door_material="oak_door",
                          frame_material="quartz_block"),
    materials=[
        BlockMaterial(name="quartz_block", color="white", percentage=60, location="wall"),
        BlockMaterial(name="terracotta", color="orange", percentage=25, location="roof"),
        BlockMaterial(name="quartz_pillar", color="white", percentage=15, location="pillar"),
    ],
    platform_material="smooth_stone",
    roof_material="terracotta",
    wall_material="quartz_block",
    pillar_material="quartz_pillar",
    description="Classical temple with quartz walls, colonnade, and dome roof.",
)


# ── 模板注册表 ──
TEMPLATES = {
    "villa": _MODERN_VILLA,
    "gate": _CHINESE_GATE,
    "church": _GOTHIC_CHURCH,
    "tower": _ROUND_TOWER,
    "temple": _CLASSICAL_TEMPLE,
}


def analyze(
    image_path: str,
    version: MinecraftVersion = MinecraftVersion.JAVA_1_20,
) -> BuildingDSL:
    """Mock 分析：根据图片文件名选模板，返回 BuildingDSL。

    选择规则：
      - 文件名含 villa/house → 现代别墅
      - 文件名含 gate/chinese → 中式城门
      - 文件名含 church/cathedral → 哥特教堂
      - 文件名含 tower/castle → 圆塔
      - 文件名含 temple/palace → 古典庙宇
      - 其他 → 默认别墅
    """
    from pathlib import Path
    name = Path(image_path).stem.lower()

    if any(kw in name for kw in ["gate", "chinese", "tiananmen"]):
        template = _CHINESE_GATE
    elif any(kw in name for kw in ["church", "cathedral", "gothic"]):
        template = _GOTHIC_CHURCH
    elif any(kw in name for kw in ["tower", "castle", "round"]):
        template = _ROUND_TOWER
    elif any(kw in name for kw in ["temple", "palace", "classical"]):
        template = _CLASSICAL_TEMPLE
    else:
        template = _MODERN_VILLA

    # 返回副本，避免修改模板
    result = template.model_copy(deep=True)
    result.minecraft_version = version
    return result
