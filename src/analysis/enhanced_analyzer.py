"""V2 Agent 3：多视角建筑融合 —— AI 分析 + Wikipedia 数据融合 + 多角度照片合并。

按 V2 技术方案：
  1. 多张照片分别走 ai_analyzer.analyze() → BuildingDSL
  2. 合并多视角结果（取最大尺寸、合并 components/curves、按方向去重 facades→windows）
  3. 如果识别到建筑名称，查 Wikipedia 获取真实尺寸校准
  4. 输出融合后的 BuildingDSL

取代旧 enhanced_analyzer（基于 BuildingDescription）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.analysis.ai_analyzer import analyze as ai_analyze
from src.models.building import (
    BlockMaterial,
    BuildingDSL,
    Component,
    CurveSpec,
    MinecraftVersion,
    WallSpec,
    WindowItem,
)
from src.utils.wikipedia import lookup_building, meters_to_blocks


def _merge_dsls(dsls: list[BuildingDSL]) -> BuildingDSL:
    """合并多张照片的 BuildingDSL（Agent 3 核心逻辑）。

    策略：
      - 尺寸取最大（不同角度看到的不同维度）
      - components 合并去重（按 name）
      - curves 合并去重（按 type+center）
      - windows.items 合并（按 side 去重，后覆盖前）
      - walls 合并（按 type 去重）
      - materials 合并（按 name 去重）
      - building_name/location/keywords 取首个非空
      - description 拼接所有角度的描述
    """
    if not dsls:
        raise ValueError("没有 DSL 可以合并")
    if len(dsls) == 1:
        return dsls[0]

    base = dsls[0].model_copy(deep=True)

    for d in dsls[1:]:
        # 取最大尺寸
        base.height = max(base.height, d.height)
        base.width = max(base.width, d.width)
        base.length = max(base.length, d.length)
        base.floor_count = max(base.floor_count, d.floor_count)
        base.detail_scale = max(base.detail_scale, d.detail_scale)

        # 元信息：取首个非空
        if d.building_name and not base.building_name:
            base.building_name = d.building_name
        if d.location and not base.location:
            base.location = d.location
        if d.style and d.style != "modern" and base.style == "modern":
            base.style = d.style
        if d.keywords:
            existing = set(base.keywords)
            for kw in d.keywords:
                if kw not in existing:
                    base.keywords.append(kw)
                    existing.add(kw)

        # components 合并去重（按 name）
        existing_comp_names = {c.name for c in base.components}
        for c in d.components:
            if c.name not in existing_comp_names:
                base.components.append(c)
                existing_comp_names.add(c.name)

        # curves 合并去重（按 type+center 近似）
        for curve in d.curves:
            # 简单去重：同 type 且 center 相同的跳过
            is_dup = any(
                c.type == curve.type
                and c.center_x == curve.center_x
                and c.center_y == curve.center_y
                and c.center_z == curve.center_z
                for c in base.curves
            )
            if not is_dup:
                base.curves.append(curve)

        # windows.items 合并（按 side+floor+x 近似去重，后覆盖前）
        for new_win in d.windows.items:
            is_dup = any(
                w.side == new_win.side
                and w.floor == new_win.floor
                and abs(w.x - new_win.x) < 0.05
                for w in base.windows.items
            )
            if is_dup:
                # 后覆盖前：移除旧的，加新的
                base.windows.items = [
                    w for w in base.windows.items
                    if not (w.side == new_win.side
                            and w.floor == new_win.floor
                            and abs(w.x - new_win.x) < 0.05)
                ]
            base.windows.items.append(new_win)

        # walls 合并（按 type 去重，后覆盖前）
        for new_wall in d.walls:
            base.walls = [w for w in base.walls if w.type != new_wall.type]
            base.walls.append(new_wall)

        # materials 合并（按 name 去重）
        existing_mat_names = {m.name for m in base.materials}
        for m in d.materials:
            if m.name not in existing_mat_names:
                base.materials.append(m)
                existing_mat_names.add(m.name)

        # 屋顶：取更复杂的（layer_count 大的优先）
        if d.roof.layer_count > base.roof.layer_count:
            base.roof = d.roof.model_copy(deep=True)

        # 入口：取更复杂的（has_stairs/has_columns 多的优先）
        d_ent_complex = sum([d.entrance.has_stairs, d.entrance.has_columns,
                             d.entrance.has_roof_cover])
        base_ent_complex = sum([base.entrance.has_stairs, base.entrance.has_columns,
                                base.entrance.has_roof_cover])
        if d_ent_complex > base_ent_complex:
            base.entrance = d.entrance.model_copy(deep=True)

        # 全局部位材质：取首个非默认值
        for attr in ("platform_material", "roof_material", "door_material",
                     "window_glass_material", "wall_material", "pillar_material",
                     "trim_material", "railing_material", "cornice_material",
                     "foundation_material"):
            base_val = getattr(base, attr)
            d_val = getattr(d, attr)
            # 默认值清单
            defaults = {
                "platform_material": "stone_bricks",
                "roof_material": "stone_bricks",
                "door_material": "dark_oak_door",
                "window_glass_material": "glass",
                "wall_material": "stone_bricks",
                "pillar_material": "chiseled_stone_bricks",
                "trim_material": "polished_andesite",
                "railing_material": "oak_fence",
                "cornice_material": "polished_andesite",
                "foundation_material": "smooth_stone",
            }
            if base_val == defaults.get(attr, "") and d_val != defaults.get(attr, ""):
                setattr(base, attr, d_val)

        # 拼接描述
        if d.description:
            base.description += f"\n--- 另一角度 ---\n{d.description}"
        if d.decorations_description and not base.decorations_description:
            base.decorations_description = d.decorations_description

    return base


def _apply_wikipedia_data(
    dsl: BuildingDSL,
    wiki_data: Optional[dict],
) -> BuildingDSL:
    """用 Wikipedia 真实数据校准 BuildingDSL 尺寸。"""
    if not wiki_data:
        return dsl

    result = dsl.model_copy(deep=True)

    # 用真实高度替换
    if "height_meters" in wiki_data:
        real_blocks = meters_to_blocks(wiki_data["height_meters"])
        if real_blocks > dsl.height:
            result.height = real_blocks

    # 用真实楼层数替换
    if "floor_count_int" in wiki_data:
        result.floor_count = wiki_data["floor_count_int"]

    # 根据建筑尺寸自动推荐精细度
    max_dim = max(result.height, result.width, result.length)
    if max_dim <= 20:
        result.detail_scale = 3
    elif max_dim <= 50:
        result.detail_scale = 2
    else:
        result.detail_scale = 1

    # 风格只做参考补充
    if "architectural_style" in wiki_data:
        style = wiki_data["architectural_style"].lower()
        mapped = _map_style(style)
        if mapped and mapped != "modern" and result.style == "modern":
            result.style = mapped

    # 附加 Wikipedia 信息到描述
    wiki_info = []
    if "height_meters" in wiki_data:
        wiki_info.append(f"Wikipedia 真实高度: {wiki_data['height_meters']}m → {result.height} 格")
    if "floor_count_int" in wiki_data:
        wiki_info.append(f"层数: {wiki_data['floor_count_int']}")
    if "architectural_style" in wiki_data:
        wiki_info.append(f"风格: {wiki_data['architectural_style']}")
    if "material" in wiki_data:
        wiki_info.append(f"材料: {wiki_data['material']}")
    if wiki_data.get("summary"):
        result.description += f"\n\nWikipedia 描述:\n{wiki_data['summary'][:500]}"
    if wiki_info:
        result.description += "\n\n" + "\n".join(wiki_info)

    return result


def _map_style(style: str) -> str:
    """将 Wikipedia 风格映射到内部风格名称。"""
    if "gothic" in style:
        return "gothic"
    if "classical" in style or "neoclassical" in style:
        return "classical"
    if "renaissance" in style:
        return "classical"
    if "baroque" in style or "rococo" in style:
        return "baroque"
    if "modern" in style or "contemporary" in style or "brutalist" in style:
        return "modern"
    if "chinese" in style or "japanese" in style or "asian" in style:
        return "chinese_traditional"
    if "medieval" in style or "romanesque" in style:
        return "medieval"
    if "victorian" in style:
        return "classical"
    return "modern"


def analyze(
    image_paths: list[str],
    version: MinecraftVersion = MinecraftVersion.JAVA_1_20,
    api_key: Optional[str] = None,
) -> BuildingDSL:
    """V2 Agent 3：多视角建筑融合。

    流程：
      1. 每张照片走 ai_analyzer.analyze() → BuildingDSL
      2. 合并多视角结果（_merge_dsls）
      3. 如果识别到建筑名称，查 Wikipedia 校准尺寸
      4. 返回融合后的 BuildingDSL

    Args:
        image_paths: 一张或多张照片路径
        version: Minecraft 版本
        api_key: 智谱 API Key

    Returns:
        BuildingDSL
    """
    # 1. 分别分析每张照片
    dsls = []
    for path in image_paths:
        dsl = ai_analyze(path, version, api_key=api_key)
        dsls.append(dsl)

    # 2. 合并多视角结果
    merged = _merge_dsls(dsls)

    # 3. 如果识别到具体建筑名称，查 Wikipedia
    wiki_data = None
    if merged.building_name and len(merged.building_name) >= 4:
        wiki_data = lookup_building(merged.building_name)

    # 4. 用 Wikipedia 数据校准
    result = _apply_wikipedia_data(merged, wiki_data)

    # 5. 最终自动修正边界问题（Wikipedia 可能改出超尺寸值）
    from src.analysis.dsl_validator import fix as _fix
    _fix(result)

    return result
