from __future__ import annotations

import shutil
import uuid
import traceback
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
MINECRAFT_STRUCTURES_DIR = Path("D:/Plain Craft Launcher 2/.minecraft/versions/1.20/saves/新的世界/generated/minecraft/structures")

app = FastAPI(title="Minecraft Real Structure", version="0.2.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _render(name: str, **context) -> HTMLResponse:
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))
    template = env.get_template(name)
    return HTMLResponse(template.render(**context))


@app.get("/", response_class=HTMLResponse)
async def home():
    import os
    default_key = os.environ.get("ZHIPU_API_KEY", "")
    return _render("index.html", default_api_key=default_key)


@app.post("/analyze")
async def analyze(
    request: Request,
    images: UploadFile = File(...),
    version: str = Form("java-1.20"),
    api_key: str | None = Form(None),
):
    """上传一张或多张照片 → AI 分析 → Wikipedia 查证 → 生成 → 下载。"""
    try:
        mc_version = MinecraftVersion(version)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"不支持的版本: {version}")

    file_id = uuid.uuid4().hex[:12]
    image_paths = []
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    ext = Path(images.filename or "unknown").suffix or ".jpg"
    img_path = UPLOAD_DIR / f"{file_id}_0{ext}"
    content = await images.read()
    img_path.write_bytes(content)
    image_paths.append(str(img_path))

    try:
        if api_key:
            desc = enhanced_analyze(image_paths, mc_version, api_key=api_key)
        else:
            desc = mock_analyze(image_paths[0], mc_version)
    except Exception as e:
        tb = traceback.format_exc()
        return _render(
            "error.html",
            error=str(e),
            detail=tb,
        )

    builder = BlockBuilder(desc)
    structure = builder.build()

    nbt_filename = f"{file_id}.nbt"
    nbt_path = STRUCTURES_DIR / nbt_filename
    STRUCTURES_DIR.mkdir(parents=True, exist_ok=True)
    export_nbt(structure, nbt_path, mc_version)

    # 自动拷贝到 Minecraft 结构文件夹
    try:
        mc_path = MINECRAFT_STRUCTURES_DIR / nbt_filename
        MINECRAFT_STRUCTURES_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(nbt_path), str(mc_path))
    except Exception:
        pass

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
