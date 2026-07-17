"""FastAPI Web 应用 —— 提供图片上传和结构文件下载的界面。

设计理由：
  1. 使用 FastAPI + Jinja2 模板渲染，不走前后端分离。
  2. 支持多张照片上传（不同角度），AI + Wikipedia 融合分析。
  3. 上传的图片存到 data/uploads/，生成的 .nbt 存到 data/structures/。
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

from src.analysis.enhanced_analyzer import analyze as enhanced_analyze
from src.analysis.mock_analyzer import analyze as mock_analyze
from src.exporter.nbt_exporter import export as export_nbt
from src.generator.block_builder import BlockBuilder
from src.models.building import MinecraftVersion

HERE = Path(__file__).resolve().parent
TEMPLATES_DIR = HERE / "templates"
STATIC_DIR = HERE / "static"
UPLOAD_DIR = Path("data/uploads")
STRUCTURES_DIR = Path("data/structures")

app = FastAPI(title="Minecraft Real Structure", version="0.2.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _render(name: str, **context) -> HTMLResponse:
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template(name)
    return HTMLResponse(template.render(**context))


@app.get("/", response_class=HTMLResponse)
async def home():
    return _render("index.html")


@app.post("/analyze")
async def analyze(
    request: Request,
    images: list[UploadFile] = File(...),
    version: str = Form("java-1.20"),
    api_key: str | None = Form(None),
):
    """上传一张或多张照片（不同角度） → AI 分析 → Wikipedia 查证 → 生成 → 下载。

    多张照片从不同角度分析后融合结果，Wikipedia 提供真实尺寸数据。
    不填 API Key 时使用 Mock 分析器（固定模板）。
    """
    try:
        mc_version = MinecraftVersion(version)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"不支持的版本: {version}")

    # 保存上传图片
    file_id = uuid.uuid4().hex[:12]
    image_paths = []
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    for img in images:
        ext = Path(img.filename or "unknown").suffix or ".jpg"
        img_path = UPLOAD_DIR / f"{file_id}_{len(image_paths)}{ext}"
        content = await img.read()
        img_path.write_bytes(content)
        image_paths.append(str(img_path))

    # 分析（增强模式：多角度 + Wikipedia，或 Mock）
    if api_key:
        desc = enhanced_analyze(image_paths, mc_version, api_key=api_key)
    else:
        # Mock 只分析第一张
        desc = mock_analyze(image_paths[0], mc_version)

    # 生成
    builder = BlockBuilder(desc)
    structure = builder.build()

    # 导出
    nbt_filename = f"{file_id}.nbt"
    nbt_path = STRUCTURES_DIR / nbt_filename
    STRUCTURES_DIR.mkdir(parents=True, exist_ok=True)
    export_nbt(structure, nbt_path, mc_version)

    # 返回
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
    file_path = STRUCTURES_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在或已过期")
    return FileResponse(
        path=str(file_path),
        media_type="application/octet-stream",
        filename=filename,
    )
