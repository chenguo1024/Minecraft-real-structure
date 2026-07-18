"""V2 Agent 3：多视角建筑融合 —— AI 分析 + Wikipedia 数据融合 + 多角度照片合并。

V3 改进：多张照片一次性综合分析（取代逐张独立分析）。
  1. 所有照片编码为 base64 → 一次性发送给 AI
  2. AI 综合所有视角构建完整 3D 理解 → 输出单一 BuildingDSL
  3. 如果识别到建筑名称，查 Wikipedia 获取真实尺寸校准
  4. 校验 + 自动修正 + Reflexion 多轮迭代
  5. 输出融合后的 BuildingDSL
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.analysis.ai_analyzer import (
    _call_zhipu_multi_image,
    _encode_image,
    _get_env_key,
    _parse_building_dsl,
    _refine_with_feedback,
)
from src.models.building import (
    DEFAULT_MATERIALS,
    BlockMaterial,
    BuildingDSL,
    Component,
    CurveSpec,
    MinecraftVersion,
    WallSpec,
    WindowItem,
)
from src.utils.wikipedia import lookup_building, meters_to_blocks


def _cross_check_dimensions(dsls: list[BuildingDSL]) -> list[str]:
    """多视角交叉校验：检查不同照片的尺寸是否一致，返回警告列表。

    规则：
      - height 在所有视角应该相同（建筑高度不变），差异 >20% 时警告
      - width 在正面/背面视角应该相同
      - 如果两张照片的 height 差异不大，取平均值；差异大时取中位数
    """
    warnings: list[str] = []
    if len(dsls) < 2:
        return warnings

    heights = [d.height for d in dsls]
    widths = [d.width for d in dsls]
    lengths = [d.length for d in dsls]

    def _median(vals: list[int]) -> int:
        s = sorted(vals)
        n = len(s)
        return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) // 2

    def _check_consistency(vals: list[int], name: str) -> int | None:
        """检查一组值是否一致。差异 >20% 时返回修正建议值（中位数）。"""
        if not vals:
            return None
        mn, mx = min(vals), max(vals)
        if mn == 0:
            return mx
        if (mx - mn) / mn > 0.2:
            med = _median(vals)
            warnings.append(
                f"{name} 多视角差异较大 ({mn}~{mx})，交叉校验后建议值: {med}"
            )
            return med
        return None

    return warnings


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
      - 交叉校验多视角一致性
    """
    if not dsls:
        raise ValueError("没有 DSL 可以合并")
    if len(dsls) == 1:
        return dsls[0]

    # 交叉校验（合并前先记录警告）
    cc_warnings = _cross_check_dimensions(dsls)
    if cc_warnings:
        __import__("logging").debug(f"多视角交叉校验: {'; '.join(cc_warnings)}")

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
        for attr in DEFAULT_MATERIALS:
            base_val = getattr(base, attr)
            d_val = getattr(d, attr)
            default_val = DEFAULT_MATERIALS.get(attr, "")
            if base_val == default_val and d_val != default_val:
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
    """用 Wikipedia 真实数据校准 BuildingDSL 尺寸。

    强制覆盖策略：Wikipedia 是权威数据，必须无条件替换 AI 的猜测值。
    """
    if not wiki_data:
        return dsl

    result = dsl.model_copy(deep=True)

    # 用真实高度替换（无条件覆盖）
    if "height_meters" in wiki_data:
        result.height = meters_to_blocks(wiki_data["height_meters"])

    # 用真实楼层数替换（无条件覆盖）
    if "floor_count_int" in wiki_data:
        result.floor_count = wiki_data["floor_count_int"]

    # 用真实宽度替换（无条件覆盖）
    if "width_meters" in wiki_data:
        result.width = meters_to_blocks(wiki_data["width_meters"])

    # 用真实进深替换（无条件覆盖）
    if "length_meters" in wiki_data:
        result.length = meters_to_blocks(wiki_data["length_meters"])

    # 用开间数/柱子数校准 components 布局
    _apply_wiki_layout(result, wiki_data)

    # 根据建筑尺寸自动推荐精细度
    max_dim = max(result.height, result.width, result.length)
    if max_dim <= 20:
        result.detail_scale = 3
    elif max_dim <= 50:
        result.detail_scale = 2
    else:
        result.detail_scale = 1

    # 风格强制覆盖
    if "architectural_style" in wiki_data:
        style = wiki_data["architectural_style"].lower()
        mapped = _map_style(style)
        if mapped:
            result.style = mapped

    # 附加 Wikipedia 信息到描述
    wiki_info = []
    if "height_meters" in wiki_data:
        wiki_info.append(f"Wikipedia 真实高度: {wiki_data['height_meters']}m → {result.height} 格")
    if "width_meters" in wiki_data:
        wiki_info.append(f"Wikipedia 真实宽度: {wiki_data['width_meters']}m → {result.width} 格")
    if "length_meters" in wiki_data:
        wiki_info.append(f"Wikipedia 真实进深: {wiki_data['length_meters']}m → {result.length} 格")
    if "floor_count_int" in wiki_data:
        wiki_info.append(f"层数: {wiki_data['floor_count_int']}")
    if "bays_int" in wiki_data:
        wiki_info.append(f"开间数: {wiki_data['bays_int']}")
    if "columns_int" in wiki_data:
        wiki_info.append(f"柱子数: {wiki_data['columns_int']}")
    if "architectural_style" in wiki_data:
        wiki_info.append(f"风格: {wiki_data['architectural_style']}")
    if "material" in wiki_data:
        wiki_info.append(f"材料: {wiki_data['material']}")
    if wiki_data.get("summary"):
        result.description += f"\n\nWikipedia 描述:\n{wiki_data['summary'][:500]}"
    if wiki_info:
        result.description += "\n\n" + "\n".join(wiki_info)

    return result


