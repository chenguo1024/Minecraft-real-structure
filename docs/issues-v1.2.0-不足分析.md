# v1.2.0 不足分析与修正方案

> 本文档总结 v1.2.0（V2 架构）已知不足，提出分阶段修正方案。
> 最后更新：2026-07-18

---

## 一、v1.2.0 回顾

v1.2.0 完成了 V2 架构落地：BuildingDSL + component 级几何 + Agent 1/3 + GLM-4.6V-Flash。
完成了 v3/v4 路线图上的 8 个 issue（逐面生成、曲线结构、多样化屋顶、内部结构、
Wikipedia 深度、3D 预览、进度反馈、手动调整），测试覆盖 216 个。

管线已完整可运行：

```
照片 → AI 视觉分析 → Wikipedia 校准 → BuildingDSL → 方块生成 → NBT 导出 → 游戏中放置
```

---

## 二、当前最大问题：缺乏反馈修正闭环

v1.2.0 的管线是**单次、单向、不可逆**的。AI 输出一旦有误，错误沿管线逐级放大，
用户只有在 3D 预览（或进游戏）后才发现效果不对。当前没有自动检测和修正机制。

---

## 三、问题清单与修正方案

### 第一层：工程侧硬校验（低成本，P0 优先）

#### Issue 1：BuildingDSL 自洽校验器

**现状**：AI 输出的 BuildingDSL 直接交给 BlockBuilder，不做一致性检查。
`_parse_building_dsl` 只做类型强制转换（`_coerce_*`），不校验语义。

**问题**：
- `components` 尺寸可能超出 `width/length/height` 总边界，导致方块溢出或被裁剪
- `roof.height` 可能使总高度超过 grid 上限
- `windows` 楼层可能超出 `floor_count`
- `entrance` 尺寸可能不合理（如门宽超过建筑宽度）
- `material` 可能不在 `BlockMap` 中，静默 fallback 为 stone_bricks

**方案**：在 `_parse_building_dsl` 之后、`BlockBuilder` 之前插入校验步骤。
校验失败时记录具体错误，用于触发二次分析。

---

#### Issue 2：AI 输出置信度评分 + 自动二次分析

**现状**：无法判断 AI 输出质量高低。

**问题**：
- components 数量为 0 时回退到单一 box，丢失所有细节
- materials 数量 <3 说明 AI 没有认真分析
- 所有字段都是默认值说明 AI 输出可能是空壳

**方案**：解析后给 BuildingDSL 打分。评分低于阈值时，自动用第一次结果 + 错误描述
重新调一次 API（最多 3 轮），直到评分合格。

---

#### Issue 3：Prompt 增强——输出前自检

**现状**：SYSTEM_PROMPT（783 行中的第 38-248 行）没有要求 LLM 在输出前自我检查。

**问题**：LLM 经常输出格式错误（尺寸超限、material 字段是对象而非字符串、
roof.height + 主体高度 > 总 height）。

**方案**：在 prompt 末尾追加自检指令，要求 LLM 输出前验证所有字段一致性。
这是极低成本的改动（只改 prompt），但能显著减少格式错误。

---

### 第二层：迭代修正闭环（中等成本，P1 优先）

#### Issue 4：AI 自我修正循环（Reflexion 模式）

**现状**：`_call_zhipu_api` 只调用一次，失败后 fallback 到更弱模型重试。

**问题**：即使是成功的调用，输出内容也可能有语义错误（尺寸不对、组件遗漏）。
当前没有任何机制让 AI 自己修正内容。

**方案**：多轮对话修正：

```
第一轮：AI 分析照片 → BuildingDSL
   ↓
校验器检查 → 发现不一致
   ↓
第二轮：把第一轮结果 + 错误描述回传给 AI
   ↓
再次校验 → 通过 or 继续迭代（最多 3 轮）
```

新增 `_refine_dsl()` 函数，构造多轮对话。

---

#### Issue 5：几何约束求解器

**现状**：完全依赖 AI 给出的数值，不做规则约束。

**问题**：AI 可能给出 `width=30` 但某个 component 的 `offset_x + width = 45`，
明显超出边界。

**方案**：在 AI 输出和生成器之间加规则约束层：

- `sum(component.heights) + roof.height <= total.height`
- `entrance.width < building.width`
- `window.floor <= floor_count`
- `component.offset + size <= building.dimension`

违反规则时自动修正数值，而非完全重跑 AI。

---

#### Issue 6：Web UI 交互式编辑

