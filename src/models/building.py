from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MinecraftVersion(str, Enum):
    """支持的 Minecraft 版本"""

    JAVA_1_12 = "java-1.12"  # 数字方块 ID
    JAVA_1_13 = "java-1.13"  # 扁平化后，命名空间 ID
    JAVA_1_17 = "java-1.17"  # 洞穴与山崖
    JAVA_1_20 = "java-1.20"  # 最新稳定版
    BEDROCK_1_20 = "bedrock-1.20"  # 基岩版


# ═══════════════════════════════════════════════════════════════
#  V2 Building DSL —— component 级几何描述（按 V2 技术方案重写）
#  数据契约：AI 输出 → BuildingDSL → 生成器按 component 渲染
# ═══════════════════════════════════════════════════════════════


class BlockMaterial(BaseModel):
    """材料描述（含位置标签，V2 方案第 11 部分）"""

    name: str = Field(description="精确 Minecraft 方块名（如 white_concrete, red_terracotta）")
    color: Optional[str] = Field(None, description="颜色描述（如 深灰色）")
    percentage: float = Field(
        default=100.0, ge=0.0, le=100.0,
        description="占比 0~100（V2 方案用 percentage，非 fraction）",
    )
    location: str = Field(
        default="wall",
        description="材料所在部位: roof/wall/door/window/pillar/railing/cornice/platform/foundation/decoration",
    )


class GeometryRef(BaseModel):
    """几何尺寸引用（V2 方案第 2/3 部分）"""

    type: str = Field(
        description="几何类型: box/cylinder/sphere/cone/prism/arch/curve/custom",
    )
    width: int = Field(default=0, ge=0, description="X 方向尺寸（方块数）")
    length: int = Field(default=0, ge=0, description="Z 方向尺寸（方块数）")
    height: int = Field(default=0, ge=0, description="Y 方向尺寸（方块数）")
    radius: int = Field(default=0, ge=0, description="半径（cylinder/sphere/cone 用）")
    half_or_full: str = Field(
        default="full",
        description="sphere 时 half=半球（穹顶）/ full=全球",
    )


class Component(BaseModel):
    """建筑组件（V2 方案第 2 部分体块拆解）"""

    name: str = Field(
        description="组件名: main_body/side_wing/tower/roof/entrance/balcony/terrase/dome/spire/pillar_wall",
    )
    shape: str = Field(
        default="box",
        description="几何形状: box/cylinder/sphere/cone/prism/arch/curve/custom",
    )
    width: int = Field(default=0, ge=0, description="X 方向尺寸（方块数）")
    length: int = Field(default=0, ge=0, description="Z 方向尺寸（方块数）")
    height: int = Field(default=0, ge=0, description="Y 方向尺寸（方块数）")
    radius: int = Field(default=0, ge=0, description="半径（cylinder/sphere/cone 用）")
    position: str = Field(
        default="center",
        description="相对位置: front/back/left/right/center/front_left_corner/front_right_corner/back_left_corner/back_right_corner/top",
    )
    offset_x: int = Field(default=0, description="相对主体 X 偏移（方块数）")
    offset_y: int = Field(default=0, description="相对主体 Y 偏移（方块数）")
    offset_z: int = Field(default=0, description="相对主体 Z 偏移（方块数）")
    material: str = Field(default="", description="组件主材质，空则用全局对应部位材质")
    rotation_deg: int = Field(
        default=0, ge=0, le=360,
        description="绕 Y 轴旋转角度（0/90/180/270）",
    )


class RoofSpec(BaseModel):
    """屋顶系统（V2 方案第 6 部分）"""

    type: str = Field(
        default="flat",
        description="屋顶类型: flat/gable/hip/pyramid/dome/mansard/barrel/butterfly/sawtooth/spire/chinese_roof/xieshan/curved/eaved",
    )
    height: int = Field(default=0, ge=0, description="屋顶高度（方块数）")
    slope_angle: int = Field(default=0, ge=0, le=90, description="坡度角（度）")
    layer_count: int = Field(default=1, ge=1, le=10, description="屋顶层数/重檐数")
    overhang: int = Field(default=0, ge=0, description="屋檐外挑距离（方块数）")
    material: str = Field(default="", description="屋顶瓦面材质，空则用全局 roof")
    # 中式屋顶细节
    has_flying_eaves: bool = Field(default=False, description="是否有飞檐翘角")
    eaves_curvature: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="飞檐曲率 0~1（0=直檐，1=强翘起）",
    )
    # 哥特尖塔
    spire_height: int = Field(default=0, ge=0, description="尖塔高度（方块数）")
    spire_angle: int = Field(default=0, ge=0, le=90, description="尖顶角度")


