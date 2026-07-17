# Minecraft Real Structure

> AI 驱动的工具，将现实世界建筑照片转换成 Minecraft 三维结构。

## 工作流程

```
用户上传照片 → AI 视觉模型分析 → 结构化 JSON → 方块生成器 → Minecraft 结构文件 (.nbt)
```

## 技术栈

| 层 | 选型 | 用途 |
|---|---|---|
| 数据模型 | Pydantic | 分析/生成/导出三层的共享数据契约 |
| AI 分析 | OpenAI Vision API / Gemini Vision | 从图片提取建筑结构化描述 |
| 方块生成 | Python + 方块映射表 | 根据描述生成三维方块数组 |
| NBT 导出 | nbtlib | 写入 Minecraft 结构文件 |
| CLI | Click | 命令行入口 |
| Web (可选) | FastAPI + Uvicorn | HTTP 上传接口 |

## 项目结构

```
minecraft-real-structure/
├── README.md
├── pyproject.toml
├── requirements.txt
├── .gitignore
├── src/
│   ├── main.py              # CLI 入口
│   ├── models/
│   │   └── building.py      # Pydantic 数据模型（数据契约）
│   ├── analysis/
│   │   ├── ai_analyzer.py   # AI 视觉分析
│   │   └── mock_analyzer.py # 测试用 mock 分析器
│   ├── generator/
│   │   ├── block_builder.py # 方块生成引擎
│   │   └── block_map.py     # 方块 ID 映射表（按版本）
│   ├── exporter/
│   │   └── nbt_exporter.py  # NBT 结构文件导出
│   └── utils/
│       └── image_utils.py   # 图片预处理
├── tests/
└── data/structures/          # 生成的结构文件输出
```

---

## Minecraft 版本兼容性

本工具设计为**一份代码多版本兼容**，通过 `--minecraft-version` 参数指定目标版本。

### 支持的版本列表

| 版本标识 | Minecraft 版本 | 方块 ID 格式 | 导出格式 | 说明 |
|---|---|---|---|---|
| `java-1.12` | Java Edition 1.12.2 | 数字 ID (如 `1`=`stone`) | NBT `.nbt` | 旧版，数字 ID 已被 Mojang 废弃 |
| `java-1.13` | Java Edition 1.13–1.16 | 命名空间 ID (如 `minecraft:stone`) | NBT `.nbt` | **扁平化更新**，所有方块改为文本 ID |
| `java-1.17` | Java Edition 1.17–1.19 | 命名空间 ID | NBT `.nbt` | 新增深板岩层、铜块、蜡烛等方块 |
| `java-1.20` | Java Edition 1.20+ | 命名空间 ID | NBT `.nbt` | 新增樱花木、雕纹陶罐等 |
| `bedrock-1.20` | Bedrock Edition 1.20+ | 命名空间 ID | `.mcstructure` | **格式不同**，待开发 |

### 版本间的主要差异

#### 1. 方块 ID

```python
# 同一方块在不同版本的 ID（以石头为例）
JAVA_1_12:   "1"            # 数字 ID
JAVA_1_13+:  "minecraft:stone"  # 命名空间 ID
```

#### 2. 新增方块（低版本中不存在）

| 方块 | 加入版本 | 替换方案（低版本） |
|---|---|---|
| 深板岩 | 1.17 | → 圆石 |
| 铜块 | 1.17 | → 石砖 |
| 樱花木 | 1.20 | → 橡木 |
| 紫水晶 | 1.17 | → 品红色玻璃 |
|  Sculk  | 1.19 | → 黑色羊毛 |

#### 3. NBT 结构差异

Java 版 `1.12` 和 `1.13+` 的结构块 NBT 格式在根标签名称和数据版本字段上不同。导出器自动识别版本并写入对应的格式。

#### 4. Bedrock 版

基岩版使用 `.mcstructure` 格式（完全不同于 NBT二进制），计划在后续版本中支持。

### 生成时的版本选择策略

1. **用户通过参数指定** `--minecraft-version java-1.20`（默认）
2. generator 从 `block_map.py` 中读取对应版本的方块 ID 映射
3. exporter 根据版本写入正确的 NBT 数据版本和格式
4. 如果指定版本中缺少某些方块，自动 fallback 到最接近的替代方块

---

## 快速开始

```bash
# 克隆仓库
git clone https://github.com/your-username/minecraft-real-structure.git
cd minecraft-real-structure

# 安装依赖（推荐使用 venv）
python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate  # macOS/Linux

pip install -r requirements.txt

# 运行 CLI（使用 mock 模式，无需 AI 密钥）
python -m src.main mock --image photo.jpg --version java-1.20

# 运行 CLI（使用 OpenAI）
python -m src.main analyze --image photo.jpg --api-key sk-xxx
```

## 路线图

- [x] 项目结构设计与数据模型
- [x] CLI 入口 + Mock 分析器
- [ ] AI 视觉分析集成（OpenAI / Gemini）
- [ ] 基础方块生成器（矩形建筑）
- [ ] NBT 结构文件导出
- [ ] 复杂建筑生成（多层、屋顶、窗户等）
- [ ] FastAPI Web 界面
- [ ] Bedrock `.mcstructure` 支持
- [ ] 本地 AI 模型（LLaVA）支持

## 许可证

MIT
