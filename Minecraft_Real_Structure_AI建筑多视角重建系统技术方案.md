# Minecraft Real Structure

# AI 建筑多视角重建系统技术方案

> 版本：v1.2.0（V2 架构落地）
> 状态：Agent 1 + Agent 3 已实现，Agent 2 待引入图像搜索 API

## 项目定位

Minecraft Real Structure 是一个将现实建筑照片转换为 Minecraft 三维结构的开源项目。

目标流程：

```
建筑照片 → Agent 1 建筑识别 → Agent 2 网络搜索多视角资料 → Agent 3 多视角融合
        → Building DSL → Minecraft 方块生成 → .nbt 导出 → /place template 放置
```

---

## 核心架构

```
用户图片
  │
  ▼
Agent 1 建筑识别（src/analysis/identifier.py）   ✅ 已实现
  │  输出 {name, location, style, keywords}
  ▼
Agent 2 网络搜索多视角资料                         ⏳ 待实现（需图像搜索 API）
  │  收集 front/side/back/aerial/floor plan/3D model
  ▼
Agent 3 多视角融合（src/analysis/enhanced_analyzer.py）   ✅ 已实现
  │  多图 BuildingDSL 合并 + Wikipedia 校准
  ▼
Building DSL（src/models/building.py）            ✅ 已实现
  │  component 级几何数据契约
  ▼
Python 几何生成器（src/generator/geometry.py）    ✅ 已实现
  │  box/cylinder/sphere/cone/arch/curve/prism
  ▼
方块生成器（src/generator/block_builder.py）     ✅ 已实现
  │  按 component 渲染 + 屋顶/墙体/窗户/入口/曲线子系统
  ▼
NBT 导出（src/exporter/nbt_exporter.py）          ✅ 已实现
  │  手写 NBT 二进制 + GZip
  ▼
.nbt 文件 → /place template 放置
```

---

## Agent 1：建筑视觉识别 ✅

**实现**：`src/analysis/identifier.py`，调用智谱 GLM-4.6V-Flash。

**任务**：
- 识别建筑名称
- 国家和城市
- 建筑风格
- 搜索关键词（供 Agent 2 用）

**输出**：
```json
{
  "name": "天安门",
  "location": "Beijing, China",
  "style": "chinese_traditional",
  "keywords": ["天安门", "Tiananmen", "Beijing gate tower"]
}
```

**CLI 调用**：`py -3 -m src.main identify -i photo.jpg`

---

## Agent 2：资料搜索 ⏳

**状态**：未实现。开工前需确认图像搜索 API 选型（Google Images/Bing Images 要付费，Wikipedia Commons 免费但只覆盖著名建筑）。

**目标搜索词**：
- 建筑名称 + front view
- 建筑名称 + side view
- 建筑名称 + aerial
- 建筑名称 + floor plan
- 建筑名称 + 3D model

**收集**：正面/侧面/背面照片、航拍图、平面图、建筑资料

---

## Agent 3：多视角融合 ✅

**实现**：`src/analysis/enhanced_analyzer.py`

**策略**：
- 尺寸取最大（不同角度看到的不同维度）
- components 按名称合并去重
- curves 按 type+center 去重
- windows.items 按 side+floor+x 去重（后覆盖前）
- walls 按 type 去重
- materials 按 name 去重
- roof 取 layer_count 更大者
- entrance 取更复杂者（has_stairs/columns/roof_cover 加权和）
- building_name/location/keywords 取首个非空
- 识别到建筑名（≥4 字符）时查 Wikipedia 校准真实尺寸

---

# 建筑几何系统 ✅

**实现**：`src/generator/geometry.py`（纯函数式）

支持几何类型：
- `box` — 长方体（实心/空心外壳）
- `cylinder` — 垂直圆柱（沿 Y 轴）
- `sphere` — 球体/半球（穹顶用 half）
- `cone` — 圆锥（哥特尖塔）
- `prism` — 棱柱（楔形组件/山花，taper_axis=x/y/z）
- `arch` — 拱形（arch_type=semicircle/pointed/ellipse + curvature 0~1）
- `curve` — 自由曲线（飞檐/曲墙，direction=up/outward/inward）

**签名**：`(setter, 坐标, 尺寸, material, hollow, w/h/l 边界) → None`
- setter 签名 `(x, y, z, material_name) -> None`，与 BlockBuilder._set 兼容
- 内置边界保护，越界坐标自动忽略
- 支持 rotation_deg（0/90/180/270）绕 Y 轴

