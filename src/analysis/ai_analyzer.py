"""V2 AI 分析器 —— 调用智谱 GLM-4V-Flash 分析建筑图片，输出 BuildingDSL。

按 V2 技术方案：
  1. Agent 1 建筑识别（name/location/style/keywords）
  2. 12 部分测绘思维框架 → 映射到 BuildingDSL schema
  3. 部位级材质 + 按风格自动选材
  4. component 级几何描述（box/cylinder/sphere/cone/arch/curve）
  5. 曲线/曲面结构单独识别

输出 BuildingDSL（取代旧 BuildingDescription），用 Pydantic 校验。
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import httpx

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

# 智谱 GLM-4V-Flash 的 API 配置
ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
ZHIPU_MODEL = "glm-4.6v-flash"  # 免费，128K 上下文，32K 输出（V2 方案 MVP 模型）

SYSTEM_PROMPT = """你是一名世界级建筑测绘专家、建筑设计师、3D 建模工程师以及 Minecraft 程序化建筑生成专家。

你的任务不是描述图片内容。
你的任务是根据建筑照片，生成一份可以用于三维重建的建筑逆向工程报告。
你的输出必须达到：另一个建筑工程师只依靠你的描述，可以在 Minecraft 中重新构建该建筑。

请进行精确、工程化分析。
禁止：简单描述、模糊形容词、只说建筑风格、只识别建筑名称。
必须输出：尺寸、比例、结构、位置、曲线、材料、装饰、几何关系。

==========================================================
【分析思维框架】——按以下 12 部分思考（思考过程不输出，仅用于推导最终 JSON）
==========================================================
第 1 部分 总体测绘：建筑类型、风格、整体比例 width:length:height、地点、搜索关键词
第 2 部分 体块拆解：主体/侧翼/塔楼/屋顶/入口/阳台/露台 各为何种几何（box/cylinder/sphere/cone/prism/arch/curve）、尺寸、相对位置
第 3 部分 平面形状：rectangle/square/L/U/T/cross/octagon/circle/complex
第 4 部分 精确尺寸：整体宽深高、楼层数、每层高度、墙厚
第 5 部分 曲线曲面（重点）：圆形（圆柱/圆塔/圆顶）、球面（穹顶）、拱形（门拱/窗拱，arch_type=semicircle/pointed/ellipse）、自由曲线（中式飞檐 direction+curvature）
第 6 部分 屋顶详细建模：类型 flat/gable/hip/pyramid/dome/mansard/barrel/spire/chinese_roof、roof_height、layer_count、overhang；中式分析飞檐；哥特分析尖塔
第 7 部分 墙体结构：基础墙 material+thickness，墙面 plain_wall/pillar/pilaster/buttress/arcade/rustication/timber_frame，柱子数量+间距+凸出
第 8 部分 窗户精确分析：每层每面窗数量、位置、尺寸、形状 square/arch/pointed_arch/circle/bay_window/glass_wall、排列 grid/symmetry/vertical_repeat
第 9 部分 入口系统：位置 center/left/right、结构 simple/arch/portal/porch/grand_stair/column_entrance、尺寸、附属 stairs/columns/roof_cover
第 10 部分 装饰细节：雕刻/栏杆/横梁/装饰线/阳台/雕像 的名称+位置+尺寸+形状
第 11 部分 材料分析：每种材料的 location（roof/wall/door/window/pillar/railing/cornice/platform）+ color + percentage
第 12 部分 最终三维建模数据：把上述所有分析映射到下面的 JSON schema 输出

==========================================================
【尺寸估算规则】
==========================================================
Minecraft 中 1 方块 ≈ 1 米。用图片中的参照物推算尺寸：
  - 一扇门 ≈ 2 格高、1 格宽
  - 一层楼 ≈ 3-4 格高
  一扇普通窗户 ≈ 1-2 格高
  一个人 ≈ 1.8 格高
  一辆轿车 ≈ 4 格长、1.5 格高
