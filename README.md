# Minecraft Real Structure

AI 驱动的工具，将现实世界建筑照片转换成 Minecraft 三维结构（`.nbt` 文件）。使用智谱 GLM-4V-Flash 分析建筑图片，自动查 Wikipedia 校准尺寸，生成 Minecraft 可识别的结构文件。

## 工作流程

```
建筑照片 → AI 视觉分析 (BuildingDSL) → Wikipedia 校准 → 方块生成器 → NBT 导出 → /place template 放置
```

## 技术栈

| 层 | 选型 | 用途 |
|---|---|---|
| 数据模型 | Pydantic v2 | BuildingDSL：分析/生成/导出三层的共享数据契约 |
| AI 分析 | 智谱 GLM-4V-Flash (httpx) | 从图片提取 12 部分结构化描述 |
| 数据查证 | Wikipedia API | 获取真实尺寸/风格/材料 |
| 几何生成 | 纯函数 (setter 模式) | `geometry.py` 提供 box/cylinder/sphere/cone/arch/curve/prism |
| 方块生成 | BlockBuilder | 按 BuildingDSL components 逐个渲染 + 叠加 roof/walls/windows/entrance/curves |
| 方块映射 | BlockMap | 1.20 palette，200+ 方块（16 色 concrete/terracotta/glazed + copper + prismarine + quartz + 木材 + 彩色玻璃 + 砖/黑石） |
| NBT 导出 | 手写 NBT 二进制 (GZip) | 写入 Minecraft 结构文件，跳过空气方块 |
| Web | FastAPI + Uvicorn + Jinja2 | HTTP 上传界面，Three.js 3D 预览 |
| CLI | Click | 子命令 mock/analyze/identify |
| 测试 | pytest (216 个测试) | 全链路测试覆盖 |

## 项目结构

```
minecraft-real-structure/
├── pyproject.toml
├── src/
│   ├── main.py                  # Click CLI：mock / analyze / identify
│   ├── models/
│   │   ├── __init__.py          # 统一导出（BuildingDSL, DEFAULT_MATERIALS, ...）
│   │   └── building.py          # Pydantic 数据模型（BuildingDSL V2）
│   ├── analysis/
│   │   ├── ai_analyzer.py       # 完整 AI 分析：图片 → BuildingDSL（12 部分测绘思维框架）
│   │   ├── enhanced_analyzer.py # 多视角融合 + Wikipedia 校准
│   │   ├── identifier.py        # Agent 1：快速识别建筑元信息
│   │   ├── dsl_validator.py     # BuildingDSL 验证与评分
│   │   ├── mock_analyzer.py     # Mock 分析器（5 模板：villa/gate/church/tower/temple）
│   │   └── templates.py         # 建筑模板定义
│   ├── generator/
│   │   ├── block_builder.py     # BlockBuilder：DSL → BlockStructure
│   │   ├── block_map.py         # BlockMap：方块 ID 映射（多版本 + 颜色材料别名）
│   │   └── geometry.py          # 纯函数几何生成器（setter 模式）
│   ├── exporter/
│   │   └── nbt_exporter.py      # NBT 二进制导出（GZip 压缩）
│   ├── utils/
│   │   └── wikipedia.py         # Wikipedia 建筑信息查询
│   └── web/
│       ├── app.py               # FastAPI 应用（/analyze, /analyze-async, /regenerate, ...）
│       └── templates/           # Jinja2 模板 + Three.js 3D 预览
├── tests/
│   ├── test_block_builder.py
│   ├── test_block_map.py
│   ├── test_geometry.py         # 几何生成器 + rotate_y
│   ├── test_integration.py
│   ├── test_mock_analyzer.py
│   ├── test_models.py
│   └── test_nbt_exporter.py
├── data/
│   ├── uploads/                 # 用户上传的图片
│   └── structures/              # 生成的 .nbt 文件
└── .gitignore
```

## 快速开始

> Windows + Python 3.10+。统一用 `py -3` 调用解释器——本机 `python` 会指向 msys64 的解释器（没装 pytest）。

### 0. 安装

```powershell
git clone git@github.com:chenguo1024/Minecraft-real-structure.git
cd minecraft-real-structure
py -3 -m pip install -r requirements.txt
```