**现状**：结果页（`result.html`）的调参表单只覆盖 10 个顶层参数：
`width/height/length/floor_count/detail_scale/style/building_type/roof_type/roof_height/roof_layers`。

**问题**：用户看不到也改不了 `components` 列表、每个 `window` 的参数、`entrance` 配置、
`curves` 列表等。AI 分析错了这些细节，用户无法修正。

**方案**：升级为完整的 BuildingDSL 编辑器：
- 暴露每个 component 的 shape/尺寸/位置/材质为可编辑表单
- 屋顶、墙体、窗户、入口、曲线各自可编辑
- 修改后点「修正生成」只走 `BlockBuilder → NBT`，不经 AI
- 保存 BuildingDSL JSON，方便后续微调

---

### 第三层：多模态增强（较高成本，P2）

#### Issue 7：多视角一致性校验

**现状**：Agent 3（`enhanced_analyzer.py`）能处理多张图片，但融合逻辑简单
（取最大尺寸、去重 components）。

**问题**：
- 正面照片说 `width=30`，侧面照片说 `width=50`，取哪个？
- 两张照片分析的 `height` 不一致时没有置信度判断

**方案**：交叉校验：
- 正面说 width，侧面也应该看到 width，不一致时标记低置信度
- 两张的 height 应该一致，差异大时取中间值
- 不一致处触发 AI 二次确认

---

#### Issue 8：基于 3D 预览的视觉反馈循环

**现状**：Three.js 3D 预览只用于展示，不参与修正流程。

**方案**：增加「AI 修正」按钮：
- 用户对 3D 效果不满意，点按钮后填写问题描述（如"屋顶太高"、"缺少侧面细节"）
- 将 BuildingDSL JSON 转回文本，连同原图一起发给 AI 修正
- 返回修正后的 BuildingDSL，重新生成并预览

---

#### Issue 9：预训练建筑模板库

**现状**：AI 每次从零构造完整的 BuildingDSL。

**问题**：对于常见建筑类型，AI 需要输出大量重复的结构信息，出错概率高。

**方案**：建立参数化模板库：

| 模板 | 结构 |
|---|---|
| 中式宫殿 | 台基 + 主体 + 重檐 + 飞檐，参数化 width/height/layer_count |
| 哥特教堂 | 主体 + 侧廊 + 尖塔 + 扶壁，参数化 |
| 现代别墅 | 主体 box + 平屋顶 + 大面积玻璃，参数化 |

AI 只需识别建筑类型 + 调整参数，不需要从头构造 BuildingDSL。

---

## 四、方案对比与优先级

| Issue | 方案 | 成本 | 收益 | 优先级 |
|---|---|---|---|---|
| 1 | BuildingDSL 自洽校验器 | 低 | 拦截明显错误 | **P0** |
| 2 | 置信度评分 + 自动二次分析 | 低 | 自动发现问题 | **P0** |
| 3 | Prompt 增强自检 | 极低 | 减少格式错误 | **P0** |
| 5 | 几何约束求解器 | 中 | 修正数值不一致 | **P1** |
| 4 | AI 自我修正循环 | 中 | 迭代优化输出 | **P1** |
| 6 | Web UI 交互式编辑 | 中 | 用户直接控制 | **P1** |
| 7 | 多视角一致性校验 | 中高 | 提高精度 | P2 |
| 9 | 建筑模板库 | 高 | 大幅降低出错 | P2 |
| 8 | 视觉反馈循环 | 高 | 用户体验最佳 | P2 |

---

## 五、推荐实施路线

### Phase 1 — 立即可做（1 天）
- Issue 1：BuildingDSL 自洽校验器
- Issue 2：置信度评分 + 自动二次分析
- Issue 3：Prompt 增强自检

### Phase 2 — 形成自动修正闭环（3-5 天）
- Issue 4：AI 自我修正循环（Reflexion）
- Issue 5：几何约束求解器
- Issue 6：Web UI 交互式编辑

### Phase 3 — 增强精度（1-2 周）
- Issue 7：多视角一致性校验
- Issue 8：视觉反馈循环
- Issue 9：建筑模板库

---

## 六、其他遗留问题

### 6.1 未完成的路线图项
- **Agent 2**（网络搜索多视角图片）：未开工，需确定图像搜索 API
- **Bedrock `.mcstructure` 导出**：较大功能，未开工

### 6.2 工程基础设施
- 无 CI/CD 自动化
- 无 lint 配置
- 存档目录硬编码（`src/web/app.py:24`）