所有维度必须在 1~256 之间。
精细度缩放 detail_scale：小型建筑（≤15m）=3，中型（15~40m）=2，大型（>40m）=1。
如果图片无法直接测量，根据建筑类型推断合理估算值，不要回答"无法判断"。

==========================================================
【材料多样化 + 部位级材质】——这是最关键要求
==========================================================
你**必须**为建筑的不同部位分别指定材质，不能整栋建筑只用一两种方块。
本方块库支持 200+ 种方块（16 色 concrete、16 色 terracotta、16 色 glazed_terracotta、copper 全家桶、prismarine 全家桶、quartz 全家桶、各种木材、各种石砖）。

部位级材质字段（每个都是**精确的 Minecraft 方块名**字符串）：
- materials: 材料列表（含 name/color/percentage/location），建议 3~6 种
- platform_material/roof_material/door_material/window_glass_material: 全局部位材质
- wall_material/pillar_material/trim_material/railing_material/cornice_material/foundation_material: 全局部位材质
- components[].material: 组件主材质
- walls[].material + walls[].pillars.material: 墙体+柱子材质
- windows.items[].frame_material + glass_material: 窗框+玻璃材质
- entrance.door_material + frame_material: 门板+门框材质
- curves[].material: 曲线结构材质

【按风格自动选材范式】
- modern（现代）：墙 white_concrete/gray_concrete/light_gray_concrete；屋顶 gray_concrete 或 blue_stained_glass（玻璃幕墙）；窗 blue_stained_glass；柱 polished_andesite；门 dark_oak_door
- chinese_traditional（中式传统）：墙 red_terracotta 或 red_concrete；瓦 red_terracotta 或 black_concrete；柱 chiseled_stone_bricks 或 dark_oak_planks；台基 stone_bricks；窗框 dark_oak_planks；门 dark_oak_door；栏杆 oak_fence
- classical（古典）：墙 quartz_block 或 white_concrete；屋顶 terracotta 或 quartz_block；柱 quartz_pillar；台基 smooth_stone；檐口 quartz_block；门 oak_door
- gothic（哥特）：墙 stone_bricks 或 deepslate_bricks；屋顶 black_concrete；窗 blue_stained_glass/red_stained_glass（花窗）；柱 chiseled_stone_bricks；门 dark_oak_door
- baroque（巴洛克）：墙 white_concrete 或 quartz_block；屋顶 terracotta；柱 quartz_pillar；檐口 chiseled_quartz_block；窗 blue_stained_glass；门 dark_oak_door
- brutalist（粗野主义）：墙 gray_concrete 或 exposed_copper；屋顶 gray_concrete；窗 glass；门 iron_door
- medieval（中世纪）：墙 stone_bricks 或 cobblestone；屋顶 dark_oak_planks；窗 glass；柱 oak_planks；门 dark_oak_door
- industrial（工业）：墙 exposed_copper 或 iron_block；屋顶 gray_concrete；窗 glass；门 iron_door

材料名必须是精确的 Minecraft 方块名（如下所列），不要用"wood"用"oak_planks"，不要用"stone"用"stone_bricks"！

按颜色分类的材料：
🔴 红色/橙色系: red_concrete, red_terracotta, red_wool, bricks, red_sandstone, nether_bricks, orange_concrete, orange_terracotta
🟡 黄色/金色系: gold_block, yellow_terracotta, yellow_concrete, smooth_quartz, birch_planks, hay_block
⚪ 白色/浅色系: quartz_block, chiseled_quartz_block, quartz_pillar, white_concrete, white_terracotta, white_wool, smooth_stone
⬜ 灰色系: stone, stone_bricks, cobblestone, andesite, polished_andesite, deepslate, deepslate_bricks, gray_concrete, light_gray_concrete, terracotta
🟫 棕色系: oak_planks, spruce_planks, dark_oak_planks, jungle_planks, birch_planks, acacia_planks, crimson_planks, warped_planks
🟦 蓝色系: blue_concrete, blue_wool, glass, blue_stained_glass, light_blue_stained_glass, cyan_stained_glass, prismarine, prismarine_bricks, dark_prismarine
🟩 绿色系: green_terracotta, green_concrete, copper_block, exposed_copper, weathered_copper, oxidized_copper, mossy_stone_bricks
⬛ 深色系: black_concrete, black_wool, blackstone, blackstone_bricks, obsidian, deepslate_bricks
特殊: iron_block, iron_bars, iron_door, gold_block, copper_block, snow_block, packed_ice, oak_door/spruce_door/dark_oak_door/jungle_door, oak_fence/spruce_fence/dark_oak_fence, stone_brick_wall/cobblestone_wall