class PillarSpec(BaseModel):
    """柱子规格（V2 方案第 7 部分墙体）"""

    count: int = Field(default=0, ge=0, description="柱子数量")
    spacing: int = Field(default=3, ge=1, description="柱间距（方块数）")
    width: int = Field(default=1, ge=1, description="柱宽（方块数）")
    protrusion: int = Field(default=0, ge=0, description="柱子凸出墙面距离（方块数）")
    material: str = Field(default="", description="柱子材质，空则用全局 pillar")


class WallSpec(BaseModel):
    """墙体系统（V2 方案第 7 部分）"""

    type: str = Field(
        default="plain_wall",
        description="墙体类型: plain_wall/pillar/pilaster/buttress/arcade/rustication/timber_frame",
    )
    thickness: int = Field(default=1, ge=1, description="墙厚（方块数）")
    material: str = Field(default="", description="墙体主材质，空则用全局 wall")
    pillars: PillarSpec = Field(default_factory=PillarSpec, description="柱子规格（type=pillar/pilaster 时生效）")


class WindowItem(BaseModel):
    """单个窗户（V2 方案第 8 部分）"""

    shape: str = Field(
        default="square",
        description="窗形: square/arch/pointed_arch/circle/bay_window/glass_wall",
    )
    floor: int = Field(default=1, ge=1, description="所在楼层（1 起算）")
    side: str = Field(default="front", description="所在立面: front/back/left/right")
    x: float = Field(default=0.5, ge=0.0, le=1.0, description="水平位置 0~1 比例")
    width: float = Field(default=0.15, ge=0.01, le=1.0, description="窗户宽度 0~1 比例")
    height: int = Field(default=2, ge=1, description="窗户高度（方块数）")
    y_offset: int = Field(default=1, ge=0, description="离地高度（方块数）")
    count: int = Field(default=1, ge=1, description="重复数量（排列时）")
    spacing: int = Field(default=3, ge=1, description="重复间距（方块数）")
    frame_material: str = Field(default="", description="窗框材质，空则用全局 trim")
    glass_material: str = Field(default="", description="玻璃材质，空则用全局 window_glass")


class WindowSystem(BaseModel):
    """窗户系统（V2 方案第 8 部分）"""

    arrangement: str = Field(
        default="symmetry",
        description="排列方式: grid/symmetry/vertical_repeat/single",
    )
    items: list[WindowItem] = Field(default_factory=list, description="窗户列表")


class EntranceSpec(BaseModel):
    """入口系统（V2 方案第 9 部分）"""

    type: str = Field(
        default="simple",
        description="入口类型: simple/arch/portal/porch/grand_stair/column_entrance",
    )
    position: str = Field(default="center", description="位置: center/left/right")
    side: str = Field(default="front", description="所在立面: front/back/left/right")
    width: int = Field(default=2, ge=0, description="门宽（方块数，0=无门洞）")
    height: int = Field(default=3, ge=0, description="门高（方块数，0=无门洞）")
    has_stairs: bool = Field(default=False, description="是否有台阶")
    stair_count: int = Field(default=0, ge=0, description="台阶数")
    has_columns: bool = Field(default=False, description="是否有门廊柱子")
    column_count: int = Field(default=0, ge=0, description="门廊柱数")
    has_roof_cover: bool = Field(default=False, description="是否有门廊屋顶")
    door_material: str = Field(default="", description="门板材质，空则用全局 door")
    frame_material: str = Field(default="", description="门框材质，空则用全局 trim")
    curvature: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="顶部曲率 0~1（type=arch/portal 时生效，0=直角过梁，1=半圆拱）",
    )


class CurveSpec(BaseModel):
    """曲线结构（V2 方案第 5 部分重点）"""

    type: str = Field(
        description="曲线类型: arch/flying_eaves/baroque_wall/dome/sphere/cylinder/free_curve",
    )
    # 圆形/球面参数
    radius: int = Field(default=0, ge=0, description="半径")
    height: int = Field(default=0, ge=0, description="高度")
    center_x: int = Field(default=0, description="中心 X")
    center_y: int = Field(default=0, description="中心 Y")
    center_z: int = Field(default=0, description="中心 Z")
    # 拱形参数
    width: int = Field(default=0, ge=0, description="拱宽")
    depth: int = Field(default=0, ge=0, description="拱深")
    curve_radius: int = Field(default=0, ge=0, description="曲率半径")
    arch_type: str = Field(
        default="semicircle",
        description="拱型: semicircle/pointed/ellipse",
    )
    # 自由曲线
    direction: str = Field(
        default="up",
        description="曲线方向: up/outward/inward（飞檐用）",
    )
    curvature: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="曲率 0~1（small/medium/large 量化为 0.3/0.6/1.0）",
    )
    material: str = Field(default="", description="曲线结构材质，空则用全局对应部位")


