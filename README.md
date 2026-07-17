# Minecraft Real Structure v1.1.2

> AI 驱动的工具，将现实世界建筑照片转换成 Minecraft 三维结构（.nbt 文件）。
> 
> 使用智谱 GLM-4V-Flash（永久免费）分析建筑图片，自动查 Wikipedia 校准尺寸，生成 Minecraft 可识别的结构文件。

## 工作流程

```
用户上传照片 → AI 视觉分析 → Wikipedia 查证 → 结构化 JSON → 方块生成器 → NBT 导出 → /place template 放置
```

## 技术栈

| 层 | 选型 | 用途 |
|---|---|---|
| 数据模型 | Pydantic v2 | 分析/生成/导出三层的共享数据契约 |
| AI 分析 | 智谱 GLM-4V-Flash (httpx 直连) | 从图片提取建筑结构化描述 |
| 数据查证 | Wikipedia API | 获取真实尺寸/风格/材料 |
| 方块生成 | Python + 颜色分组 BlockMap | 根据描述生成三维方块数组 |
| NBT 导出 | 手写 NBT 二进制 (GZip) | 写入 Minecraft 结构文件 |
| Web | FastAPI + Uvicorn + Jinja2 | HTTP 上传界面 |
| 测试 | pytest (118 个测试) | 全链路测试覆盖 |

## 项目结构

```
minecraft-real-structure/
├── README.md
├── pyproject.toml
├── src/
│   ├── analysis/
│   │   ├── ai_analyzer.py       # GLM-4V-Flash API 调用 + 值归一化
│   │   ├── enhanced_analyzer.py # 多角度融合 + Wikipedia 增强
│   │   └── mock_analyzer.py     # 测试用 mock 分析器
│   ├── generator/
│   │   ├── block_builder.py     # 方块生成引擎（gate/tower/pagoda/bridge/generic）
│   │   └── block_map.py         # 方块 ID 映射表（多版本+颜色材料别名）
│   ├── exporter/
│   │   └── nbt_exporter.py      # 手写 NBT 二进制格式（跳过空气方块）
│   ├── models/
│   │   └── building.py          # Pydantic 数据模型（数据契约）
│   ├── utils/
│   │   └── wikipedia.py         # Wikipedia 建筑信息查询
│   └── web/
│       ├── app.py               # FastAPI 应用
│       ├── templates/           # Jinja2 模板
│       └── static/              # CSS 样式
├── tests/
│   ├── test_block_builder.py
│   ├── test_block_map.py
│   ├── test_integration.py
│   ├── test_mock_analyzer.py
│   ├── test_models.py
│   └── test_nbt_exporter.py
├── data/
│   ├── uploads/                 # 用户上传的图片
│   └── structures/              # 生成的 .nbt 文件
└── docs/
    └── issues-v4.md             # v4 待实现功能
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
3. 结果页：Three.js InstancedMesh 3D 预览 + 全参数表单
4. 微调参数 → 点「重新生成」只走生成器，不再花钱调 AI（端点 `/regenerate`）
5. 下载 `.nbt`

> ⚠️ **存档目录硬编码**：`src/web/app.py` 第 24 行写死了 `D:/Plain Craft Launcher 2/.minecraft/versions/1.20/saves/新的世界/generated/minecraft/structures`。你的游戏装别处就改这行；不改也行——文件仍会落到 `data/structures/`，自己复制即可。

### B. 命令行 AI 分析

```powershell
$env:ZHIPU_API_KEY = "你的智谱API Key"
py -3 -m src.main analyze -i photo.jpg -v java-1.20 -o data/structures/mybuilding.nbt
```

`-v` 默认 `java-1.20`，可选 `java-1.12 / 1.13 / 1.17 / 1.20`；`-o` 默认 `data/structures/<图片名>.nbt`。

### C. Mock 分析（不调 AI，验证管线用）

无需 Key，用固定模板数据跑完整流程，改完代码快速验证：

```powershell
py -3 -m src.main mock -i photo.jpg -v java-1.20
# 输出到 data/structures/<图片名>_mock.nbt
```

### 把 .nbt 放进游戏

| 大小 | 方式 |
|---|---|
| ≤48×48×48 | `/give @s structure_block`，模式 LOAD，输入文件名（不带 `.nbt`） |
| 任意大小 ≤128³ | 游内按 T：`/place template minecraft:文件名`（文件需在 `<存档>/generated/minecraft/structures/` 下） |

超过 48³ 会在生成时打印 warning 提示改用 `/place template`。

### 跑测试

```powershell
py -3 -m pytest tests/ -q
# 期望：118 passed
```

`pyproject.toml` 已配 `-p no:cacheprovider -q`，不需要额外参数。常见报错：

| 症状 | 原因 | 解决 |
|---|---|---|
| `python: No module named pytest` | 用了 msys64 的 `python` | 改用 `py -3` |
| `PermissionError [Errno 13]` 写文件被拒 | 当前会话非管理员，仓库目录 ACL = Users RX | 管理员身份启动 PowerShell / opencode |
| `.pytest_cache` WinError 183 | 不同 pytest 版本 cache 残留冲突 | `Remove-Item -LiteralPath .pytest_cache -Recurse -Force` 重跑 |
| `pytest-of-<用户>` Temp 权限拒绝 | pytest 扫不到自己建的临时目录 | 加 `--basetemp=C:\Users\<你>\AppData\Local\Temp\opencode\pytest` |

## 核心功能

- **AI 视觉分析**：上传照片，GLM-4V-Flash 识别建筑类型、尺寸、材料、风格
- **Wikipedia 查证**：识别到建筑名称后自动查 Wikipedia 获取真实尺寸校准
- **多角度融合**：支持上传多张角度照片，分析后合并结果
- **按颜色选材料**：AI 根据图片实际颜色选择最匹配的 Minecraft 方块
- **多开间大门生成**：支持 bays（开间数）、platform_height（台基）、roof_tiers（重檐数）
- **多建筑类型**：gate（大门）、tower（塔楼）、pagoda（塔）、bridge（桥）、arch（拱门）、generic（通用）
- **结构方块 / /place template 双支持**：≤48 格可用结构方块，≤128 格用 `/place template`
- **多版本兼容**：Java 1.12 ~ 1.20，自动方块 ID 映射与 fallback

## Minecraft 放置命令

```minecraft
# 游戏内按 T 输入（文件名去掉 .nbt）
/place template minecraft:文件名
```

如果结构 >48×48×48，请使用 `/place template` 命令，结构方块无法放置。

## 开发

```bash
# 运行测试
py -3 -m pytest tests/ -v

# 添加新方块映射
# 编辑 src/generator/block_map.py 中的 _PALETTE 字典

# 添加新建筑类型
# 在 block_builder.py 中添加 _build_xxx 方法，在 build() 中注册
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
- [ ] Bedrock `.mcstructure` 支持

## 许可证

MIT
