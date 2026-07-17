"""AI 分析器 —— 调用智谱 GLM-4V-Flash 分析建筑图片，输出结构化 JSON。

设计理由：
  1. 使用 OpenAI SDK + 自定义 base_url 对接智谱 API。
     这样接口风格统一，以后切换其他兼容 OpenAI 的 API（如阿里、硅基流动）只需改两行配置。
  2. 图片以 base64 编码传入，不依赖外部图床，用户上传的本地文件直接处理。
  3. System Prompt 明确要求输出 JSON 格式，并给出字段说明，
     让模型理解我们需要的结构化数据。同时要求只输出 JSON，避免解析 Markdown 代码块。
  4. 用 Pydantic 模型校验 AI 输出，不符合 schema 时抛出明确的验证错误。
"""

from __future__ import annotations

import base64
from pathlib import Path

from openai import OpenAI

from src.models.building import (
    BlockMaterial,
    BuildingDescription,
    BuildingFeature,
    MinecraftVersion,
)

# 智谱 GLM-4V-Flash 的 API 配置
ZHIPU_BASE_URL = "https://open.bigmodel.cn/api/paas/v4/"
ZHIPU_MODEL = "glm-4v-flash"  # 永久免费

SYSTEM_PROMPT = """你是一个建筑分析专家。分析图片中建筑的**视觉外观**，返回 JSON 格式的数据。
核心原则：仔细观察图片中实际可见的内容，不要猜测或编造。

尺寸估算规则（非常重要）：
  Minecraft 中 1 方块 ≈ 1 米。用图片中的参照物推算尺寸：
  - 一扇门 ≈ 2 格高、1 格宽
  - 一层楼（地板到天花板）≈ 3-4 格高
  - 一扇普通窗户 ≈ 1-2 格高
  - 一个人 ≈ 1.8 格高
  - 一辆轿车 ≈ 4 格长、1.5 格高

  多角度估算：
  - 如果能看到完整的正面/侧面，沿墙数门/窗/柱子推断宽度/高度
  - 如果只有一张透视照片，根据已知参照物（行人、车辆、门窗）反推比例尺
  - 如果只能看到部分建筑，根据典型比例推测被遮挡的维度
  - **所有维度必须在 1~256 之间**
  - **精细度缩放 (detail_scale)**：为了用更多方块表现细节：
    * 小型建筑（≤15m）：detail_scale=3，每米 3 格
    * 中型建筑（15~40m）：detail_scale=2，每米 2 格
    * 大型建筑（>40m）：detail_scale=1，每米 1 格

字段说明：
- building_type: 建筑类型，"gate"(大门/牌坊), "house"(房屋), "tower"(塔), "church"(教堂), "bridge"(桥), "skyscraper"(摩天楼), "temple"(庙), "pagoda"(塔), "arch"(拱门), "pavilion"(亭/阁)
- building_name: **只有当你非常确定建筑名称时才填写**（如"天安门"、"中科大西大门"），不确定就留空字符串
- height: 总高度（米），整数 1-256
- width: 宽度（米），整数 1-256
- length: 深度（米），整数 1-256
- shape: 平面形状，如 "rectangle"(矩形), "L", "cross"(十字), "T", "U", "arch"(拱形), "gate"(门形)
- style: 风格，"chinese"(中式), "modern"(现代), "classical"(古典), "gothic"(哥特), "asian"(亚洲), "medieval"(中世纪), "brutalist"(粗野主义), "renaissance"(文艺复兴)
- floors: 楼层数
- detail_scale: 精细度缩放 1~3
- materials: 主要材料列表，每个含 name/color/fraction。根据**图片中实际可见的颜色和质感**选择最匹配的 Minecraft 方块：

  可用材料名（建议选择最匹配的）：
  石头类: stone, granite, diorite, andesite, cobblestone, mossy_cobblestone
  石砖类: stone_bricks, mossy_stone_bricks, cracked_stone_bricks, chiseled_stone_bricks
  磨制类: polished_granite, polished_diorite, polished_andesite
  深板岩(现代建筑/地下室): deepslate, cobbled_deepslate, polished_deepslate, deepslate_bricks
  木板类: oak_planks, spruce_planks, birch_planks, jungle_planks, acacia_planks, dark_oak_planks
  玻璃类: glass, glass_pane, white_stained_glass, gray_stained_glass
  陶瓦/混凝土: terracotta, white_terracotta, white_concrete, gray_concrete, red_concrete
  羊毛(帐篷/装饰): white_wool, light_gray_wool, gray_wool, red_wool, blue_wool
  砖类: bricks, nether_bricks
  海晶石(水下): prismarine, prismarine_bricks
  砂岩(沙漠): sandstone, cut_sandstone, red_sandstone
  金属/现代: iron_block, gold_block, copper_block, quartz_block, quartz_pillar
  其他: end_stone, netherrack, obsidian, bookshelf, glowstone, sea_lantern, snow_block, packed_ice

- features: 建筑特征列表，每个包含 feature_type（door, window, roof, balcony, pillar, column, arch, chimney, tower, dome, skylight）、position（front, side, back, top, corner，roof 用 flat/gable/hip/pyramid/dome）、count（数量）
- description: 一段文字描述建筑的外观特征，包括颜色、纹理、独特细节等

只输出 JSON，不要输出其他内容。"""