class BuildingDSL(BaseModel):
    """V2 Building DSL —— 建筑三维 Blueprint（按 V2 技术方案第 12 部分最终建模数据）。

    这是整个项目的新数据契约：AI 输出 → BuildingDSL → 生成器按 component 渲染。
    取代旧 BuildingDescription，schema 从 facade 级升到 component 级几何。
    """

    # ── 元信息（V2 第 1 部分）──
    minecraft_version: MinecraftVersion = Field(
        default=MinecraftVersion.JAVA_1_20,
        description="目标 Minecraft 版本",
    )
    building_name: str = Field(default="", description="建筑名称（如 天安门）")
    building_type: str = Field(
        description="建筑类型: church/villa/castle/temple/tower/palace/gate/house/bridge/skyscraper/pagoda/arch/pavilion",
    )
    style: str = Field(
        default="modern",
        description="建筑风格: modern/gothic/classical/baroque/asian/chinese_traditional/medieval/brutalist/renaissance/industrial",
    )
    location: str = Field(default="", description="建筑地点（国家/城市，Agent 1 输出）")

    # ── 尺寸（V2 第 4 部分）──
    width: int = Field(ge=1, le=1024, description="建筑总宽（方块数）")
    length: int = Field(ge=1, le=1024, description="建筑总深（方块数）")
    height: int = Field(ge=1, le=1024, description="建筑总高（方块数）")
    floor_count: int = Field(default=1, ge=1, le=100, description="楼层数")
    floor_height: int = Field(default=4, ge=2, le=20, description="每层高度（方块数）")
    wall_thickness: int = Field(default=1, ge=1, le=10, description="墙厚（方块数）")
    detail_scale: int = Field(
        default=1, ge=1, le=8,
        description="精细度缩放 1~3（小建筑=3，中=2，大=1）",
    )

    # ── 平面形状（V2 第 3 部分）──
    shape: str = Field(
        default="rectangle",
        description="平面形状: rectangle/square/L/U/T/cross/octagon/circle/complex",
    )

    # ── 几何 + 体块拆解（V2 第 2/12 部分）──
    geometry: GeometryRef = Field(
        default_factory=lambda: GeometryRef(type="box"),
        description="主体几何引用",
    )
    components: list[Component] = Field(
        default_factory=list,
        description="建筑组件列表（主体/侧翼/塔楼/屋顶/入口/阳台等），按 component 级几何渲染",
    )

    # ── 屋顶（V2 第 6 部分）──
    roof: RoofSpec = Field(default_factory=RoofSpec, description="屋顶规格")

    # ── 墙体（V2 第 7 部分）──
    walls: list[WallSpec] = Field(
        default_factory=list,
        description="墙体列表（每面墙一个 WallSpec）",
    )

    # ── 窗户（V2 第 8 部分）──
    windows: WindowSystem = Field(default_factory=WindowSystem, description="窗户系统")

    # ── 入口（V2 第 9 部分）──
    entrance: EntranceSpec = Field(default_factory=EntranceSpec, description="入口系统")

    # ── 曲线/曲面（V2 第 5 部分重点）──
    curves: list[CurveSpec] = Field(
        default_factory=list,
        description="所有非直线结构（圆塔/穹顶/拱/飞檐/曲墙）",
    )

    # ── 材料（V2 第 11 部分）──
    materials: list[BlockMaterial] = Field(
        default_factory=list,
        description="材料列表（含 location 部位标签）",
    )

    # ── 全局部位材质（方便生成器回退）──
    platform_material: str = Field(default="stone_bricks", description="台基材质")
    roof_material: str = Field(default="stone_bricks", description="屋顶瓦面材质")
    door_material: str = Field(default="dark_oak_door", description="门板材质")
    window_glass_material: str = Field(default="glass", description="窗玻璃材质")
    wall_material: str = Field(default="stone_bricks", description="墙体主材质")
    pillar_material: str = Field(default="chiseled_stone_bricks", description="立柱材质")
    trim_material: str = Field(default="polished_andesite", description="装饰线脚/窗框材质")
    railing_material: str = Field(default="oak_fence", description="栏杆材质")
    cornice_material: str = Field(default="polished_andesite", description="檐口材质")
    foundation_material: str = Field(default="smooth_stone", description="地基材质")

    # ── 兼容 V2 第 10 部分装饰细节（用文字描述，生成器按关键词识别）──
    decorations_description: str = Field(
        default="",
        description="装饰细节文字描述（雕刻/栏杆/横梁/装饰线/阳台/雕像 的名称+位置+尺寸+形状）",
    )

    # ── 工程报告（V2 第 12 部分）──
    description: str = Field(
        default="",
        description="建筑逆向工程报告全文（体块拆解+曲线+装饰+3D 形态），给工程师看",
    )

    # ── 搜索关键词（Agent 1 输出，供 Agent 2 网络搜索用）──
    keywords: list[str] = Field(
        default_factory=list,
        description="建筑搜索关键词（如 [\"天安门\", \"Tiananmen\", \"Beijing gate tower\"]）",
    )