==========================================================
【最终输出 JSON schema】——把 12 部分分析映射到 BuildingDSL
==========================================================
{
  // 第 1 部分：总体测绘
  "building_name": "只有非常确定时才填，如\"天安门\"，否则空字符串",
  "building_type": "church|villa|castle|temple|tower|palace|gate|house|bridge|skyscraper|pagoda|arch|pavilion",
  "style": "modern|gothic|classical|baroque|asian|chinese_traditional|medieval|brutalist|renaissance|industrial",
  "location": "建筑地点（国家/城市）",
  "keywords": ["建筑名", "英文名", "地点关键词"],

  // 第 4 部分：尺寸
  "width": 整数 1-256,
  "length": 整数 1-256,
  "height": 整数 1-256,
  "floor_count": 楼层数,
  "floor_height": 每层高度（方块数）,
  "wall_thickness": 墙厚（方块数）,
  "detail_scale": 1|2|3,

  // 第 3 部分：平面形状
  "shape": "rectangle|square|L|U|T|cross|octagon|circle",

  // 第 2 部分体块拆解 → components
  "components": [
    {
      "name": "main_body|side_wing|tower|roof|entrance|balcony|terrase|dome|spire|pillar_wall",
      "shape": "box|cylinder|sphere|cone|prism|arch|curve|custom",
      "width": X 方向尺寸,
      "length": Z 方向尺寸,
      "height": Y 方向尺寸,
      "radius": 半径（cylinder/sphere/cone 用，其他填 0）,
      "position": "center|front|back|left|right|front_left_corner|front_right_corner|back_left_corner|back_right_corner|top",
      "offset_x": 相对 X 偏移,
      "offset_y": 相对 Y 偏移,
      "offset_z": 相对 Z 偏移,
      "material": "组件主材质方块名",
      "rotation_deg": 0|90|180|270
    }
  ],

  // 第 6 部分屋顶
  "roof": {
    "type": "flat|gable|hip|pyramid|dome|mansard|barrel|spire|chinese_roof",
    "height": 屋顶高度,
    "layer_count": 屋顶层数/重檐数,
    "overhang": 屋檐外挑距离,
    "material": "屋顶瓦面材质",
    "has_flying_eaves": true|false（中式飞檐）,
    "eaves_curvature": 0~1（飞檐曲率）,
    "spire_height": 尖塔高度（哥特用）,
    "spire_angle": 尖顶角度
  },

  // 第 7 部分墙体
  "walls": [
    {
      "type": "plain_wall|pillar|pilaster|buttress|arcade|rustication|timber_frame",
      "thickness": 墙厚,
      "material": "墙体材质",
      "pillars": {"count":数量, "spacing":间距, "width":柱宽, "protrusion":凸出, "material":"柱材质"}
    }
  ],

  // 第 8 部分窗户
  "windows": {
    "arrangement": "grid|symmetry|vertical_repeat|single",
    "items": [
      {"shape":"square|arch|pointed_arch|circle|bay_window|glass_wall",
       "floor":楼层, "side":"front|back|left|right",
       "x":0~1, "width":0~1, "height":方块数, "y_offset":离地高度,
       "count":重复数, "spacing":间距,
       "frame_material":"窗框材质", "glass_material":"玻璃材质"}
    ]
  },

  // 第 9 部分入口
  "entrance": {
    "type": "simple|arch|portal|porch|grand_stair|column_entrance",
    "position": "center|left|right",
    "side": "front|back|left|right",
    "width": 门宽, "height": 门高,
    "has_stairs": true|false, "stair_count": 台阶数,
    "has_columns": true|false, "column_count": 门廊柱数,
    "has_roof_cover": true|false,
    "door_material": "门板材质", "frame_material": "门框材质",
    "curvature": 0~1（type=arch/portal 时，0=直角过梁，1=半圆拱）
  },

  // 第 5 部分曲线曲面
  "curves": [
    {
      "type": "arch|flying_eaves|baroque_wall|dome|sphere|cylinder|free_curve",
      "radius": 半径, "height": 高度,
      "center_x": 中心X, "center_y": 中心Y, "center_z": 中心Z,
      "width": 拱宽, "depth": 拱深, "curve_radius": 曲率半径,
      "arch_type": "semicircle|pointed|ellipse",
      "direction": "up|outward|inward",
      "curvature": 0~1,
      "material": "曲线结构材质"
    }
  ],

  // 第 11 部分材料
  "materials": [
    {"name":"精确方块名", "color":"颜色描述", "percentage":0~100, "location":"roof|wall|door|window|pillar|railing|cornice|platform|foundation|decoration"}
  ],

  // 全局部位材质（生成器回退用）
  "platform_material": "台基材质",
  "roof_material": "屋顶材质",
  "door_material": "门板材质",
  "window_glass_material": "窗玻璃材质",
  "wall_material": "墙体主材质",
  "pillar_material": "立柱材质",
  "trim_material": "装饰线脚材质",
  "railing_material": "栏杆材质",
  "cornice_material": "檐口材质",
  "foundation_material": "地基材质",

  // 第 10 部分装饰细节（文字描述）
  "decorations_description": "雕刻/栏杆/横梁/装饰线/阳台/雕像 的名称+位置+尺寸+形状",

  // 第 12 部分工程报告
  "description": "建筑逆向工程报告全文（体块拆解+曲线+装饰+3D 形态），给工程师看"
}

