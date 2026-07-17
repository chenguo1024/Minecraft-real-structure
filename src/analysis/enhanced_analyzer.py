"""增强分析器 —— AI 分析 + Wikipedia 数据融合 + 多角度照片分析。

设计理由：
  1. AI 分析单张照片估算尺寸不准确，用 Wikipedia 真实数据替换。
  2. 如果识别出建筑名称，自动查 Wikipedia 获取真实尺寸/风格/材料。
  3. 支持上传多张照片（不同角度），分析后合并结果。
  4. 如果有 Wikipedia 真实高度，用真实高度换算 Minecraft 方块数。
"""

from __future__ import annotations

from pathlib import Path

from src.analysis.ai_analyzer import analyze as ai_analyze
from src.models.building import BuildingDescription, BuildingFeature, MinecraftVersion
from src.utils.wikipedia import lookup_building, meters_to_blocks


def _merge_descriptions(descs: list[BuildingDescription]) -> BuildingDescription:
    """合并多张照片的分析结果（取最大尺寸、合并特征列表）。"""
    if not descs:
        raise ValueError("没有描述可以合并")
    if len(descs) == 1:
        return descs[0]

    base = descs[0].model_copy(deep=True)

    for d in descs[1:]:
        # 取最大尺寸
        base.height = max(base.height, d.height)
        base.width = max(base.width, d.width)
        base.length = max(base.length, d.length)
        base.floors = max(base.floors, d.floors)
        base.detail_scale = max(base.detail_scale, d.detail_scale)

        # 如果某张识别到建筑名称，保留
        if d.building_name and not base.building_name:
            base.building_name = d.building_name
        if d.building_type and d.building_type != base.building_type:
            base.building_type = d.building_type

        # 合并特征（去重）
        existing_types = {f.feature_type for f in base.features}
        for f in d.features:
            if f.feature_type not in existing_types:
                base.features.append(f)
                existing_types.add(f.feature_type)

        # 追加描述
        if d.description:
            base.description += f"\n--- 另一角度 ---\n{d.description}"

        # 合并 facades（按方向去重，后相同方向覆盖前）
        if d.facades:
            existing_faces = {f.face for f in base.facades}
            for f in d.facades:
                if f.face in existing_faces:
                    base.facades = [x for x in base.facades if x.face != f.face]
                base.facades.append(f)
                existing_faces.add(f.face)

    return base


def _apply_wikipedia_data(
    desc: BuildingDescription,
    wiki_data: dict | None,
) -> BuildingDescription:
    """用 Wikipedia 真实数据替换 AI 估算值。"""
    if not wiki_data:
        return desc

    result = desc.model_copy(deep=True)

    # 用真实高度替换
    if "height_meters" in wiki_data:
        real_blocks = meters_to_blocks(wiki_data["height_meters"])
        if real_blocks > desc.height:
            result.height = real_blocks

    # 用真实楼层数替换
    if "floor_count_int" in wiki_data:
        result.floors = wiki_data["floor_count_int"]

    # 根据建筑尺寸自动推荐精细度
    max_dim = max(result.height, result.width, result.length)
    if max_dim <= 20:
        result.detail_scale = 3  # 小型建筑极精细
    elif max_dim <= 50:
        result.detail_scale = 2  # 中型建筑精细
    else:
        result.detail_scale = 1  # 大型建筑标准

    # 风格和材料只做参考补充，不改 AI 视觉分析的结果
    if "architectural_style" in wiki_data:
        style = wiki_data["architectural_style"].lower()
        mapped = _map_style(style)
        if mapped and mapped != "modern":
            # 只有 Wikipedia 风格明确时才覆盖
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
    if "modern" in style or "contemporary" in style or "brutalist" in style:
        return "modern"
    if "chinese" in style or "japanese" in style or "asian" in style:
        return "asian"
    if "medieval" in style or "romanesque" in style:
        return "medieval"
    if "victorian" in style or "baroque" in style or "rococo" in style:
        return "classical"
    return "modern"


def _map_material(mat_text: str) -> list | None:
    """将 Wikipedia 材料文本映射为 Minecraft 材料列表。"""
    from src.models.building import BlockMaterial

    mapping = {
        "concrete": "concrete",
        "steel": "iron_block",
        "glass": "glass",
        "stone": "stone",
        "marble": "quartz_block",
        "granite": "granite",
        "limestone": "stone",
        "brick": "bricks",
        "wood": "oak_planks",
        "timber": "oak_planks",
        "sandstone": "sandstone",
        "copper": "copper_block",
        "iron": "iron_block",
        "gold": "gold_block",
    }

    materials = []
    for keyword, block_name in mapping.items():
        if keyword in mat_text:
            materials.append(BlockMaterial(name=block_name, fraction=0.5))
    return materials if materials else None


def analyze(
    image_paths: list[str],
    version: MinecraftVersion = MinecraftVersion.JAVA_1_20,
    api_key: str | None = None,
) -> BuildingDescription:
    """增强分析：多张照片 + AI + Wikipedia。

    Args:
        image_paths: 一张或多张照片路径。
        version: Minecraft 版本。
        api_key: 智谱 API Key。

    Returns:
        融合后的建筑描述。
    """
    # 1. 分别分析每张照片
    descs = []
    for path in image_paths:
        desc = ai_analyze(path, version, api_key)
        descs.append(desc)

    # 2. 合并多角度结果
    merged = _merge_descriptions(descs)

    # 3. 如果识别到具体的建筑名称，查 Wikipedia（只查完整名称，避免误匹配）
    wiki_data = None
    if merged.building_name and len(merged.building_name) >= 4:
        # 只对具体名称（≥4个字符）查 Wikipedia
        wiki_data = lookup_building(merged.building_name)

    # 4. 用 Wikipedia 数据增强
    result = _apply_wikipedia_data(merged, wiki_data)

    return result
