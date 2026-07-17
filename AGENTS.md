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
  期望：`115 passed`。
- 若报 `.pytest_cache` WinError 183：删除 `.pytest_cache` 目录后重跑。
- 若报 Temp 权限拒绝（`pytest-of-<用户>` 无法扫描）：加参数
  `--basetemp=C:\Users\12190\AppData\Local\Temp\opencode\pytest`

## 写权限注意
- 普通（非管理员）会话对 `D:\Minecraft-real-structure` **只读**（NTFS ACL: Users=RX）。
- 若写文件报 `FileSystem.writeFile` / `UnauthorizedAccessException` / `PermissionError [Errno 13]`，
  说明当前会话非管理员 —— 需用管理员身份重启 opencode。

## 代码结构要点
- `src/generator/block_builder.py`（~950 行）核心生成引擎。
  - `build()` 按 `building_type` 分发；`_build_from_facades()` 是逐面生成分支。
  - 曲线辅助：`_circle_xz` / `_cylinder_y` / `_arch_curve`。
  - 屋顶：`_add_xieshan_roof` / `_add_curved_roof` / `_add_eaved_roof`。
  - `models/building.py`：`Facade` 模型（line 58）、`BuildingDescription.facades`（line 109）、
    `bays`/`roof_tiers`/`platform_height`（line 106-108）。
- Web：`src/web/app.py` —— `/progress`（SSE, line 41）、`/regenerate`（line 264）。
- 3D 预览：`src/web/templates/result.html` 内嵌 Three.js InstancedMesh。

## 约定
- 修改后**必须**跑测试并确认 `115 passed`（或新数量）再交付。
- 不要自动 commit —— 等用户明确要求。
- 代码注释保持现状（中文为主），无必要不加新注释。

## 路线图剩余项
- Bedrock `.mcstructure` 导出（唯一未完成路线图项，属较大功能，开工前先与用户确认范围）。