注意：
- 所有材质字段必须是精确 Minecraft 方块名字符串（见上面色卡），不要输出对象/字典
- 如果只能看到正面，components 至少包含 main_body，其他面可推断
- 尺寸给不出精确值时根据建筑类型推断合理估算值

只输出 JSON，不要输出其他内容。"""


def _coerce_material(mat) -> str:
    """把 AI 返回的材质字段归一化为字符串。

    AI 有时把字符串字段输出成 dict（含 name/color）。代码层容错。
    """
    if isinstance(mat, dict):
        return str(mat.get("name", "") or "")
    if isinstance(mat, str):
        return mat
    return ""


def _coerce_int(val, default: int = 0) -> int:
    """把 AI 返回的数值字段归一化为 int（容错字符串/float/None）。"""
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return default


def _coerce_float(val, default: float = 0.0) -> float:
    """把 AI 返回的数值字段归一化为 float。"""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _clamp(val: float, lo: float, hi: float) -> float:
    """把值夹到 [lo, hi] 范围（AI 输出脏数据时用）。"""
    return max(lo, min(hi, val))


def _encode_image(image_path: str, max_dim: int = 256) -> tuple[str, str]:
    """将图片压缩后转为 base64 字符串，返回 (base64_data, mime_type)。

    智谱 API 限制 inputs + max_new_tokens <= 16384，大图必须压缩。
    """
    from PIL import Image
    import io

    ext = Path(image_path).suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}
    mime = mime_map.get(ext, "image/jpeg")

    img = Image.open(image_path)
    w, h = img.size
    if max(w, h) > max_dim:
        ratio = max_dim / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    buf = io.BytesIO()
    if mime == "image/png":
        img.save(buf, format="PNG")
    else:
        img.save(buf, format="JPEG", quality=85)
    data = base64.b64encode(buf.getvalue()).decode("utf-8")
    return data, mime


def _parse_components(raw_components: list) -> list[Component]:
    """解析 AI 输出的 components 列表。"""
    components = []
    for c in raw_components or []:
        if not isinstance(c, dict):
            continue
        components.append(Component(
            name=c.get("name", "main_body"),
            shape=c.get("shape", "box"),
            width=_coerce_int(c.get("width", 0)),
            length=_coerce_int(c.get("length", 0)),
            height=_coerce_int(c.get("height", 0)),
            radius=_coerce_int(c.get("radius", 0)),
            position=c.get("position", "center"),
            offset_x=_coerce_int(c.get("offset_x", 0)),
            offset_y=_coerce_int(c.get("offset_y", 0)),
            offset_z=_coerce_int(c.get("offset_z", 0)),
            material=_coerce_material(c.get("material", "")),
            rotation_deg=_coerce_int(c.get("rotation_deg", 0)),
        ))
    return components


def _parse_roof(raw_roof: dict) -> RoofSpec:
    """解析屋顶规格。"""
    r = raw_roof or {}
    return RoofSpec(
        type=r.get("type", "flat"),
        height=_coerce_int(r.get("height", 0)),
        slope_angle=_coerce_int(r.get("slope_angle", 0)),
        layer_count=max(1, _coerce_int(r.get("layer_count", 1), 1)),
        overhang=_coerce_int(r.get("overhang", 0)),
        material=_coerce_material(r.get("material", "")),
        has_flying_eaves=bool(r.get("has_flying_eaves", False)),
        eaves_curvature=_clamp(_coerce_float(r.get("eaves_curvature", 0.0)), 0.0, 1.0),
        spire_height=_coerce_int(r.get("spire_height", 0)),
        spire_angle=_coerce_int(r.get("spire_angle", 0)),
    )


def _parse_walls(raw_walls: list) -> list[WallSpec]:
    """解析墙体列表。"""
    walls = []
    for w in raw_walls or []:
        if not isinstance(w, dict):
            continue
        pillars_raw = w.get("pillars", {}) or {}
        pillars = PillarSpec(
            count=_coerce_int(pillars_raw.get("count", 0)),
            spacing=max(1, _coerce_int(pillars_raw.get("spacing", 3), 3)),
            width=max(1, _coerce_int(pillars_raw.get("width", 1), 1)),
            protrusion=_coerce_int(pillars_raw.get("protrusion", 0)),
            material=_coerce_material(pillars_raw.get("material", "")),
        )
        walls.append(WallSpec(
            type=w.get("type", "plain_wall"),
            thickness=max(1, _coerce_int(w.get("thickness", 1), 1)),
            material=_coerce_material(w.get("material", "")),
            pillars=pillars,
        ))
    return walls


def _parse_windows(raw_windows: dict) -> WindowSystem:
    """解析窗户系统。"""
    w = raw_windows or {}
    items = []
    for item in w.get("items", []) or []:
        if not isinstance(item, dict):
            continue
        items.append(WindowItem(
            shape=item.get("shape", "square"),
            floor=max(1, _coerce_int(item.get("floor", 1), 1)),
            side=item.get("side", "front"),
            x=_clamp(_coerce_float(item.get("x", 0.5)), 0.0, 1.0),
            width=_clamp(_coerce_float(item.get("width", 0.15)), 0.01, 1.0),
            height=max(1, _coerce_int(item.get("height", 2), 2)),
            y_offset=max(0, _coerce_int(item.get("y_offset", 1), 1)),
            count=max(1, _coerce_int(item.get("count", 1), 1)),
            spacing=max(1, _coerce_int(item.get("spacing", 3), 3)),
            frame_material=_coerce_material(item.get("frame_material", "")),
            glass_material=_coerce_material(item.get("glass_material", "")),
        ))
    return WindowSystem(arrangement=w.get("arrangement", "symmetry"), items=items)


def _parse_entrance(raw_entrance: dict) -> EntranceSpec:
    """解析入口系统。"""
    e = raw_entrance or {}
    return EntranceSpec(
        type=e.get("type", "simple"),
        position=e.get("position", "center"),
        side=e.get("side", "front"),
        width=_coerce_int(e.get("width", 2), 2),
        height=_coerce_int(e.get("height", 3), 3),
        has_stairs=bool(e.get("has_stairs", False)),
        stair_count=_coerce_int(e.get("stair_count", 0)),
        has_columns=bool(e.get("has_columns", False)),
        column_count=_coerce_int(e.get("column_count", 0)),
        has_roof_cover=bool(e.get("has_roof_cover", False)),
        door_material=_coerce_material(e.get("door_material", "")),
        frame_material=_coerce_material(e.get("frame_material", "")),
        curvature=_clamp(_coerce_float(e.get("curvature", 0.0)), 0.0, 1.0),
    )


def _parse_curves(raw_curves: list) -> list[CurveSpec]:
    """解析曲线结构列表。"""
    curves = []
    for c in raw_curves or []:
        if not isinstance(c, dict):
            continue
        curves.append(CurveSpec(
            type=c.get("type", "arch"),
            radius=_coerce_int(c.get("radius", 0)),
            height=_coerce_int(c.get("height", 0)),
            center_x=_coerce_int(c.get("center_x", 0)),
            center_y=_coerce_int(c.get("center_y", 0)),
            center_z=_coerce_int(c.get("center_z", 0)),
            width=_coerce_int(c.get("width", 0)),
            depth=_coerce_int(c.get("depth", 0)),
            curve_radius=_coerce_int(c.get("curve_radius", 0)),
            arch_type=c.get("arch_type", "semicircle"),
            direction=c.get("direction", "up"),
            curvature=_clamp(_coerce_float(c.get("curvature", 0.0)), 0.0, 1.0),
            material=_coerce_material(c.get("material", "")),
        ))
    return curves


def _parse_materials(raw_materials: list) -> list[BlockMaterial]:
    """解析材料列表。"""
    materials = []
    for m in raw_materials or []:
        if isinstance(m, dict):
            materials.append(BlockMaterial(
                name=_coerce_material(m.get("name", "")) or str(m.get("name", "stone")),
                color=m.get("color"),
                percentage=_coerce_float(m.get("percentage", 100.0), 100.0),
                location=m.get("location", "wall"),
            ))
        elif isinstance(m, str):
            materials.append(BlockMaterial(name=m))
    return materials


def _parse_building_dsl(raw: dict, version: MinecraftVersion) -> BuildingDSL:
    """把 AI 返回的 raw dict 解析为 BuildingDSL（含容错归一化）。"""
    return BuildingDSL(
        minecraft_version=version,
        building_name=raw.get("building_name", ""),
        building_type=raw.get("building_type", "house"),
        style=raw.get("style", "modern"),
        location=raw.get("location", ""),
        keywords=raw.get("keywords", []) or [],
        width=max(1, _coerce_int(raw.get("width", 10), 10)),
        length=max(1, _coerce_int(raw.get("length", 10), 10)),
        height=max(1, _coerce_int(raw.get("height", 8), 8)),
        floor_count=max(1, _coerce_int(raw.get("floor_count", 1), 1)),
        floor_height=max(2, _coerce_int(raw.get("floor_height", 4), 4)),
        wall_thickness=max(1, _coerce_int(raw.get("wall_thickness", 1), 1)),
        detail_scale=max(1, min(8, _coerce_int(raw.get("detail_scale", 1), 1))),
        shape=raw.get("shape", "rectangle"),
        geometry={"type": raw.get("shape", "box")},  # 简化
        components=_parse_components(raw.get("components", [])),
        roof=_parse_roof(raw.get("roof", {})),
        walls=_parse_walls(raw.get("walls", [])),
        windows=_parse_windows(raw.get("windows", {})),
        entrance=_parse_entrance(raw.get("entrance", {})),
        curves=_parse_curves(raw.get("curves", [])),
        materials=_parse_materials(raw.get("materials", [])),
        platform_material=_coerce_material(raw.get("platform_material", "")) or "stone_bricks",
        roof_material=_coerce_material(raw.get("roof_material", "")) or "stone_bricks",
        door_material=_coerce_material(raw.get("door_material", "")) or "dark_oak_door",
        window_glass_material=_coerce_material(raw.get("window_glass_material", "")) or "glass",
        wall_material=_coerce_material(raw.get("wall_material", "")) or "stone_bricks",
        pillar_material=_coerce_material(raw.get("pillar_material", "")) or "chiseled_stone_bricks",
        trim_material=_coerce_material(raw.get("trim_material", "")) or "polished_andesite",
        railing_material=_coerce_material(raw.get("railing_material", "")) or "oak_fence",
        cornice_material=_coerce_material(raw.get("cornice_material", "")) or "polished_andesite",
        foundation_material=_coerce_material(raw.get("foundation_material", "")) or "smooth_stone",
        decorations_description=raw.get("decorations_description", ""),
        description=raw.get("description", ""),
    )


def _get_env_key() -> str | None:
    """从环境变量读取智谱 API Key。"""
    import os
    return os.environ.get("ZHIPU_API_KEY", None)


def _call_zhipu_api(api_key: str, image_data: str, mime: str) -> dict:
    """调用智谱 GLM-4.6V-Flash API，返回 raw JSON dict。

    含 429 限流指数退避重试（最多 3 次）+ 4.6V 失败时 fallback 到 4V-Flash。
    """
    import time
    url = f"{ZHIPU_BASE_URL}chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": ZHIPU_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{image_data}"
                        }
                    },
                    {
                        "type": "text",
                        "text": "分析这张建筑照片，按 schema 输出 JSON。"
                    }
                ]
            }
        ],
        "max_tokens": 8192,  # GLM-4.6V-Flash 上限 32K，给 8K 留足 BuildingDSL JSON 输出空间
        "temperature": 0.1,
    }

    # 4.6V 失败时按优先级 fallback：4.1V-Thinking-Flash（16K 输出）→ 4V-Flash（1K 输出，最后兜底）
    fallback_chain = [
        {"model": "glm-4.1v-thinking-flash", "max_tokens": 4096},
        {"model": "glm-4v-flash", "max_tokens": 1024},
    ]

    max_retries = 5  # 4.6V 是免费热门模型，高峰期需要多试几次
    last_error = None
    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=90.0) as client:
                response = client.post(url, headers=headers, json=payload)
                if response.status_code == 429:
                    # 限流，指数退避 + 抖动：2/4/6/8/10s
                    wait = 2 * (attempt + 1)
                    time.sleep(wait)
                    last_error = f"429 限流（重试 {attempt+1}/{max_retries}，等了 {wait}s）"
                    continue
                response.raise_for_status()
                result = response.json()
                try:
                    return _extract_content(result)
                except json.JSONDecodeError as e:
                    # 4.6V 输出被截断（罕见，max_tokens=8192 通常够）
                    last_error = f"JSON 解析失败: {e}"
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue
                    raise
        except httpx.HTTPStatusError as e:
            last_error = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
            if e.response.status_code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            raise
        except json.JSONDecodeError as e:
            last_error = f"JSON 解析失败（输出可能被截断）: {e}"
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            raise
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            raise

    # 4.6V 五次都失败，按 fallback 链尝试其他免费视觉模型
    for fb in fallback_chain:
        fb_payload = {**payload, "model": fb["model"], "max_tokens": fb["max_tokens"]}
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(url, headers=headers, json=fb_payload)
                response.raise_for_status()
                result = response.json()
                try:
                    return _extract_content(result)
                except json.JSONDecodeError as e:
                    # 截断的 JSON 尝试修复
                    content = _extract_raw_content(result)
                    repaired = _try_repair_json(content)
                    if repaired is not None:
                        return repaired
                    last_error = f"{fb['model']} JSON 截断无法修复: {e}"
                    continue
        except Exception as e:
            last_error = f"{fb['model']} 失败: {e}"
            continue

    raise RuntimeError(f"所有视觉模型都失败。最后错误：{last_error}")


def _extract_raw_content(result: dict) -> str:
    """从 API 响应提取原始 content 字符串（不去 markdown、不解析）。"""
    content = result["choices"][0]["message"]["content"]
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)
    return content


def _try_repair_json(content: str) -> dict | None:
    """尝试修复被截断的 JSON（补全未闭合的 } 和 ]）。

    AI 输出被 max_tokens 截断时，JSON 可能不完整。
    策略：
      1. 找最后一个完整闭合的 } 或 ]（任何 depth），截到那里 + 补全外层
      2. 如果找不到，粗暴补全缺失的 } 和 ]
    """
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 统计未闭合的 { 和 [，并记录最后一个完整闭合位置
    last_complete = -1
    depth_brace = 0
    depth_bracket = 0
    in_string = False
    escape = False
    for i, ch in enumerate(content):
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"' and not escape:
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth_brace += 1
        elif ch == "}":
            depth_brace -= 1
            last_complete = i  # 记录任何 } 闭合位置（含嵌套）
        elif ch == "[":
            depth_bracket += 1
        elif ch == "]":
            depth_bracket -= 1
            last_complete = i  # 记录任何 ] 闭合位置

    if last_complete >= 0:
        # 截到最后一个完整闭合位置，然后补全外层缺失的 ] 和 }
        truncated = content[:last_complete + 1]
        # 重新统计截断后的 depth
        d_brace = 0
        d_bracket = 0
        in_str = False
        esc = False
        for ch in truncated:
            if esc:
                esc = False
                continue
            if ch == "\\":
                esc = True
                continue
            if ch == '"' and not esc:
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == "{":
                d_brace += 1
            elif ch == "}":
                d_brace -= 1
            elif ch == "[":
                d_bracket += 1
            elif ch == "]":
                d_bracket -= 1
        # 去掉末尾逗号
        truncated = truncated.rstrip()
        if truncated.endswith(","):
            truncated = truncated[:-1]
        truncated += "]" * max(0, d_bracket) + "}" * max(0, d_brace)
        try:
            return json.loads(truncated)
        except json.JSONDecodeError:
            pass

    # 最后手段：粗暴补全 } 和 ]
    needs_braces = max(0, depth_brace)
    needs_brackets = max(0, depth_bracket)
    if needs_braces or needs_brackets:
        # 截掉末尾不完整的 token：找最后一个值结束位置（数字/"/}/]）
        # 跳过末尾的逗号/空格/冒号等分隔符
        cut = len(content)
        for i in range(len(content) - 1, max(0, len(content) - 80), -1):
            ch = content[i]
            if ch in ' \t\n\r,':
                continue
            if ch in '"}]}0123456789truefalsn':
                cut = i + 1
                break
        content = content[:cut] + "]" * needs_brackets + "}" * needs_braces
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # 再试一次：去掉末尾逗号
            content = content.rstrip()
            if content.endswith(","):
                content = content[:-1]
            content = content + "]" * needs_brackets + "}" * needs_braces
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return None
    return None


def _extract_content(result: dict) -> dict:
    """从 API 响应提取 content，去 markdown 包裹，解析为 dict。

    JSON 解析失败时尝试修复截断的 JSON。
    """
    content = _extract_raw_content(result)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # 尝试修复截断的 JSON
        repaired = _try_repair_json(content)
        if repaired is not None:
            return repaired
        raise


def analyze(
    image_path: str,
    version: MinecraftVersion = MinecraftVersion.JAVA_1_20,
    api_key: str | None = None,
) -> BuildingDSL:
    """分析建筑图片，返回 BuildingDSL。

    Args:
        image_path: 图片文件路径
        version: 目标 Minecraft 版本
        api_key: 智谱 API Key（None 则从 ZHIPU_API_KEY 环境变量读）

    Returns:
        BuildingDSL 建筑逆向工程数据契约
    """
    key = api_key or _get_env_key()
    if not key:
        raise ValueError("缺少智谱 API Key，请设置 ZHIPU_API_KEY 环境变量或传 api_key 参数")

    image_data, mime = _encode_image(image_path)
    raw = _call_zhipu_api(key, image_data, mime)
    return _parse_building_dsl(raw, version)
