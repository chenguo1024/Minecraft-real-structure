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


class FaceWindow(BaseModel):
    """立面上的窗户描述"""

    x: float = Field(description="窗户在立面上的水平位置（0~1 比例）")
    width: float = Field(default=0.15, description="窗户宽度（0~1 比例）")
    height: int = Field(default=2, description="窗户高度（方块数）")
    y_offset: int = Field(default=1, description="离地高度（方块数）")


class FaceOpening(BaseModel):
    """立面上的开口（门洞/拱门）"""

    x: float = Field(description="开口水平位置（0~1 比例）")
    width: float = Field(default=0.2, description="开口宽度（0~1 比例）")
    height: int = Field(default=3, description="开口高度（方块数）")
    style: str = Field(default="rectangle", description="开口样式: rectangle/arch")


class Facade(BaseModel):
    """建筑单个立面的描述"""

    face: str = Field(description="立面方向: front/back/left/right")
    material: str = Field(default="", description="该面墙的材质，空则用全局材料")
    columns: list[float] = Field(
        default_factory=list,
        description="立柱水平位置列表（0~1 比例），如 [0.1, 0.5, 0.9]",
    )
    windows: list[FaceWindow] = Field(
        default_factory=list,
        description="窗户列表",
    )
    openings: list[FaceOpening] = Field(
        default_factory=list,
        description="开口列表（门洞/拱门）",
    )
    railings: bool = Field(default=False, description="是否有栏杆/护栏")
    cornice: bool = Field(default=False, description="是否有檐口线脚")


class BuildingDescription(BaseModel):
    """
    AI 分析后的建筑结构化描述。
    这是整个项目的数据契约 —— 所有模块都基于此结构通信。
    """

    minecraft_version: MinecraftVersion = Field(
        default=MinecraftVersion.JAVA_1_20,
        description="目标 Minecraft 版本，决定方块 ID 映射和导出格式",
    )
    building_type: str = Field(description="建筑类型，如 house, tower, church, bridge, gate")
    building_name: str = Field(default="", description="建筑名称，如 中科大西大门, 故宫太和殿")
    height: int = Field(ge=1, le=1024, description="建筑高度（方块数）。使用 /place template 命令可放置任意大小。")
    width: int = Field(ge=1, le=1024, description="建筑宽度（方块数）。")
    length: int = Field(ge=1, le=1024, description="建筑深度（方块数）。")
    shape: str = Field(default="rectangle", description="建筑平面形状，如 rectangle, L, cross, T, U")
    style: str = Field(default="modern", description="建筑风格，如 modern, gothic, classical, asian, chinese")
    materials: list[BlockMaterial] = Field(
        default_factory=list,
        description="主要建筑材料列表",
    )
    features: list[BuildingFeature] = Field(
        default_factory=list,
        description="建筑特征列表",
    )
    floors: int = Field(default=1, ge=1, le=100, description="楼层数")
    detail_scale: int = Field(default=1, ge=1, le=8, description="精细度缩放倍率。1=每米1格(标准), 2=每米2格(精细), 3=每米3格(极精细)")
    bays: int | None = Field(default=None, description="开间数（正面柱间数量），如天安门 9 间，常见 1/3/5/7/9")
    roof_tiers: int | None = Field(default=None, description="屋顶层数/重檐数，如天安门重檐=2，普通建筑=1")
    platform_height: int | None = Field(default=None, description="台基/基座高度（方块数），如天安门的城台")
    facades: list[Facade] = Field(
        default_factory=list,
        description="各立面详细描述。空列表时生成器使用对称逻辑代替。",
    )
    description: str = Field(default="", description="AI 生成的额外文字描述")
