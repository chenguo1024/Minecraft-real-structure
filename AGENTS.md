# AGENTS.md — 给 opencode / AI 助手的项目指引

## 环境
- 工作目录：`D:\Minecraft-real-structure`（Windows，git 仓库，主分支 `main`）
- Python：本机 `py -3` = **Python 3.14**（`C:\Users\12190\AppData\Local\Programs\Python\Python314\python.exe`）
  - ⚠️ 不要用 `python`，那会指向 `C:\msys64\ucrt64\bin\python.exe`（无 pytest）。
  - pytest 版本：9.1.1
- 测试命令（**必须用这个**，已在 `pyproject.toml [tool.pytest.ini_options]` 配好）：
  ```powershell
  py -3 -m pytest tests/ -q
  ```
  期望：`216 passed`。
- 若报 `.pytest_cache` WinError 183：删除 `.pytest_cache` 目录后重跑。
- 若报 Temp 权限拒绝（`pytest-of-<用户>` 无法扫描）：加参数
  `--basetemp=C:\Users\12190\AppData\Local\Temp\opencode\pytest`

## 写权限注意
- 普通（非管理员）会话对 `D:\Minecraft-real-structure` **只读**（NTFS ACL: Users=RX）。
- 若写文件报 `FileSystem.writeFile` / `UnauthorizedAccessException` / `PermissionError [Errno 13]`，
  说明当前会话非管理员 —— 需用管理员身份重启 opencode。

## 代码结构要点（V2 架构）

### 数据契约：BuildingDSL（V2，取代旧 BuildingDescription）
- `src/models/building.py`：
  - `BuildingDSL`：顶层模型（building_name/type/style/location/keywords + 尺寸 + components + roof + walls + windows + entrance + curves + materials + 全局部位材质 + description）
  - `Component`：体块（name/shape=box|cylinder|sphere|cone|prism|arch|curve + width/length/height/radius + position + offset_x/y/z + material + rotation_deg）
  - `RoofSpec`：屋顶（type=flat|gable|hip|pyramid|dome|mansard|barrel|spire|chinese_roof + has_flying_eaves/eaves_curvature + spire_height/spire_angle）
  - `WallSpec`：墙体（type=plain_wall|pillar|pilaster|buttress|arcade|rustication|timber_frame + PillarSpec）
  - `WindowItem` / `WindowSystem`：窗户（shape=square|arch|pointed_arch|circle|bay_window|glass_wall + frame_material + glass_material）
  - `EntranceSpec`：入口（type=simple|arch|portal|porch|grand_stair|column_entrance + has_stairs/columns/roof_cover + curvature）
  - `CurveSpec`：曲线（type=arch|flying_eaves|baroque_wall|dome|sphere|cylinder|free_curve + arch_type + direction + curvature）
  - `BlockMaterial`：材料（name/color/percentage/location）

### 几何生成器：纯函数式
- `src/generator/geometry.py`：`generate_box/cylinder/sphere/cone/arch/curve/prism` + `rotate_y`
  - 签名：(setter, 坐标, 尺寸, material, hollow, w/h/l 边界) → None
  - setter 签名 `(x,y,z,material_name) -> None`，与 BlockBuilder._set 兼容
  - 支持边界保护 + hollow/solid + arch_type semicircle/pointed/ellipse + curvature

### 方块生成器
- `src/generator/block_builder.py`：`BlockBuilder` 接受 `BuildingDSL`，`build()` 按 components 逐个渲染 + 叠加 roof/walls/windows/entrance/curves
  - `BlockStructure`：输出（palette/blocks/size_x/y/z），NBT exporter 接口不变
- `src/generator/block_map.py`：方块 ID 映射，1.20 palette 含 200+ 方块（16 色 concrete/terracotta/glazed + copper + prismarine + quartz 全家 + 木材全家 + 彩色玻璃 + 砖/黑石 + 栏杆围墙楼梯）

### AI 分析（V2 Agent 架构）
- `src/analysis/identifier.py`：**Agent 1** 建筑识别，输出 `{name, location, style, keywords}`
- `src/analysis/ai_analyzer.py`：完整 AI 分析，输出 `BuildingDSL`（12 部分测绘思维框架 → BuildingDSL schema）
  - `_coerce_material/int/float` 容错归一化 + 子解析器 `_parse_components/roof/walls/windows/entrance/curves/materials`
- `src/analysis/enhanced_analyzer.py`：**Agent 3** 多视角融合（多图 BuildingDSL 合并 + Wikipedia 校准）
- `src/analysis/mock_analyzer.py`：Mock 分析器（5 模板：villa/gate/church/tower/temple），输出 BuildingDSL

### Web / CLI
- `src/web/app.py`：FastAPI（v1.2.0），`/analyze`（HTML+JSON）/ `/analyze-async`（后台任务）/ `/progress`（SSE）/ `/regenerate`（调参重生成）/ `/download`
  - `src/web/templates/result.html`：3D 预览（Three.js InstancedMesh）+ 组件/屋顶/曲线/墙体/材料展示 + 调参表单
- `src/main.py`：CLI，子命令 `mock` / `analyze` / `identify`，支持 `--json-out` 输出 BuildingDSL JSON

## 约定
- 修改后**必须**跑测试并确认 `216 passed`（或新数量）再交付。
- 不要自动 commit —— 等用户明确要求。
- 代码注释保持现状（中文为主），无必要不加新注释。

## 路线图剩余项
- Agent 2 网络搜索多视角图（V2 方案未完成项，需引入图像搜索 API，开工前先与用户确认范围）
- Bedrock `.mcstructure` 导出（唯一未完成路线图项，属较大功能）