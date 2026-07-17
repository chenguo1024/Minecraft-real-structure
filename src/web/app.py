from __future__ import annotations

import shutil
import uuid
import traceback
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

from src.analysis.enhanced_analyzer import analyze as enhanced_analyze
from src.analysis.mock_analyzer import analyze as mock_analyze
from src.exporter.nbt_exporter import export as export_nbt
from src.generator.block_builder import BlockBuilder
from src.models.building import MinecraftVersion, BuildingFeature

HERE = Path(__file__).resolve().parent
TEMPLATES_DIR = HERE / "templates"
STATIC_DIR = HERE / "static"
UPLOAD_DIR = Path("data/uploads")
STRUCTURES_DIR = Path("data/structures")
MINECRAFT_STRUCTURES_DIR = Path("D:/Plain Craft Launcher 2/.minecraft/versions/1.20/saves/新的世界/generated/minecraft/structures")

app = FastAPI(title="Minecraft Real Structure", version="1.0.1")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# 进度跟踪：task_id → progress dict
# 描述存储：task_id → BuildingDescription (用于重新生成)
# 结果存储：task_id → dict (用于异步进度流)
progress_store: dict[str, dict] = {}
desc_store: dict[str, BuildingDescription] = {}
result_store: dict[str, dict] = {}


def set_progress(task_id: str, step: str, pct: int, message: str) -> None:
    progress_store[task_id] = {"step": step, "pct": pct, "message": message}


@app.get("/progress/{task_id}")
async def get_progress(task_id: str):
    p = progress_store.get(task_id, {"step": "unknown", "pct": 0, "message": "无进度信息"})
    return p


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


@app.get("/result/{task_id}")
async def get_result(task_id: str):
    """获取异步生成的结果页面。"""
    result = result_store.get(task_id)
    if not result:
        # 还没完成，返回进度页面
        p = progress_store.get(task_id, {"pct": 0, "message": "等待中..."})
        return _render("progress.html", task_id=task_id, pct=p["pct"], message=p["message"])
    return _render("result.html", **result)


def _run_analysis(task_id: str, image_paths: list[str],
                  mc_version: MinecraftVersion, api_key: str | None) -> None:
    """后台运行分析（同步函数，在 BackgroundTasks 中执行）。"""
    import asyncio
    try:
        set_progress(task_id, "analyze", 20, "AI 分析建筑照片...")
        if api_key:
            desc = enhanced_analyze(image_paths, mc_version, api_key=api_key)
        else:
            desc = mock_analyze(image_paths[0], mc_version)

        set_progress(task_id, "build", 60, "正在生成三维结构...")
        builder = BlockBuilder(desc)
        structure = builder.build()

        set_progress(task_id, "export", 80, "正在导出 NBT 文件...")
        nbt_filename = f"{task_id}.nbt"
        nbt_path = STRUCTURES_DIR / nbt_filename
        STRUCTURES_DIR.mkdir(parents=True, exist_ok=True)
        export_nbt(structure, nbt_path, mc_version)

        try:
            mc_path = MINECRAFT_STRUCTURES_DIR / nbt_filename
            MINECRAFT_STRUCTURES_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(nbt_path), str(mc_path))
        except Exception:
            pass

        roof_type = "flat"
        for f in desc.features:
            if f.feature_type == "roof" and f.position:
                roof_type = f.position

        desc_store[task_id] = desc
        result_store[task_id] = dict(
            desc=desc,
            block_total=len(structure.blocks),
            size_x=structure.size_x,
            size_y=structure.size_y,
            size_z=structure.size_z,
            palette=structure.palette,
            blocks_json=structure.blocks,
            roof_type=roof_type,
            task_id=task_id,
            download_url=f"/download/{nbt_filename}",
        )
        set_progress(task_id, "done", 100, "生成完成")
    except Exception as e:
        progress_store[task_id] = {"step": "error", "pct": -1, "message": str(e)}


@app.post("/analyze-async")
async def analyze_async(
    background_tasks: BackgroundTasks,
    images: list[UploadFile] = File(...),
    version: str = Form("java-1.20"),
    api_key: str | None = Form(None),
):
    """异步分析：立即返回任务 ID，前端轮询进度。"""
    try:
        mc_version = MinecraftVersion(version)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"不支持的版本: {version}")

    task_id = uuid.uuid4().hex[:12]
    image_paths = []
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    set_progress(task_id, "upload", 5, "正在保存上传图片...")

    for i, img_file in enumerate(images):
        ext = Path(img_file.filename or "unknown").suffix or ".jpg"
        img_path = UPLOAD_DIR / f"{task_id}_{i}{ext}"
        content = img_file.file.read()
        img_path.write_bytes(content)
        image_paths.append(str(img_path))

    background_tasks.add_task(_run_analysis, task_id, image_paths, mc_version, api_key)

    return _render("progress.html", task_id=task_id, pct=5, message="图片已上传，开始 AI 分析...")