def _encode_image(image_path: str) -> str:
    """将图片文件转为 base64 字符串。"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze(
    image_path: str,
    version: MinecraftVersion = MinecraftVersion.JAVA_1_20,
    api_key: str | None = None,
) -> BuildingDescription:
    """调用 GLM-4V-Flash 分析建筑图片。

    Args:
        image_path: 图片文件路径。
        version: 目标 Minecraft 版本。
        api_key: 智谱 API Key。不传则从环境变量 ZHIPU_API_KEY 读取。

    Returns:
        结构化建筑描述。

    Raises:
        ValueError: API Key 未设置或 AI 返回格式无效。
    """
    key = api_key or _get_env_key()
    if not key:
        raise ValueError(
            "未设置智谱 API Key。请通过 --api-key 参数或 ZHIPU_API_KEY 环境变量传入。"
        )

    client = OpenAI(api_key=key, base_url=ZHIPU_BASE_URL)
    base64_image = _encode_image(image_path)
    image_data_url = f"data:image/jpeg;base64,{base64_image}"

    response = client.chat.completions.create(
        model=ZHIPU_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": image_data_url},
                    },
                    {
                        "type": "text",
                        "text": "分析这张建筑图片，返回 JSON 格式的建筑描述。",
                    },
                ],
            },
        ],
        temperature=0.1,  # 低温度，让输出更稳定、更可预测
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("AI 返回内容为空")

    # --- 解析 JSON ---
    import json

    # 有时模型会返回 Markdown 代码块 ```json ... ```
    content = content.strip()
    if content.startswith("```"):
        # 提取 ``` 和 ``` 之间的内容
        lines = content.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()

    raw = json.loads(content)

    # --- 转换为 BuildingDescription ---
    materials = [
        BlockMaterial(**m) if isinstance(m, dict) else BlockMaterial(name=m)
        for m in raw.get("materials", [])
    ]
    features = [
        BuildingFeature(**f) if isinstance(f, dict) else BuildingFeature(feature_type=f)
        for f in raw.get("features", [])
    ]

    return BuildingDescription(
        minecraft_version=version,
        building_type=raw.get("building_type", "house"),
        building_name=raw.get("building_name", ""),
        height=raw.get("height", 10),
        width=raw.get("width", 8),
        length=raw.get("length", 10),
        floors=raw.get("floors", 1),
        detail_scale=raw.get("detail_scale", 1),
        style=raw.get("style", "modern"),
        materials=materials,
        features=features,
        description=raw.get("description", ""),
    )


def _get_env_key() -> str | None:
    """从环境变量读取智谱 API Key。"""
    import os
    return os.environ.get("ZHIPU_API_KEY", None)
