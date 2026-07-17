"""FastAPI Web 应用 —— 提供图片上传和结构文件下载的界面。

设计理由：
  1. 使用 FastAPI + Jinja2 模板渲染，不走前后端分离。
     MVP 阶段减少 JS 代码量，一个 HTML 模板搞定。
  2. 上传的图片存到 data/uploads/，生成的 .nbt 存到 data/structures/，
     各自独立的清理策略（上传文件可定时删除，结构文件永久保留）。
  3. /analyze 接口同时返回 JSON 和 HTML，API 消费者和浏览器用户都能用。
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

from src.analysis.ai_analyzer import analyze as ai_analyze
from src.analysis.mock_analyzer import analyze as mock_analyze
from src.exporter.nbt_exporter import export as export_nbt
from src.generator.block_builder import BlockBuilder
from src.models.building import MinecraftVersion

# ── 路径常量 ──
HERE = Path(__file__).resolve().parent
TEMPLATES_DIR = HERE / "templates"
STATIC_DIR = HERE / "static"
UPLOAD_DIR = Path("data/uploads")
STRUCTURES_DIR = Path("data/structures")

app = FastAPI(title="Minecraft Real Structure", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _render(name: str, **context) -> HTMLResponse:
    """渲染 Jinja2 模板。手动加载以避免额外依赖 FastAPI 的模板集成。"""
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template(name)
    return HTMLResponse(template.render(**context))


@app.get("/", response_class=HTMLResponse)
async def home():
    """上传页面。"""
    return _render("index.html")


@app.post("/analyze")
async def analyze(
    request: Request,
    image: UploadFile = File(...),
    version: str = Form("java-1.20"),
    api_key: str | None = Form(None),
):
    """上传图片 → 分析 → 生成 → 返回结果页。

    填写 API Key 时使用 GLM-4V-Flash 真实 AI 分析，
    不填时使用 Mock 分析器（返回固定数据，用于测试）。
    Accept 头含 application/json 时返回 JSON，否则返回 HTML。
    """
    # ── 1. 校验版本 ──
    try:
        mc_version = MinecraftVersion(version)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"不支持的版本: {version}")

    # ── 2. 保存上传图片 ──
    file_id = uuid.uuid4().hex[:12]
    ext = Path(image.filename or "unknown").suffix or ".jpg"
    image_path = UPLOAD_DIR / f"{file_id}{ext}"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    content = await image.read()
    image_path.write_bytes(content)

    # ── 3. 分析图片（真实 AI 或 Mock） ──
    if api_key:
        desc = ai_analyze(str(image_path), mc_version, api_key=api_key)
    else:
        desc = mock_analyze(str(image_path), mc_version)

    # ── 4. 生成方块结构 ──
    builder = BlockBuilder(desc)
    structure = builder.build()

    # ── 5. 导出 .nbt ──
    nbt_filename = f"{file_id}.nbt"
    nbt_path = STRUCTURES_DIR / nbt_filename
    STRUCTURES_DIR.mkdir(parents=True, exist_ok=True)
    export_nbt(structure, nbt_path, mc_version)

    # ── 6. 返回结果 ──
    accept = request.headers.get("accept", "")
    is_json = "application/json" in accept

    if is_json:
        return {
            "building": desc.model_dump(),
            "structure": {
                "size": [structure.size_x, structure.size_y, structure.size_z],
                "palette": structure.palette,
                "block_count": len(structure.blocks),
            },
            "download_url": f"/download/{nbt_filename}",
        }

    return _render(
        "result.html",
        desc=desc,
        block_total=len(structure.blocks),
        size_x=structure.size_x,
        size_y=structure.size_y,
        size_z=structure.size_z,
        palette=structure.palette,
        download_url=f"/download/{nbt_filename}",
    )


@app.get("/download/{filename}")
async def download(filename: str):
    """下载生成的 .nbt 结构文件。"""
    file_path = STRUCTURES_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在或已过期")

    return FileResponse(
        path=str(file_path),
        media_type="application/octet-stream",
        filename=filename,
    )
