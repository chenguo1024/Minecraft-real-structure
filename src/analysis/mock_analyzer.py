"""Mock 分析器 —— 覆盖多种建筑风格/形状/屋顶组合用于测试。"""

from src.models.building import (
    BlockMaterial,
    BuildingDescription,
    BuildingFeature,
    MinecraftVersion,
)

# ── 预设模板 ──

_MODERN_VILLA = BuildingDescription(
    minecraft_version=MinecraftVersion.JAVA_1_20,
    building_type="villa",
    height=10, width=8, length=12,
    shape="rectangle",
    style="modern",
    floors=2,
    materials=[
        BlockMaterial(name="stone_bricks", color="light_gray", fraction=0.6),
        BlockMaterial(name="oak_planks", color="brown", fraction=0.25),
        BlockMaterial(name="glass", color="light_blue", fraction=0.15),
    ],
    features=[
        BuildingFeature(feature_type="door", position="front_center", count=1),
        BuildingFeature(feature_type="window", position="front", count=4),
        BuildingFeature(feature_type="roof", position="flat", count=1),
    ],
    description="Two-story modern villa with flat roof.",
)

_L_SHAPE_VILLA = BuildingDescription(
    minecraft_version=MinecraftVersion.JAVA_1_20,
    building_type="villa",
    height=10, width=10, length=12,
    shape="L",
    style="modern",
    floors=2,
    materials=[
        BlockMaterial(name="stone_bricks", color="light_gray", fraction=0.5),
        BlockMaterial(name="glass", color="light_blue", fraction=0.2),
    ],
    features=[
        BuildingFeature(feature_type="door", position="front_center", count=1),
        BuildingFeature(feature_type="window", position="front", count=4),
        BuildingFeature(feature_type="roof", position="flat", count=1),
    ],
    description="L-shaped modern villa.",
)

_GOTHIC_CHURCH = BuildingDescription(
    minecraft_version=MinecraftVersion.JAVA_1_20,
    building_type="church",
    height=18, width=10, length=20,
    shape="cross",
    style="gothic",
    floors=1,
    materials=[
        BlockMaterial(name="stone_bricks", color="light_gray", fraction=0.7),
        BlockMaterial(name="polished_andesite", color="gray", fraction=0.2),
        BlockMaterial(name="glass", color="white", fraction=0.1),
    ],
    features=[
        BuildingFeature(feature_type="door", position="front_center", count=1),
        BuildingFeature(feature_type="window", position="front", count=6),
        BuildingFeature(feature_type="roof", position="gable", count=1),
    ],
    description="Gothic church with cross-shaped floor plan and gabled roof.",
)

_ASIAN_PAGODA = BuildingDescription(
    minecraft_version=MinecraftVersion.JAVA_1_20,
    building_type="pagoda",
    height=14, width=8, length=8,
    shape="rectangle",
    style="asian",
    floors=5,
    materials=[
        BlockMaterial(name="bricks", color="red", fraction=0.5),
        BlockMaterial(name="oak_planks", color="brown", fraction=0.3),
    ],
    features=[
        BuildingFeature(feature_type="door", position="front_center", count=1),
        BuildingFeature(feature_type="window", position="front", count=4),
        BuildingFeature(feature_type="roof", position="pyramid", count=1),
    ],
    description="Asian pagoda with pyramid roof.",
)

_CLASSICAL_MANSION = BuildingDescription(
    minecraft_version=MinecraftVersion.JAVA_1_20,
    building_type="mansion",
    height=12, width=12, length=14,
    shape="rectangle",
    style="classical",
    floors=3,
    materials=[
        BlockMaterial(name="stone_bricks", color="light_gray", fraction=0.6),
        BlockMaterial(name="polished_andesite", color="gray", fraction=0.3),
        BlockMaterial(name="oak_planks", color="brown", fraction=0.1),
    ],
    features=[
        BuildingFeature(feature_type="door", position="front_center", count=1),
        BuildingFeature(feature_type="window", position="front", count=6),
        BuildingFeature(feature_type="roof", position="hip", count=1),
    ],
    description="Classical mansion with hip roof.",
)


TEMPLATES = {
    "L_villa": _L_SHAPE_VILLA,
    "villa": _MODERN_VILLA,
    "church": _GOTHIC_CHURCH,
    "pagoda": _ASIAN_PAGODA,
    "mansion": _CLASSICAL_MANSION,
}


def analyze(image_path: str, version: MinecraftVersion) -> BuildingDescription:
    """根据路径关键词选择不同 Mock 模板（长关键词优先匹配）。"""
    path_lower = image_path.lower()
    # 按关键词长度降序排列，避免 "L_villa" 被 "villa" 拦截
    sorted_keys = sorted(TEMPLATES.keys(), key=len, reverse=True)
    for keyword in sorted_keys:
        if keyword.lower() in path_lower:
            template = TEMPLATES[keyword]
            data = template.model_dump()
            data["minecraft_version"] = version
            return BuildingDescription(**data)
    data = _MODERN_VILLA.model_dump()
    data["minecraft_version"] = version
    return BuildingDescription(**data)