### A. Web 界面（最常用）

```powershell
# 只有用 AI 分析才需要 Key；Mock 模式不需要
$env:ZHIPU_API_KEY = "你的智谱API Key"

# 启动服务（前台进程，Ctrl+C 退出）
py -3 -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000
```

浏览器打开 <http://127.0.0.1:8000>：
1. 上传建筑照片（支持多图多角度）
2. SSE 实时推送进度（上传 → AI 分析 → 查 Wikipedia → 生成 → 导出），页面不再转圈无反馈
3. 结果页：Three.js InstancedMesh 3D 预览 + 组件/屋顶/曲线/墙体/材料展示 + 调参表单
4. 微调参数 → 点「重新生成」只走生成器，不再花钱调 AI（端点 `/regenerate`）
5. 下载 `.nbt`

### B. 命令行 AI 分析

```powershell
$env:ZHIPU_API_KEY = "你的智谱API Key"
py -3 -m src.main analyze -i photo.jpg -v java-1.20 -o data/structures/mybuilding.nbt
```

`-v` 默认 `java-1.20`，可选 `java-1.12 / 1.13 / 1.17 / 1.20`；`-o` 默认 `data/structures/<图片名>.nbt`。
`--json-out` 可额外输出 BuildingDSL JSON。

### C. Mock 分析（不调 AI，验证管线用）

无需 Key，用固定模板数据跑完整流程：

```powershell
py -3 -m src.main mock -i photo.jpg -v java-1.20
# 输出到 data/structures/<图片名>_mock.nbt
```

### D. 快速识别（Agent 1）

只识别建筑名称/地点/风格/关键词，不做完整分析：

```powershell
py -3 -m src.main identify -i photo.jpg
```

### 把 .nbt 放进游戏

| 大小 | 方式 |
|---|---|
| ≤48×48×48 | `/give @s structure_block`，模式 LOAD，输入文件名（不带 `.nbt`） |
| 任意大小 ≤128³ | 游内按 T：`/place template minecraft:文件名`（文件需在 `<存档>/generated/minecraft/structures/` 下） |

### 跑测试

```powershell
py -3 -m pytest tests/ -q
# 期望：216 passed
```

`pyproject.toml` 已配 `-p no:cacheprovider -q`。常见报错：

| 症状 | 原因 | 解决 |
|---|---|---|
| `python: No module named pytest` | 用了 msys64 的 `python` | 改用 `py -3` |
| `PermissionError [Errno 13]` 写文件被拒 | 当前会话非管理员，仓库目录 ACL = Users RX | 管理员身份启动 |
| `.pytest_cache` WinError 183 | cache 残留冲突 | `Remove-Item -LiteralPath .pytest_cache -Recurse -Force` |
| `pytest-of-<用户>` Temp 权限拒绝 | pytest 扫不到临时目录 | 加 `--basetemp=C:\Users\<你>\AppData\Local\Temp\opencode\pytest` |

## 架构设计

### BuildingDSL（V2 数据模型）

`BuildingDSL` 取代了旧的 `BuildingDescription`，是分析层和生成层之间的唯一数据契约：

- **元信息**：`building_name` / `type` / `style` / `location` / `keywords`
- **尺寸**：`width` / `height` / `length`
- **组件**（`Component[]`）：体块定义（name, shape=box|cylinder|sphere|cone|prism|arch|curve, 尺寸, 位置, offset, material, rotation）
- **屋顶**（`RoofSpec`）：type=flat|gable|hip|pyramid|dome|mansard|barrel|spire|chinese_roof + 飞檐/曲率
- **墙体**（`WallSpec`）：type=plain_wall|pillar|pilaster|buttress|arcade|rustication|timber_frame + PillarSpec
- **窗户**（`WindowSystem` / `WindowItem`）：shape=square|arch|pointed_arch|circle|bay_window|glass_wall + frame/glass 材质
- **入口**（`EntranceSpec`）：type=simple|arch|portal|porch|grand_stair|column_entrance + stairs/columns/roof_cover
- **曲线**（`CurveSpec[]`）：type=arch|flying_eaves|baroque_wall|dome|sphere|cylinder|free_curve + arch_type + curvature
- **材料**（`BlockMaterial[]`）：name/color/percentage/location
- **全局部位材质**：10 个预定义部位（platform/roof/door/window_glass/wall/pillar/trim/railing/cornice/foundation）

