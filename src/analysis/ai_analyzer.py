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

import httpx

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
- materials: 主要材料列表，每个含 name/color/fraction。根据**图片中实际可见的颜色**选择最匹配的方块！这是最重要的字段，必须仔细观察颜色。

  关键：按照建筑实际颜色选择材料！白色建筑不要选石头，红色建筑不要选木板！
  重要：材料名必须是精确的 Minecraft 方块名（如下所列），不要用"wood"用"oak_planks"，不要用"stone"用"stone_bricks"！
  
  按颜色分类的材料（优先选择最接近视觉颜色的）：
  
  🔴 **红色/橙色系**（中式红墙、红砖、红瓦屋顶）:
    red_concrete(深红), red_terracotta(红陶), red_wool(红), bricks(红砖), red_sandstone(红砂岩), nether_bricks(暗红)
    
  🟡 **黄色/金色系**（金色屋顶、黄色外墙）:
    gold_block(金), yellow_terracotta(黄陶), yellow_concrete(黄), smooth_quartz(白黄), birch_planks(浅黄)
    
  ⚪ **白色/浅色系**（白色墙壁、大理石）:
    quartz_block(白), white_concrete(纯白), white_terracotta(白陶), white_wool(白), smooth_stone(灰白)
    
  ⬜ **灰色系**（水泥、石材）:
    stone(灰), stone_bricks(石砖), cobblestone(圆石), andesite(安山岩), polished_andesite(磨制安山岩)
    deepslate(深板岩-深灰), deepslate_bricks(深石板砖), cobbled_deepslate(圆石板岩)
    gray_concrete(灰混凝土), light_gray_concrete(浅灰混凝土), terracotta(陶瓦)
    
  🟫 **棕色系**（木材、木结构）:
    oak_planks(橡木), spruce_planks(云杉木), dark_oak_planks(深色橡木), jungle_planks(丛林木)

  🟦 **蓝色系**（玻璃、水面）:
    blue_concrete(蓝), blue_wool(蓝羊毛), glass(透玻), blue_stained_glass(蓝玻), prismarine(海晶石)
    
  🟩 **绿色系**（铜绿、植物）:
    green_terracotta(绿陶), green_concrete(绿), copper_block(铜-橙), exposed_copper(锈铜-绿)
    
  ⬛ **深色系**（黑色屋顶、地基）:
    black_concrete(黑), black_wool(黑), blackstone(黑石), obsidian(黑曜石)
    
  特殊材料：iron_block(铁-银灰), gold_block(金-黄), copper_block(铜-橙), snow_block(雪-白), packed_ice(冰-蓝白)

- bays: 开间数（正面柱间数量），如天安门 9 间、普通房子 3~5 间。仅大门/牌坊/庙宇等开间式建筑填写，不确定留 null
- roof_tiers: 屋顶层数/重檐数，如天安门重檐=2，普通建筑=1。不确定留 null
- platform_height: 台基/基座高度（米），如天安门的高大城台。不确定留 null
- features: 建筑特征列表，每个包含 feature_type（door, window, roof, balcony, pillar, column, arch, chimney, tower, dome, skylight）、position（front, side, back, top, corner，roof 用 flat/gable/hip/pyramid/dome）、count（数量，必须是纯数字！不要用"multiple"、"many"、"several"等文字）
- description: 一段文字描述建筑的外观特征，包括颜色、纹理、独特细节等

只输出 JSON，不要输出其他内容。"""


def _encode_image(image_path: str, max_dim: int = 256) -> tuple[str, str]:
    """将图片压缩后转为 base64 字符串，返回 (base64_data, mime_type)。
    
    智谱 API 限制 inputs + max_new_tokens <= 16384，大图必须压缩。
    """
    from PIL import Image
    import io

    ext = Path(image_path).suffix.lower()
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp", ".bmp": "image/bmp"}
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
        img.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode("utf-8"), mime


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
        raise ValueError("未设置智谱 API Key。请通过 --api-key 参数或 ZHIPU_API_KEY 环境变量传入。")

    base64_image, mime_type = _encode_image(image_path)
    image_data_url = f"data:{mime_type};base64,{base64_image}"

    import httpx
    payload = {
        "model": ZHIPU_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                    {"type": "text", "text": "分析这张建筑图片，返回 JSON 格式的建筑描述。"},
                ],
            },
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    r = httpx.post(f"{ZHIPU_BASE_URL}chat/completions", json=payload, headers=headers, timeout=120)
    if r.status_code != 200:
        raise ValueError(f"API 返回错误 (HTTP {r.status_code}): {r.text[:500]}")
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    if not content:
        raise ValueError("AI 返回内容为空")

    # --- 解析 JSON ---
    import json

    content = content.strip()
    # 去掉 Markdown 代码块
    if content.startswith("```"):
        lines = content.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines).strip()

    # 尝试直接解析；失败时尝试找最外层 {}
    try:
        raw = json.loads(content)
    except json.JSONDecodeError:
        # 找第一个 { 和最后一个 }
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            raw = json.loads(content[start:end+1])
        else:
            raise ValueError(f"AI 返回内容不是有效 JSON:\n{content[:500]}")

    # --- 转换为 BuildingDescription ---
    raw_materials = raw.get("materials", [])
    for m in raw_materials:
        if isinstance(m, dict) and "fraction" in m:
            f = m["fraction"]
            if isinstance(f, str):
                try:
                    f = float(f.replace("%", "").strip())
                except (ValueError, AttributeError):
                    f = 0.5
                m["fraction"] = f
            if isinstance(f, (int, float)) and f > 1:
                m["fraction"] = f / 100.0
    materials = [
        BlockMaterial(**m) if isinstance(m, dict) else BlockMaterial(name=m)
        for m in raw_materials
    ]
    features = []
    for f in raw.get("features", []):
        if isinstance(f, dict):
            if "count" in f and not isinstance(f["count"], (int, float)):
                f["count"] = 1
            features.append(BuildingFeature(**f))
        else:
            features.append(BuildingFeature(feature_type=f))

    return BuildingDescription(
        minecraft_version=version,
        building_type=raw.get("building_type", "house"),
        building_name=raw.get("building_name", ""),
        height=max(1, raw.get("height", 10)),
        width=max(1, raw.get("width", 8)),
        length=max(1, raw.get("length", 10)),
        floors=max(1, raw.get("floors", 1)),
        detail_scale=max(1, min(8, raw.get("detail_scale", 1))),
        style=raw.get("style", "modern"),
        materials=materials,
        features=features,
        bays=raw.get("bays"),
        roof_tiers=raw.get("roof_tiers"),
        platform_height=raw.get("platform_height"),
        description=raw.get("description", ""),
    )


def _get_env_key() -> str | None:
    """从环境变量读取智谱 API Key。"""
    import os
    return os.environ.get("ZHIPU_API_KEY", None)