---

# Building DSL ✅

**实现**：`src/models/building.py`（取代旧 BuildingDescription）

```json
{
  "building_name": "天安门",
  "building_type": "gate",
  "style": "chinese_traditional",
  "location": "Beijing, China",
  "keywords": ["天安门", "Tiananmen"],

  "width": 60, "length": 32, "height": 20,
  "floor_count": 2, "floor_height": 5, "wall_thickness": 2,
  "detail_scale": 2,
  "shape": "rectangle",

  "components": [
    {
      "name": "main_body",
      "shape": "box|cylinder|sphere|cone|prism|arch|curve|custom",
      "width": 60, "length": 32, "height": 12,
      "radius": 0,
      "position": "center|front|back|left|right|front_left_corner|front_right_corner|back_left_corner|back_right_corner|top",
      "offset_x": 0, "offset_y": 4, "offset_z": 0,
      "material": "red_concrete",
      "rotation_deg": 0
    }
  ],

  "roof": {
    "type": "flat|gable|hip|pyramid|dome|mansard|barrel|spire|chinese_roof",
    "height": 8, "layer_count": 2, "overhang": 3,
    "material": "red_terracotta",
    "has_flying_eaves": true, "eaves_curvature": 0.6,
    "spire_height": 0, "spire_angle": 0
  },

  "walls": [
    {
      "type": "plain_wall|pillar|pilaster|buttress|arcade|rustication|timber_frame",
      "thickness": 2, "material": "red_concrete",
      "pillars": {"count": 12, "spacing": 5, "width": 1, "protrusion": 0, "material": "chiseled_stone_bricks"}
    }
  ],

  "windows": {
    "arrangement": "grid|symmetry|vertical_repeat|single",
    "items": [
      {
        "shape": "square|arch|pointed_arch|circle|bay_window|glass_wall",
        "floor": 2, "side": "front",
        "x": 0.5, "width": 0.2, "height": 3, "y_offset": 1,
        "count": 1, "spacing": 3,
        "frame_material": "dark_oak_planks", "glass_material": "glass"
      }
    ]
  },

  "entrance": {
    "type": "simple|arch|portal|porch|grand_stair|column_entrance",
    "position": "center", "side": "front",
    "width": 6, "height": 5,
    "has_stairs": false, "stair_count": 0,
    "has_columns": false, "column_count": 0,
    "has_roof_cover": false,
    "door_material": "dark_oak_door", "frame_material": "red_terracotta",
    "curvature": 1.0
  },

  "curves": [
    {
      "type": "arch|flying_eaves|baroque_wall|dome|sphere|cylinder|free_curve",
      "radius": 0, "height": 0,
      "center_x": 0, "center_y": 0, "center_z": 0,
      "width": 0, "depth": 0, "curve_radius": 0,
      "arch_type": "semicircle|pointed|ellipse",
      "direction": "up|outward|inward",
      "curvature": 0.6,
      "material": "red_terracotta"
    }
  ],

  "materials": [
    {"name": "red_concrete", "color": "red", "percentage": 50, "location": "wall"}
  ],

  "platform_material": "stone_bricks",
  "roof_material": "red_terracotta",
  "door_material": "dark_oak_door",
  "window_glass_material": "glass",
  "wall_material": "red_concrete",
  "pillar_material": "chiseled_stone_bricks",
  "trim_material": "polished_andesite",
  "railing_material": "oak_fence",
  "cornice_material": "polished_andesite",
  "foundation_material": "smooth_stone",

  "decorations_description": "雕刻/栏杆/横梁/装饰线/阳台/雕像",
  "description": "建筑逆向工程报告全文"
}
```

---

# 建筑尺寸分析 ✅

BuildingDSL 顶层字段：
- `width` / `length` / `height` — 总尺寸（方块数，1~1024）
- `floor_count` — 楼层数
- `floor_height` — 每层高度
- `wall_thickness` — 墙厚
- `detail_scale` — 精细度缩放（小建筑=3，中=2，大=1）

AI 估算规则（system prompt 内置）：
- 1 方块 ≈ 1 米
- 一扇门 ≈ 2 格高
- 一层楼 ≈ 3-4 格高
- 参照物反推（行人 1.8 格、轿车 4 格长）

---

# 屋顶系统 ✅

**实现**：`block_builder.py:_render_roof` + 9 个子方法

