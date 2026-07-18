"""BuildingDSL 自洽校验器与置信度评分。

在 AI 解析完成之后、BlockBuilder 之前执行。
  - validate()  → 语义一致性检查，返回错误/警告列表
  - score()     → 置信度打分，返回 (score, reasons)
  - fix()       → 自动修正明显错误的字段（原地修改 DSL）
"""
from __future__ import annotations


from src.generator.block_map import BlockMap
from src.models.building import DEFAULT_MATERIALS, BuildingDSL


# ─── 校验 ───

def validate(dsl: BuildingDSL) -> list[str]:
    """对 BuildingDSL 进行语义一致性校验，返回错误/警告消息列表。

    空列表 = 全部通过。
    """
    errors: list[str] = []
    w = dsl.width
    l = dsl.length
    h = dsl.height

    # 1. 基本维度合理性
    if w > 256 or l > 256 or h > 256:
        errors.append(f"维度过大 ({w}x{h}x{l})，超过 256 上限")

    # 2. components 边界检查
    for c in dsl.components:
        if c.width == 0 and c.length == 0 and c.height == 0:
            errors.append(f"组件 \"{c.name}\" 尺寸全为零，应删除")
            continue

        comp_size_x = c.radius * 2 if c.shape in ("cylinder", "sphere", "cone") else c.width
        comp_size_z = c.radius * 2 if c.shape in ("cylinder", "sphere", "cone") else c.length

        if c.offset_x + comp_size_x > w:
            errors.append(
                f"组件 \"{c.name}\" X 方向溢出: "
                f"offset_x={c.offset_x} + size={comp_size_x} > width={w}"
            )
        if c.offset_z + comp_size_z > l:
            errors.append(
                f"组件 \"{c.name}\" Z 方向溢出: "
                f"offset_z={c.offset_z} + size={comp_size_z} > length={l}"
            )
        if c.offset_y + c.height > h:
            errors.append(
                f"组件 \"{c.name}\" Y 方向溢出: "
                f"offset_y={c.offset_y} + height={c.height} > height={h}"
            )

    # 3. 屋顶高度合理性
    if dsl.roof.height and dsl.roof.height > h // 2:
        errors.append(
            f"屋顶高度 ({dsl.roof.height}) 超过总高度的一半 ({h // 2})"
        )

    # 4. windows 楼层不超出 floor_count
    for win in dsl.windows.items:
        if win.floor > dsl.floor_count:
            errors.append(
                f"窗户 (side={win.side}, floor={win.floor}) 超出总楼层数 ({dsl.floor_count})"
            )

    # 5. entrance 尺寸合理性
    ent = dsl.entrance
    if ent.width and ent.width >= w:
        errors.append(
            f"入口宽度 ({ent.width}) ≥ 建筑宽度 ({w})"
        )
    if ent.height and ent.height >= h:
        errors.append(
            f"入口高度 ({ent.height}) ≥ 建筑高度 ({h})"
        )

    # 6. curves 中心点应在合理范围内
    for curve in dsl.curves:
        if curve.radius:
            if curve.center_x < 0 or curve.center_x >= w:
                errors.append(
                    f"曲线 \"{curve.type}\" center_x={curve.center_x} 超出 X 范围 [0, {w})"
                )
            if curve.center_z < 0 or curve.center_z >= l:
                errors.append(
                    f"曲线 \"{curve.type}\" center_z={curve.center_z} 超出 Z 范围 [0, {l})"
                )
            if curve.center_y < 0 or curve.center_y >= h:
                errors.append(
                    f"曲线 \"{curve.type}\" center_y={curve.center_y} 超出 Y 范围 [0, {h})"
                )

    # 7. 台阶数不应超过门高
    ent = dsl.entrance
    if ent.has_stairs and ent.stair_count > ent.height:
        errors.append(
            f"台阶数 ({ent.stair_count}) 超过入口高度 ({ent.height})"
        )

    # 8. has_columns=True 时 column_count 应 > 0
    if ent.has_columns and ent.column_count == 0:
        errors.append("has_columns=True 但 column_count=0")

    # 9. 窗户 x + width 不应超过 1.0
    for win in dsl.windows.items:
        if win.x + win.width > 1.0:
            errors.append(
                f"窗户 (side={win.side}) x={win.x} + width={win.width} > 1.0"
            )

    # 10. 墙体柱数不应超过建筑宽度
    for wall in dsl.walls:
        if wall.pillars.count and wall.pillars.spacing > 0:
            max_pillars = max(1, w // wall.pillars.spacing)
            if wall.pillars.count > max_pillars:
                errors.append(
                    f"墙体 {wall.type} 柱数 ({wall.pillars.count}) "
                    f"超过宽度可容纳的最大值 ({max_pillars})"
                )

    return errors


# ─── 置信度评分 ───

def score(dsl: BuildingDSL) -> tuple[int, list[str]]:
    """评估 BuildingDSL 质量，返回 (分数 0~100, 扣分原因列表)。

    评分规则（扣分制，从 100 开始扣）：
      - components 数量：0 个扣 40，1 个扣 20，≥2 个不扣
      - materials 数量：<3 扣 15
      - 全局部位材质全部为默认值扣 20
      - 没有 windows 扣 10
      - 没有 curves 且建筑类型复杂扣 10
      - components 中有零尺寸扣 10/个
      - 没有 description 扣 5
    """
    reasons: list[str] = []
    s = 100

    # components 数量
    n_comp = len(dsl.components)
    if n_comp == 0:
        s -= 40
        reasons.append("components 为空，回退到单一 box 将丢失所有细节")
    elif n_comp == 1:
        s -= 20
        reasons.append("components 仅 1 个，复杂建筑应有多个体块")

    # materials 数量
    n_mat = len(dsl.materials)
    if n_mat < 3:
        s -= 15
        reasons.append(f"materials 仅 {n_mat} 种，至少应有 3 种")

    # 全局部位材质是否全部为默认值
    custom_parts = 0
    for field, default in DEFAULT_MATERIALS.items():
        val = getattr(dsl, field, "")
        if val and val != default:
            custom_parts += 1
    if custom_parts == 0:
        s -= 20
        reasons.append("所有部位材质都是默认值，AI 可能没有认真选材")

    # windows
    if not dsl.windows.items:
        s -= 10
        reasons.append("没有窗户，多数建筑应有窗户")

    # curves
    complex_styles = ("gothic", "chinese_traditional", "baroque", "renaissance", "medieval", "classical")
    if (not dsl.curves
            and dsl.style in complex_styles
            and dsl.building_type not in ("house", "villa")):
        s -= 10
        reasons.append(f"风格为 {dsl.style} 但没有 curves，应有拱/穹顶/飞檐等曲线结构")

    # 零尺寸 components
    for c in dsl.components:
        if c.width == 0 and c.length == 0 and c.height == 0:
            s -= 10
            reasons.append(f"组件 \"{c.name}\" 尺寸全为零")

    # description
    if not dsl.description:
        s -= 5
        reasons.append("没有 description 文本")

    return max(0, s), reasons


# ─── 自动修正 ───

def fix(dsl: BuildingDSL) -> list[str]:
    """自动修正 BuildingDSL 中可修复的字段，返回修正说明列表。

    修正策略：
      - 零尺寸组件直接删除
      - 超出边界的组件尺寸/偏移裁剪到边界内
      - 屋顶高度不超过总高度一半
      - 窗户楼层不超过 floor_count
      - 入口尺寸不超过建筑尺寸
      - 无效材质回退为有效材质
    """
    messages: list[str] = []
    w = dsl.width
    l = dsl.length
    h = dsl.height

    # 删除零尺寸组件
    before = len(dsl.components)
    dsl.components = [
        c for c in dsl.components
        if not (c.width == 0 and c.length == 0 and c.height == 0)
    ]
    if len(dsl.components) < before:
        messages.append(f"删除了 {before - len(dsl.components)} 个零尺寸组件")

    # 裁剪组件边界
    for c in dsl.components:
        comp_size_x = c.radius * 2 if c.shape in ("cylinder", "sphere", "cone") else c.width
        comp_size_z = c.radius * 2 if c.shape in ("cylinder", "sphere", "cone") else c.length

        if comp_size_x and c.offset_x + comp_size_x > w:
            old = c.offset_x
            c.offset_x = max(0, w - comp_size_x)
            messages.append(f"组件 \"{c.name}\" offset_x 从 {old} 裁剪为 {c.offset_x}")

        if comp_size_z and c.offset_z + comp_size_z > l:
            old = c.offset_z
            c.offset_z = max(0, l - comp_size_z)
            messages.append(f"组件 \"{c.name}\" offset_z 从 {old} 裁剪为 {c.offset_z}")

        if c.height and c.offset_y + c.height > h:
            old = c.offset_y
            c.offset_y = max(0, h - c.height)
            messages.append(f"组件 \"{c.name}\" offset_y 从 {old} 裁剪为 {c.offset_y}")

        # 组件自身尺寸也裁剪
        if c.shape not in ("cylinder", "sphere", "cone"):
            if c.width > w:
                c.width = w
                messages.append(f"组件 \"{c.name}\" width 从 {c.width} 裁剪为 {w}")
            if c.length > l:
                c.length = l
                messages.append(f"组件 \"{c.name}\" length 从 {c.length} 裁剪为 {l}")
        if c.height > h:
            c.height = h
            messages.append(f"组件 \"{c.name}\" height 从 {c.height} 裁剪为 {h}")

    # 屋顶高度
    if dsl.roof.height and dsl.roof.height > h // 2:
        old = dsl.roof.height
        dsl.roof.height = h // 2
        messages.append(f"屋顶高度从 {old} 裁剪为 {dsl.roof.height}")

    # 窗户楼层
    for win in dsl.windows.items:
        if win.floor > dsl.floor_count:
            old = win.floor
            win.floor = dsl.floor_count
            messages.append(f"窗户 (side={win.side}) floor 从 {old} 修正为 {dsl.floor_count}")

    # 入口尺寸
    ent = dsl.entrance
    if ent.width >= w:
        old = ent.width
        ent.width = max(1, w // 4)
        messages.append(f"入口宽度从 {old} 修正为 {ent.width}")
    if ent.height >= h:
        old = ent.height
        ent.height = max(1, h // 3)
        messages.append(f"入口高度从 {old} 修正为 {ent.height}")

    # 曲线中心点裁剪到边界内
    for curve in dsl.curves:
        if curve.radius:
            if curve.center_x < 0:
                old = curve.center_x
                curve.center_x = 0
                messages.append(f"曲线 \"{curve.type}\" center_x 从 {old} 修正为 0")
            if curve.center_x >= w:
                old = curve.center_x
                curve.center_x = w - 1
                messages.append(f"曲线 \"{curve.type}\" center_x 从 {old} 修正为 {w-1}")
            if curve.center_z < 0:
                old = curve.center_z
                curve.center_z = 0
                messages.append(f"曲线 \"{curve.type}\" center_z 从 {old} 修正为 0")
            if curve.center_z >= l:
                old = curve.center_z
                curve.center_z = l - 1
                messages.append(f"曲线 \"{curve.type}\" center_z 从 {old} 修正为 {l-1}")
            if curve.center_y < 0:
                old = curve.center_y
                curve.center_y = 0
                messages.append(f"曲线 \"{curve.type}\" center_y 从 {old} 修正为 0")
            if curve.center_y >= h:
                old = curve.center_y
                curve.center_y = h - 1
                messages.append(f"曲线 \"{curve.type}\" center_y 从 {old} 修正为 {h-1}")

    # 台阶数约束：stair_count 不应超过 entrance.height
    ent = dsl.entrance
    if ent.has_stairs and ent.stair_count > ent.height:
        old = ent.stair_count
        ent.stair_count = max(1, ent.height // 2)
        messages.append(f"台阶数从 {old} 修正为 {ent.stair_count}（不应超过门高）")

    # 门廊柱约束：column_count 为 0 时如果 has_columns 为 True 则设为 2
    if ent.has_columns and ent.column_count == 0:
        ent.column_count = 2
        messages.append("has_columns=True 但 column_count=0，设为 2")

    # 墙体柱子约束：pillar count 不应超过建筑宽度
    for wall in dsl.walls:
        if wall.pillars.count and wall.pillars.spacing > 0:
            max_pillars = max(1, w // wall.pillars.spacing)
            if wall.pillars.count > max_pillars:
                old = wall.pillars.count
                wall.pillars.count = max_pillars
                messages.append(f"墙体 {wall.type} 柱数从 {old} 修正为 {max_pillars}（受宽度限制）")

    # 窗户 x 和 width 合理性：x + width <= 1.0
    for win in dsl.windows.items:
        if win.x + win.width > 1.0:
            old_w = win.width
            win.width = max(0.01, 1.0 - win.x)
            messages.append(f"窗户 (side={win.side}) width 从 {old_w:.2f} 修正为 {win.width:.2f}")

    # 材质回退：检查每个材质字段是否在 BlockMap 中存在
    _bm = BlockMap(dsl.minecraft_version)
    for field, fallback in DEFAULT_MATERIALS.items():
        val = getattr(dsl, field, "")
        if val and _bm.get_block_id(val) == _bm.get_block_id("stone_bricks") and val.lower().strip() not in ("stone_bricks", "minecraft:stone_bricks"):
            old = val
            setattr(dsl, field, fallback)
            messages.append(f"部位材质 {field} 从 \"{old}\"（不在方块表中）回退为 \"{fallback}\"")

    # 组件材质回退
    for c in dsl.components:
        if c.material and _bm.get_block_id(c.material) == _bm.get_block_id("stone_bricks") and c.material.lower().strip() not in ("stone_bricks", "minecraft:stone_bricks"):
            old = c.material
            c.material = dsl.wall_material
            messages.append(f"组件 \"{c.name}\" 材质从 \"{old}\" 回退为 \"{dsl.wall_material}\"")

    # 窗户材质回退
    for win in dsl.windows.items:
        if win.frame_material and _bm.get_block_id(win.frame_material) == _bm.get_block_id("stone_bricks") and win.frame_material.lower().strip() not in ("stone_bricks", "minecraft:stone_bricks"):
            win.frame_material = dsl.trim_material
        if win.glass_material and _bm.get_block_id(win.glass_material) == _bm.get_block_id("stone_bricks") and win.glass_material.lower().strip() not in ("stone_bricks", "minecraft:stone_bricks"):
            win.glass_material = dsl.window_glass_material

    # 入口材质回退
    if ent.door_material and _bm.get_block_id(ent.door_material) == _bm.get_block_id("stone_bricks") and ent.door_material.lower().strip() not in ("stone_bricks", "minecraft:stone_bricks"):
        ent.door_material = dsl.door_material
    if ent.frame_material and _bm.get_block_id(ent.frame_material) == _bm.get_block_id("stone_bricks") and ent.frame_material.lower().strip() not in ("stone_bricks", "minecraft:stone_bricks"):
        ent.frame_material = dsl.trim_material

    # 曲线材质回退
    for curve in dsl.curves:
        if curve.material and _bm.get_block_id(curve.material) == _bm.get_block_id("stone_bricks") and curve.material.lower().strip() not in ("stone_bricks", "minecraft:stone_bricks"):
            curve.material = dsl.wall_material

    return messages