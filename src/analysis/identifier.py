"""Agent 1：建筑视觉识别 —— 从图片识别建筑元信息。

按 V2 技术方案 Agent 1 职责：
  - 识别建筑名称
  - 国家和城市
  - 建筑风格
  - 搜索关键词（供 Agent 2 网络搜索用）

输出 BuildingIdentification（轻量结构，不含几何/尺寸）。
独立于 ai_analyzer.py 的完整 BuildingDSL 分析，先快速识别再决定后续流程。
"""
from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Optional

import httpx
from pydantic import BaseModel, Field

from src.analysis.ai_analyzer import (
    ZHIPU_BASE_URL,
    ZHIPU_MODEL,
    _encode_image,
    _get_env_key,
)


IDENTIFY_PROMPT = """你是一名建筑识别专家。快速识别图片中建筑的基本信息。

只输出 JSON，不要其他内容。schema：
{
  "name": "建筑名称（只有非常确定时才填，如\"天安门\"、\"埃菲尔铁塔\"；不确定留空字符串）",
  "location": "建筑所在国家/城市（如\"Paris, France\"、\"Beijing, China\"；不确定留空）",
  "style": "建筑风格：modern|gothic|classical|baroque|asian|chinese_traditional|medieval|brutalist|renaissance|industrial",
  "keywords": ["建筑名", "英文名", "地点关键词"]  // 供网络搜索用，3~5 个
}

注意：
- 不确定名称时留空，不要猜
- keywords 至少包含建筑英文名（如有）和地点，供后续搜索多视角图用
"""


class BuildingIdentification(BaseModel):
    """Agent 1 输出：建筑识别结果（V2 方案 Agent 1）。"""

    name: str = Field(default="", description="建筑名称")
    location: str = Field(default="", description="建筑地点（国家/城市）")
    style: str = Field(default="modern", description="建筑风格")
    keywords: list[str] = Field(default_factory=list, description="搜索关键词")


def identify(
    image_path: str,
    api_key: Optional[str] = None,
) -> BuildingIdentification:
    """Agent 1：快速识别建筑元信息。

    比 ai_analyzer.analyze() 轻量，只识别不测绘。
    用于：
      1. 决定是否值得查 Wikipedia（name 非空时）
      2. 提供 keywords 给 Agent 2 网络搜索多视角图
      3. 快速反馈用户"识别到 XXX"

    Args:
        image_path: 图片路径
        api_key: 智谱 API Key（None 从环境变量读）

    Returns:
        BuildingIdentification
    """
    key = api_key or _get_env_key()
    if not key:
        raise ValueError("缺少智谱 API Key")

    image_data, mime = _encode_image(image_path, max_dim=256)
    url = f"{ZHIPU_BASE_URL}chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": ZHIPU_MODEL,
        "messages": [
            {"role": "system", "content": IDENTIFY_PROMPT},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{image_data}"},
                    },
                    {"type": "text", "text": "识别这张建筑照片的基本信息。"},
                ]
            }
        ],
        "max_tokens": 512,  # 识别任务用小 token 数
        "temperature": 0.1,
    }

    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()

    content = result["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        lines = content.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        content = "\n".join(lines)

    raw = json.loads(content)
    return BuildingIdentification(
        name=raw.get("name", "") or "",
        location=raw.get("location", "") or "",
        style=raw.get("style", "modern") or "modern",
        keywords=raw.get("keywords", []) or [],
    )