支持类型：
- `flat` — 平顶
- `gable` — 人字顶
- `hip` — 四坡顶
- `pyramid` — 攒尖顶
- `dome` — 穹顶（用 generate_sphere half）
- `mansard` — 曼萨德式（双折，下部陡坡上部缓坡）
- `barrel` — 筒形顶
- `spire` — 哥特尖塔（用 generate_cone）
- `chinese_roof` — 中式屋顶（四坡 + 飞檐翘角 + 正脊 + 重檐）

参数：
- `height` — 屋顶高度
- `slope_angle` — 坡度角
- `layer_count` — 屋顶层数/重檐数
- `overhang` — 屋檐外挑距离

中式特殊：`has_flying_eaves` + `eaves_curvature`（0~1，飞檐翘起程度）
哥特特殊：`spire_height` + `spire_angle`

---

# 曲线结构 ✅

**实现**：`geometry.py:generate_arch/curve` + `block_builder.py:_render_curve`

## 圆形
- `CurveSpec.type = cylinder`，参数 `radius` / `height` / `center_x/y/z`

## 球面（穹顶）
- `CurveSpec.type = dome|sphere`，`radius` + `center`

## 拱形
- `CurveSpec.type = arch`，参数 `width` / `height` / `curve_radius`
- `arch_type`: semicircle（半圆拱）/ pointed（尖拱）/ ellipse（扁拱）

## 自由曲线（飞檐/曲墙）
- `CurveSpec.type = flying_eaves|baroque_wall|free_curve`
- `direction`: up / outward / inward
- `curvature`: 0~1（small/medium/large 量化为 0.3/0.6/1.0）

---

# 墙体系统 ✅

**实现**：`block_builder.py:_render_wall` + 子方法

支持类型：
- `plain_wall` — 纯墙
- `pillar` — 柱列（均匀分布柱子）
- `pilaster` — 壁柱（扁平附墙柱）
- `buttress` — 扶壁（凸出墙面的支撑柱）
- `arcade` — 券柱式（柱 + 柱间拱）
- `rustication` — 粗石砌
- `timber_frame` — 木框架

参数：`thickness` + `PillarSpec`（count/spacing/width/protrusion/material）

---

# 窗户系统 ✅

**实现**：`block_builder.py:_render_windows` + `_render_window_item`

支持窗形：
- `square` — 方窗
- `arch` — 拱形窗
- `pointed_arch` — 尖拱窗（哥特）
- `circle` — 圆窗/玫瑰窗
- `bay_window` — 凸窗
- `glass_wall` — 玻璃幕墙

参数：`floor` / `side` / `x`(0~1) / `width`(0~1) / `height` / `y_offset` / `count` + `spacing`（重复排列）+ `frame_material` + `glass_material`

排列方式：`grid` / `symmetry` / `vertical_repeat` / `single`

---

# 入口系统 ✅

**实现**：`block_builder.py:_render_entrance`

支持类型：
- `simple` — 简单门洞
- `arch` — 拱门
- `portal` — 大门廊
- `porch` — 门廊
- `grand_stair` — 大台阶入口
- `column_entrance` — 列柱入口

参数：`position`(center/left/right) + `side` + `width`/`height` + `has_stairs`/`stair_count` + `has_columns`/`column_count` + `has_roof_cover` + `door_material`/`frame_material` + `curvature`(拱顶曲率)

---

# 材料系统 ✅

**方块库**：`src/generator/block_map.py`，1.20 palette 含 200+ 方块：
- 16 色 concrete / terracotta / glazed_terracotta
- copper 全家桶（copper/exposed/weathered/oxidized）
- prismarine 全家桶 / quartz 全家桶
- 各种木材（oak/spruce/birch/jungle/acacia/dark_oak/crimson/warped）
- 16 色彩色玻璃 / 羊毛
- 砖/黑石/深板岩/海晶石/砂岩
- 栏杆围墙楼梯（iron_bars/oak_fence/stone_brick_wall 等）
- 多版本兼容（Java 1.12~1.20 + Bedrock）+ 自动 fallback

**部位级材质**：AI 为不同部位分别指定方块（墙/屋顶/门/窗/柱/栏杆/檐口/台基/地基），按风格自动选材范式：
- modern → white_concrete + gray_concrete + blue_stained_glass
- chinese_traditional → red_concrete + red_terracotta + chiseled_stone_bricks
- classical → quartz_block + quartz_pillar + smooth_stone
- gothic → stone_bricks + black_concrete + blue_stained_glass（花窗）
- 等等

---

# Minecraft 生成器 ✅

**实现**：`src/generator/block_builder.py`

