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


class BlockMaterial(BaseModel):
    """建筑材料的方块映射"""

    name: str = Field(description="材料名称（如 stone, oak_planks）")
    color: Optional[str] = Field(None, description="颜色描述（如 深灰色）")
    fraction: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="该材料占比（0~1），总和不为 1 也没关系",
    )


class BuildingFeature(BaseModel):
    """建筑特征描述"""

    feature_type: str = Field(description="特征类型，如 door, window, roof, balcony, pillar")
    position: Optional[str] = Field(None, description="位置描述，如 front, center, top")
    count: int = Field(default=1, ge=0, description="数量")


class BuildingDescription(BaseModel):
    """
    AI 分析后的建筑结构化描述。
    这是整个项目的数据契约 —— 所有模块都基于此结构通信。
    """

    minecraft_version: MinecraftVersion = Field(
        default=MinecraftVersion.JAVA_1_20,
        description="目标 Minecraft 版本，决定方块 ID 映射和导出格式",
    )
    building_type: str = Field(description="建筑类型，如 house, tower, church, bridge")
    height: int = Field(ge=1, le=256, description="建筑高度（方块数）。为 Minecraft 结构方块兼容性推荐 ≤48，大于 48 时生成器会给出警告。")
    width: int = Field(ge=1, le=256, description="建筑宽度（方块数）。推荐 ≤48。")
    length: int = Field(ge=1, le=256, description="建筑深度（方块数）。推荐 ≤48。")
    shape: str = Field(default="rectangle", description="建筑平面形状，如 rectangle, L, cross, T, U")
    style: str = Field(default="modern", description="建筑风格，如 modern, gothic, classical, asian")
    materials: list[BlockMaterial] = Field(
        default_factory=list,
        description="主要建筑材料列表",
    )
    features: list[BuildingFeature] = Field(
        default_factory=list,
        description="建筑特征列表",
    )
    description: str = Field(default="", description="AI 生成的额外文字描述")