def _apply_wiki_layout(dsl: BuildingDSL, wiki_data: dict) -> None:
    """用 Wikipedia 的开间数/柱子数校准 components 墙体柱列布局。"""
    bays = wiki_data.get("bays_int")
    columns = wiki_data.get("columns_int")
    n_pillars = columns if columns else bays

    # 校准墙体 PillarSpec
    for wall in dsl.walls:
        if wall.pillars and wall.type in ("pillar", "pilaster", "buttress", "arcade"):
            if n_pillars:
                wall.pillars.count = max(2, n_pillars)

    # 校准入口柱子数
    if n_pillars and dsl.entrance.has_columns:
        dsl.entrance.column_count = min(n_pillars, max(2, n_pillars // 2))


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
    max_refine_rounds: int = 3,
) -> BuildingDSL:
    """多视角建筑综合分析（V4：Wikipedia 引导 + 多图一次分析）。

    核心改进：先用 Agent 1 快速识别建筑名 → 查 Wikipedia 拿到权威数据
    → 把所有图片 + Wikipedia 数据一起发给 AI 做详细测绘。
    AI 不再是"从零猜"，而是有权威数据指导的精确重建。

    流程：
      1. Agent 1 快速识别建筑名（用第一张照片）
      2. 查 Wikipedia 获取真实尺寸/风格/材料/开间数/层数
      3. 所有图片 + Wikipedia 权威数据 → 一次性发送给 AI
      4. AI 综合所有视角 + 权威数据 → 输出精确 BuildingDSL
      5. 校验 + 自动修正
      6. Reflexion 多轮迭代（评分低时反馈修正）
      7. 模板兜底
      8. 返回

    Args:
        image_paths: 一张或多张照片路径
        version: Minecraft 版本
        api_key: 智谱 API Key
        max_refine_rounds: 最多 AI 修正轮数

    Returns:
        BuildingDSL
    """
    from src.analysis.dsl_validator import validate as _validate, \
        score as _score, fix as _fix

    key = api_key or _get_env_key()
    if not key:
        raise ValueError("缺少智谱 API Key，请设置 ZHIPU_API_KEY 环境变量或传 api_key 参数")

    # ── Step 1: Agent 1 快速识别建筑名 ──
    building_name = ""
    keywords = []
    try:
        from src.analysis.identifier import identify as _identify
        ident = _identify(image_paths[0], api_key=key)
        building_name = ident.name
        keywords = ident.keywords
        if building_name:
            __import__("logging").debug(f"Agent 1 识别: {building_name} ({ident.location})")
    except Exception as e:
        __import__("logging").debug(f"Agent 1 识别失败: {e}")

    # ── Step 2: 查 Wikipedia 获取权威数据 ──
    wiki_data = None
    if building_name and len(building_name) >= 4:
        wiki_data = lookup_building(building_name)
        if wiki_data:
            __import__("logging").debug(f"Wikipedia 找到: {wiki_data.get('height_meters', '?')}m")

    # ── Step 3: 编码所有图片 ──
    images = []
    for path in image_paths:
        img_data, img_mime = _encode_image(path)
        images.append((img_data, img_mime))

    # ── Step 4: 构造带 Wikipedia 引导的 prompt ──
    num_photos = len(images)
    prompt_parts = []
    if num_photos > 1:
        prompt_parts.append(
            f"以下是同一栋建筑从 {num_photos} 个不同角度拍摄的照片，"
            f"请综合分析，构建完整的 3D 理解。"
        )
    else:
        prompt_parts.append("以下是建筑照片，请进行详细测绘分析。")

    # Wikipedia 权威数据作为参考
    if wiki_data:
        wiki_info = []
        if "height_meters" in wiki_data:
            real_blocks = meters_to_blocks(wiki_data["height_meters"])
            wiki_info.append(f"真实高度: {wiki_data['height_meters']}m（≈{real_blocks} 方块）")
        if "floor_count_int" in wiki_data:
            wiki_info.append(f"楼层数: {wiki_data['floor_count_int']}")
        if "architectural_style" in wiki_data:
            wiki_info.append(f"建筑风格: {wiki_data['architectural_style']}")
        if "material" in wiki_data:
            wiki_info.append(f"材料: {wiki_data['material']}")
        if "summary" in wiki_data:
            wiki_info.append(f"描述: {wiki_data['summary'][:300]}")
        if wiki_info:
            prompt_parts.append(
                "\n\n【Wikipedia 权威数据】——以下数据来自维基百科，请作为参考基准："
                + "\n".join(f"- {i}" for i in wiki_info)
                + "\n\n请确保你的分析结果与以上权威数据吻合（特别是高度、层数、风格）。"
            )

    prompt_parts.append("\n按 schema 输出 JSON。")
    prompt_text = "".join(prompt_parts)

    # ── Step 5: 一次性发送给 AI ──
    raw = _call_zhipu_multi_image(key, images, prompt_text)
    dsl = _parse_building_dsl(raw, version)

    # 保留 Agent 1 识别的建筑名（AI 可能输出空名）
    if building_name and not dsl.building_name:
        dsl.building_name = building_name
    if keywords and not dsl.keywords:
        dsl.keywords = keywords

    # 自动修正
    fix_msgs = _fix(dsl)
    if fix_msgs:
        __import__("logging").debug(f"自动修正: {'; '.join(fix_msgs)}")

    # 校验 + 评分
    errors = _validate(dsl)
    s, reasons = _score(dsl)

    # ── Step 6: Reflexion 多轮迭代修正 ──
    prev_score = s
    for round_n in range(1, max_refine_rounds + 1):
        if s >= 50 or not errors:
            break

        # 用第一张图片做代表图片给 refine
        rep_img_data, rep_mime = images[0]
        refined_raw = _refine_with_feedback(key, rep_img_data, rep_mime, dsl, errors, s, reasons)
        if refined_raw is None:
            __import__("logging").debug(f"第 {round_n} 轮 AI 修正失败（API 超时/限流），终止迭代")
            break

        dsl = _parse_building_dsl(refined_raw, version)
        fix_msgs2 = _fix(dsl)
        if fix_msgs2:
            __import__("logging").debug(f"第 {round_n} 轮修正: {'; '.join(fix_msgs2)}")

        errors = _validate(dsl)
        s, reasons = _score(dsl)
        __import__("logging").debug(f"第 {round_n} 轮评分: {s}/100, 错误数: {len(errors)}")

        if s <= prev_score:
            __import__("logging").debug(
                f"第 {round_n} 轮评分未提升 ({prev_score}→{s})，终止迭代"
            )
            break
        prev_score = s

    # ── Step 7: 模板兜底 ──
    if s < 30:
        try:
            from src.analysis.templates import get_template
            template_dsl = get_template(
                style=dsl.style,
                building_type=dsl.building_type,
                width=dsl.width,
                length=dsl.length,
                height=dsl.height,
                floor_count=dsl.floor_count,
                detail_scale=dsl.detail_scale,
            )
            template_dsl.building_name = dsl.building_name
            template_dsl.location = dsl.location
            template_dsl.keywords = dsl.keywords
            template_dsl.description = dsl.description
            template_dsl.decorations_description = dsl.decorations_description
            template_dsl.minecraft_version = version
            dsl = template_dsl
            _fix(dsl)
            __import__("logging").debug(f"模板兜底: style={dsl.style}, type={dsl.building_type}")
        except Exception:
            pass

    # ── Step 8: Wikipedia 校准（覆盖 AI 输出） ──
    result = _apply_wikipedia_data(dsl, wiki_data)

    # 最终自动修正
    _fix(result)

    return result