```
BuildingDSL → BlockBuilder.build() → BlockStructure
  ├─ _render_component (按 shape 分发到 geometry.py)
  ├─ _render_roof (9 种屋顶)
  ├─ _render_wall (柱列/扶壁/券柱式)
  ├─ _render_windows (6 种窗形 + 重复排列)
  ├─ _render_entrance (6 种入口 + 台阶/门廊柱)
  ├─ _render_curve (圆塔/穹顶/拱/飞檐)
  └─ _build_platform (台基)
```

输出 `BlockStructure`（palette/blocks/size_x/y/z），NBT exporter 接口不变。

---

# AI 分析器 ✅

**实现**：`src/analysis/ai_analyzer.py`

**模型**：智谱 GLM-4.6V-Flash（免费，128K 上下文，32K 输出）

**system prompt**：12 部分测绘思维框架 → BuildingDSL schema
1. 总体测绘（类型/风格/比例/地点/关键词）
2. 体块拆解（主体/侧翼/塔楼/屋顶/入口/阳台 → components）
3. 平面形状
4. 精确尺寸（楼层/墙厚）
5. 曲线曲面（圆/球/拱/自由曲线）
6. 屋顶详细建模
7. 墙体结构
8. 窗户精确分析
9. 入口系统
10. 装饰细节
11. 材料分析（含 location 部位标签）
12. 最终三维建模数据 → BuildingDSL JSON

**容错**：
- `_coerce_material/int/float` 归一化 AI 脏输入（dict/字符串数字/None）
- `_clamp` 把 curvature/x/width 夹到合法范围
- `max(1, ...)` 保护所有 ge=1 字段
- 429 限流指数退避重试 5 次（2/4/6/8/10s）
- fallback 链：4.6V → 4.1V-Thinking-Flash（16K 输出）→ 4V-Flash（1K 兜底）
- `_try_repair_json` 修复被 max_tokens 截断的 JSON（智能补全未闭合括号）

---

# 模型路线 ✅

## MVP（已实现）
**GLM-4.6V-Flash**（免费）：
- 图片理解 + 建筑识别 + 完整 BuildingDSL 输出
- 128K 上下文 / 32K 输出

## 高级（可选）
**GLM-4.1V-Thinking-Flash**（免费，带思考模式）：
- 复杂建筑结构推理
- 比例修正
- 已作为 4.6V 限流时的 fallback

**GLM-5V-Turbo**（付费，旗舰）：
- 200K 上下文 / 128K 输出
- 多模态 Coding 基座，最强

---

# 开发路线

## V1 ✅
- 单图分析
- 基础建筑分类
- 基础几何生成
- 屋顶、门窗

## V2 ✅（本次 v1.2.0 落地）
- Agent 1 + Agent 3 系统
- BuildingDSL component 级几何
- 几何生成器（box/cylinder/sphere/cone/arch/curve/prism）
- 9 种屋顶 + 7 种墙体 + 6 种窗形 + 6 种入口
- 部位级材质 + 200+ 方块库
- GLM-4.6V-Flash + 限流重试 + JSON 截断修复
- 222 个测试全过

## V3 ⏳
- Agent 2 网络搜索多视角图（需图像搜索 API）
- NeRF / Gaussian Splatting 3D Reconstruction
- Bedrock `.mcstructure` 导出

---

# 最终目标

```
Real Building
  ↓
AI Architectural Understanding (Agent 1+2+3)
  ↓
3D Procedural Blueprint (BuildingDSL)
  ↓
Minecraft World Reconstruction
```

---

# 测试覆盖 ✅

```
py -3 -m pytest tests/ -q
# 222 passed
```

| 测试文件 | 数量 | 覆盖 |
|---|---|---|
| test_models.py | 44 | BuildingDSL 全字段 Pydantic 校验 |
| test_geometry.py | 33 | 7 种几何纯函数 + 边界 + hollow |
| test_block_builder.py | 37 | component 渲染 + 9 屋顶 + 墙/窗/入口/曲线 + 材质 |
| test_ai_analyzer.py | 49 | 容错归一化 + 子解析器 + JSON 截断修复 |
| test_mock_analyzer.py | 13 | 5 模板选择 + 版本适配 |
| test_integration.py | 9 | 完整管线 Mock→DSL→BlockBuilder→NBT |
| test_block_map.py | 29 | 方块 ID 映射 + fallback |
| test_nbt_exporter.py | 8 | NBT 二进制 + GZip + 版本 |
