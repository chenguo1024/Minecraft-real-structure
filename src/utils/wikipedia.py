"""Wikipedia 建筑查询 —— 根据建筑名称搜索 Wikipedia 获取真实尺寸、风格等数据。

设计理由：
  1. AI 识别出建筑名称后，用 Wikipedia 查真实数据（尺寸、风格、材料、楼层）。
  2. 用真实数据替换 AI 的估算，大幅提高准确度。
  3. 使用 Wikipedia REST API，无需额外依赖（httpx 已安装）。
"""

from __future__ import annotations

import re
import html

import httpx

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_HEADERS = {
    "User-Agent": "MinecraftRealStructure/1.0 (building generator; academic project)"
}

# 中文和英文的维基百科信息框字段映射
INFOBOX_FIELDS = {
    "height": ["height", "高度", "建筑高度"],
    "floor_count": ["floor_count", "floor count", "楼层", "层数", "floors"],
    "architectural_style": ["architectural_style", "architectural style", "style", "风格", "建筑风格"],
    "material": ["material", "材料", "建筑材料", "结构体系"],
    "architect": ["architect", "建筑师", "设计师"],
    "start_date": ["start_date", "start date", "开工", "奠基"],
    "completion_date": ["completion_date", "completion date", "竣工", "建成"],
    "width": ["width", "宽度"],
    "length": ["length", "长度", "进深"],
    "area": ["area", "建筑面积", "占地面积"],
}


def _search_building(name: str, lang: str = "en") -> str | None:
    """在 Wikipedia 搜索建筑，返回第一个匹配的页面标题。"""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": name,
        "srlimit": 5,
        "format": "json",
    }
    try:
        r = httpx.get(
            f"https://{lang}.wikipedia.org/w/api.php",
            params=params,
            headers=WIKIPEDIA_HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        results = data.get("query", {}).get("search", [])
        if results:
            return results[0]["title"]
    except Exception:
        pass
    return None


def _get_page_summary(title: str, lang: str = "en") -> str | None:
    """获取 Wikipedia 页面摘要。"""
    params = {
        "action": "query",
        "titles": title,
        "prop": "extracts",
        "exintro": True,
        "explaintext": True,
        "format": "json",
    }
    try:
        r = httpx.get(
            f"https://{lang}.wikipedia.org/w/api.php",
            params=params,
            headers=WIKIPEDIA_HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        pages = data.get("query", {}).get("pages", {})
        for page_id, page in pages.items():
            if page_id != "-1" and "extract" in page:
                return page["extract"]
    except Exception:
        pass
    return None


def _get_page_html(title: str, lang: str = "en") -> str | None:
    """获取 Wikipedia 页面 HTML 用于提取信息框。"""
    params = {
        "action": "parse",
        "page": title,
        "prop": "text",
        "format": "json",
    }
    try:
        r = httpx.get(
            f"https://{lang}.wikipedia.org/w/api.php",
            params=params,
            headers=WIKIPEDIA_HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        return data.get("parse", {}).get("text", {}).get("*", None)
    except Exception:
        return None


def _extract_infobox_value(html_text: str, field_names: list[str]) -> str | None:
    """从 Wikipedia HTML 信息框中提取字段值。
    
    解析类似:
      <th scope="row" ...>Height</th>
      <td ...>330 m (1,080 ft)</td>
    """
    for field in field_names:
        # 匹配 th 中包含字段名的行
        patterns = [
            rf'<th[^>]*>\s*{re.escape(field)}\s*</th>\s*<td[^>]*>(.*?)</td>',
            rf'<td[^>]*class="infobox-data"[^>]*>\s*{re.escape(field)}\s*</td>\s*<td[^>]*>(.*?)</td>',
            rf'<th[^>]*>\s*<a[^>]*>\s*{re.escape(field)}\s*</a>\s*</th>\s*<td[^>]*>(.*?)</td>',
        ]
        for pattern in patterns:
            m = re.search(pattern, html_text, re.IGNORECASE | re.DOTALL)
            if m:
                val = m.group(1)
                val = re.sub(r'<[^>]+>', '', val)  # 去掉 HTML 标签
                val = html.unescape(val).strip()
                if val:
                    return val
    return None


def _extract_height_meters(height_str: str) -> int | None:
    """从高度字符串（如 '330 m (1,080 ft)'）中提取米数。"""
    m = re.search(r'(\d+[\.\d]*)\s*m', height_str, re.IGNORECASE)
    if m:
        return int(float(m.group(1)))
    # 尝试中文 "米"
    m = re.search(r'(\d+[\.\d]*)\s*米', height_str)
    if m:
        return int(float(m.group(1)))
    return None


def _extract_floor_count(floor_str: str) -> int | None:
    """从楼层数字符串提取整数。"""
    m = re.search(r'(\d+)', floor_str)
    if m:
        return int(m.group(1))
    return None


def lookup_building(name: str) -> dict | None:
    """根据建筑名称查询 Wikipedia，返回结构化数据。

    Args:
        name: 建筑名称（支持中英文）。

    Returns:
        包含 height, floor_count, style, material 等字段的字典，查询不到返回 None。
    """
    # 先搜中文
    title = _search_building(name, "zh")
    lang = "zh" if title else "en"

    if not title:
        title = _search_building(name, "en")
        lang = "en"

    if not title:
        return None

    summary = _get_page_summary(title, lang)
    html_text = _get_page_html(title, lang)

    result = {"title": title, "lang": lang, "summary": summary}

    if html_text:
        for key, field_names in INFOBOX_FIELDS.items():
            val = _extract_infobox_value(html_text, field_names)
            if val:
                result[key] = val

    # 尝试转换高度
    if "height" in result:
        h = _extract_height_meters(result["height"])
        if h:
            result["height_meters"] = h

    # 转换楼层数
    if "floor_count" in result:
        f = _extract_floor_count(result["floor_count"])
        if f:
            result["floor_count_int"] = f

    return result


def meters_to_blocks(meters: int) -> int:
    """将米转换为 Minecraft 方块数（1 方块 ≈ 1 米），上限 256。"""
    blocks = max(1, meters)
    return min(blocks, 256)


def estimate_width_from_height(height_m: int, aspect_ratio: float = 0.3) -> int:
    """从高度推算大致宽度（常见建筑的高宽比）。"""
    w = int(height_m * aspect_ratio)
    return max(1, min(w, 256))