@app.post("/analyze")
async def analyze(
    request: Request,
    images: list[UploadFile] = File(...),
    version: str = Form("java-1.20"),
    api_key: str | None = Form(None),
):
    """上传一张或多张照片 → AI 分析 → Wikipedia 查证 → 生成 → 下载。"""
    try:
        mc_version = MinecraftVersion(version)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"不支持的版本: {version}")

    file_id = uuid.uuid4().hex[:12]
    task_id = file_id
    image_paths = []
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    set_progress(task_id, "upload", 5, "正在保存上传图片...")

    for i, img_file in enumerate(images):
        ext = Path(img_file.filename or "unknown").suffix or ".jpg"
        img_path = UPLOAD_DIR / f"{file_id}_{i}{ext}"
        content = await img_file.read()
        img_path.write_bytes(content)
        image_paths.append(str(img_path))

    try:
        set_progress(task_id, "analyze", 20, "AI 分析建筑照片...")
        if api_key:
            desc = enhanced_analyze(image_paths, mc_version, api_key=api_key)
        else:
            desc = mock_analyze(image_paths[0], mc_version)
        set_progress(task_id, "build", 60, "正在生成三维结构...")
    except Exception as e:
        tb = traceback.format_exc()
        return _render(
            "error.html",
            error=str(e),
            detail=tb,
        )

    builder = BlockBuilder(desc)
    structure = builder.build()
    set_progress(task_id, "export", 80, "正在导出 NBT 文件...")

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

    roof_type = "flat"
    for f in desc.features:
        if f.feature_type == "roof" and f.position:
            roof_type = f.position

    set_progress(task_id, "done", 100, "生成完成")

    # 存储描述用于后续重新生成
    desc_store[task_id] = desc

    # 存储结果用于异步流
    result_store[task_id] = dict(
        desc=desc,
        block_total=len(structure.blocks),
        size_x=structure.size_x,
        size_y=structure.size_y,
        size_z=structure.size_z,
        palette=structure.palette,
        blocks_json=structure.blocks,
        roof_type=roof_type,
        task_id=task_id,
        download_url=f"/download/{nbt_filename}",
    )

    return _render(
        "result.html",
        desc=desc,
        block_total=len(structure.blocks),
        size_x=structure.size_x,
        size_y=structure.size_y,
        size_z=structure.size_z,
        palette=structure.palette,
        blocks_json=structure.blocks,
        roof_type=roof_type,
        task_id=task_id,
        download_url=f"/download/{nbt_filename}",
    )


@app.post("/regenerate")
async def regenerate(
    request: Request,
    width: int = Form(...),
    height: int = Form(...),
    length: int = Form(...),
    floors: int = Form(1),
    detail_scale: int = Form(1),
    style: str = Form("modern"),
    building_type: str = Form("house"),
    roof_type: str = Form("flat"),
    task_id: str = Form(""),
):
    """根据调整后的参数重新生成。"""
    try:
        # 尝试复用原始 AI 分析结果
        original_desc = desc_store.get(task_id)

        from src.analysis.mock_analyzer import analyze as mock_analyze

        if original_desc:
            desc = original_desc.model_copy(deep=True)
        else:
            desc = mock_analyze("dummy.jpg", MinecraftVersion.JAVA_1_20)

        desc.height = max(1, min(height, 128))
        desc.width = max(1, min(width, 128))
        desc.length = max(1, min(length, 128))
        desc.floors = max(1, floors)
        desc.detail_scale = max(1, min(detail_scale, 8))
        desc.style = style
        desc.building_type = building_type

        # Override roof type
        found_roof = False
        for f in desc.features:
            if f.feature_type == "roof":
                f.position = roof_type
                found_roof = True
                break
        if not found_roof:
            desc.features.append(BuildingFeature(feature_type="roof", position=roof_type))

        builder = BlockBuilder(desc)
        structure = builder.build()

        nbt_filename = f"{task_id or uuid.uuid4().hex[:12]}.nbt"
        nbt_path = STRUCTURES_DIR / nbt_filename
        STRUCTURES_DIR.mkdir(parents=True, exist_ok=True)
        from src.exporter.nbt_exporter import export as export_nbt
        export_nbt(structure, nbt_path, MinecraftVersion.JAVA_1_20)

        try:
            mc_path = MINECRAFT_STRUCTURES_DIR / nbt_filename
            MINECRAFT_STRUCTURES_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(nbt_path), str(mc_path))
        except Exception:
            pass

        roof_type_val = roof_type

        return _render(
            "result.html",
            desc=desc,
            block_total=len(structure.blocks),
            size_x=structure.size_x,
            size_y=structure.size_y,
            size_z=structure.size_z,
            palette=structure.palette,
            blocks_json=structure.blocks,
            roof_type=roof_type_val,
            task_id=task_id,
            download_url=f"/download/{nbt_filename}",
        )
    except Exception as e:
        tb = traceback.format_exc()
        return _render("error.html", error=str(e), detail=tb)


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