### 几何生成器（纯函数式）

`geometry.py` 提供纯函数 `generate_box/cylinder/sphere/cone/arch/curve/prism` + `rotate_y`：
- 签名：`(setter, 坐标, 尺寸, material, hollow, w/h/l 边界) → None`
- setter 签名 `(x,y,z,material_name) → None`，与 `BlockBuilder._set` 兼容
- 支持边界保护 + hollow/solid + arch_type（semicircle/pointed/ellipse）+ curvature

### AI 分析管线（Agent 架构）

- **Agent 1**（`identifier.py`）：建筑识别，输出 `{name, location, style, keywords}`
- **Agent 3**（`enhanced_analyzer.py`）：多视角融合（多图 BuildingDSL 合并 + Wikipedia 校准）
- `ai_analyzer.py`：串联完整管线，12 部分测绘思维框架 → BuildingDSL，含 `_coerce_material/int/float` 容错归一化

### 共享常量

`DEFAULT_MATERIALS`（`src/models/building.py`）：10 个全局部位材质的默认值，由 `dsl_validator.py` 和 `enhanced_analyzer.py` 共享引用，避免重复定义。

## 核心功能

- **AI 视觉分析**：上传照片，GLM-4V-Flash 识别建筑类型、尺寸、材料、风格
- **Wikipedia 查证**：识别到建筑名称后自动查 Wikipedia 获取真实尺寸校准
- **多角度融合**：支持上传多张角度照片，分析后合并结果
- **按颜色选材料**：AI 根据图片实际颜色选择最匹配的 Minecraft 方块
- **多建筑类型**：gate（大门）、tower（塔楼）、pagoda（塔）、bridge（桥）、arch（拱门）、generic（通用）
- **结构方块 / /place template 双支持**：≤48 格可用结构方块，≤128 格用 `/place template`
- **多版本兼容**：Java 1.12 ~ 1.20，自动方块 ID 映射与 fallback
- **BuildingDSL JSON 导出**：`--json-out` 输出完整结构化描述

## 开发

```powershell
# 运行测试
py -3 -m pytest tests/ -v

# 添加新方块映射
# 编辑 src/generator/block_map.py 中的 _PALETTE 字典

# 添加新几何生成器
# 在 geometry.py 中添加 generate_xxx 纯函数，在 block_builder.py 中注册
```

## 已知限制

- 圆形/弧线仅用阶梯状方块近似，非真正平滑曲面
- 内部布局（房间/楼梯/家具）仍较简单，依赖 AI 的 `floors` 等参数
- AI 输出细节（开间数、屋顶层数等）利用仍有限
- 暂不支持 Bedrock 版 `.mcstructure` 导出
- 无 CI / lint 自动化

详见 [GitHub Issues](https://github.com/chenguo1024/Minecraft-real-structure/issues)。

## 路线图

- [x] 项目结构设计与数据模型
- [x] CLI 入口 + Mock 分析器
- [x] AI 视觉分析集成（GLM-4V-Flash）
- [x] Wikipedia 建筑信息查证
- [x] 多角度照片融合
- [x] 多建筑类型生成（gate/tower/pagoda/bridge/arch/generic）
- [x] 颜色分组材料映射
- [x] FastAPI Web 界面
- [x] 多版本方块映射与自动 fallback
- [x] 多开间/台基/重檐大门生成器
- [x] 逐面生成（按 AI 对每个面的描述放置方块）
- [x] 曲线/圆形/非正交结构（阶梯近似）
- [x] 多样化屋顶（歇山/卷棚/重檐）
- [x] 内部结构（房间/楼梯/家具）
- [x] Wikipedia 深度利用（开间/进深解析）
- [x] Web 端 3D 预览（Three.js InstancedMesh）
- [x] 生成进度反馈（SSE /progress）
- [x] 结果页手动调整参数（/regenerate）
- [x] BuildingDSL V2（取代 BuildingDescription）
- [x] 几何生成器纯函数化
- [x] AI Agent 架构（Agent 1 快速识别）
- [ ] Bedrock `.mcstructure` 支持

## 许可证

MIT