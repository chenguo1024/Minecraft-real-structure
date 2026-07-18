"""V2 CLI 主入口 —— 串联整个工作流：识别 → 分析 → 生成 → 导出。

设计理由：
  1. 使用 Click 而非 argparse：Click 天然支持子命令（mock/analyze/identify），自动生成 --help。
  2. 每个命令完成完整管线（分析→生成→导出），用户一次调用就拿到 .nbt 文件。
  3. --output 可选，默认根据图片名自动生成文件名，减少用户输入。
  4. V2 新增 identify 子命令（Agent 1 快速识别）和 --json 输出 BuildingDSL。
"""
import json
from pathlib import Path

import click

from src.analysis.ai_analyzer import analyze as ai_analyze
from src.analysis.identifier import identify as ai_identify
from src.analysis.mock_analyzer import analyze as mock_analyze
from src.exporter.nbt_exporter import export as export_nbt
from src.generator.block_builder import BlockBuilder
from src.models.building import BuildingDSL, MinecraftVersion


def _build_structure(desc: BuildingDSL, output: Path) -> None:
    """生成方块数据并导出为 .nbt 结构文件。"""
    builder = BlockBuilder(desc)
    structure = builder.build()

    click.echo(f"  方块 Palette: {len(structure.palette)} 种")
    click.echo(f"  结构尺寸: {structure.size_x}x{structure.size_y}x{structure.size_z}")
    click.echo(f"  方块总数: {len(structure.blocks)}")

    export_nbt(structure, output, desc.minecraft_version)
    click.echo(f"  结构文件已保存 → {output}")


def _resolve_version(version_str: str) -> MinecraftVersion:
    """将用户输入的版本字符串转为枚举值，不合法时报错。"""
    try:
        return MinecraftVersion(version_str)
    except ValueError:
        valid = "', '".join(v.value for v in MinecraftVersion)
        msg = f"不支持的版本: '{version_str}'。有效值: '{valid}'"
        raise click.BadParameter(msg)


@click.group()
def cli():
    """Minecraft Real Structure — 将建筑照片转为 Minecraft 结构文件。"""


@cli.command()
@click.option(
    "-i", "--image",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="输入建筑图片路径",
)
@click.option(
    "-v", "--version",
    default="java-1.20",
    show_default=True,
    help="目标 Minecraft 版本",
)
@click.option(
    "-o", "--output",
    type=click.Path(dir_okay=False),
    default=None,
    help="输出路径（默认: data/structures/<图片名>_mock.nbt）",
)
@click.option(
    "--json-out",
    type=click.Path(dir_okay=False),
    default=None,
    help="同时输出 BuildingDSL JSON 到指定路径",
)
def mock(image: str, version: str, output: str | None, json_out: str | None):
    """使用 Mock 分析器（无需 API 密钥），测试完整管线。"""
    mc_version = _resolve_version(version)
    click.echo(f"  Mock 分析: {image}")
    click.echo(f"  目标版本: {mc_version.value}")

    desc = mock_analyze(image, mc_version)
    click.echo(f"  建筑类型: {desc.building_type} ({desc.width}x{desc.height}x{desc.length})")
    click.echo(f"  风格: {desc.style}")
    click.echo(f"  组件数: {len(desc.components)}")

    if output is None:
        stem = Path(image).stem
        output = str(Path("data/structures") / f"{stem}_mock.nbt")

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _build_structure(desc, output_path)

    if json_out:
        Path(json_out).write_text(desc.model_dump_json(indent=2), encoding="utf-8")
        click.echo(f"  BuildingDSL JSON 已保存 → {json_out}")


@cli.command()
@click.option(
    "-i", "--image",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="输入建筑图片路径",
)
@click.option(
    "--api-key",
    envvar="ZHIPU_API_KEY",
    required=False,
    help="智谱 API Key（也可通过 ZHIPU_API_KEY 环境变量设置）",
)
@click.option(
    "-v", "--version",
    default="java-1.20",
    show_default=True,
    help="目标 Minecraft 版本",
)
@click.option(
    "-o", "--output",
    type=click.Path(dir_okay=False),
    default=None,
    help="输出路径（默认: data/structures/<图片名>.nbt）",
)
@click.option(
    "--json-out",
    type=click.Path(dir_okay=False),
    default=None,
    help="同时输出 BuildingDSL JSON 到指定路径",
)
def analyze(image: str, api_key: str | None, version: str, output: str | None, json_out: str | None):
    """使用 AI 视觉模型分析图片并生成 Minecraft 结构文件（V2 BuildingDSL）。"""
    mc_version = _resolve_version(version)
    click.echo(f"  分析图片: {image}")
    click.echo(f"  目标版本: {mc_version.value}")

    desc = ai_analyze(image, mc_version, api_key=api_key)
    click.echo(f"  建筑类型: {desc.building_type} ({desc.width}x{desc.height}x{desc.length})")
    click.echo(f"  风格: {desc.style}")
    click.echo(f"  组件数: {len(desc.components)}")
    click.echo(f"  曲线结构数: {len(desc.curves)}")
    if desc.building_name:
        click.echo(f"  识别建筑: {desc.building_name}")
    if desc.location:
        click.echo(f"  地点: {desc.location}")

    if output is None:
        stem = Path(image).stem
        output = str(Path("data/structures") / f"{stem}.nbt")

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _build_structure(desc, output_path)

    if json_out:
        Path(json_out).write_text(desc.model_dump_json(indent=2), encoding="utf-8")
        click.echo(f"  BuildingDSL JSON 已保存 → {json_out}")


@cli.command()
@click.option(
    "-i", "--image",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="输入建筑图片路径",
)
@click.option(
    "--api-key",
    envvar="ZHIPU_API_KEY",
    required=False,
    help="智谱 API Key",
)
def identify(image: str, api_key: str | None):
    """Agent 1：快速识别建筑元信息（名称/地点/风格/关键词）。"""
    result = ai_identify(image, api_key=api_key)
    click.echo(f"  名称: {result.name or '(未识别)'}")
    click.echo(f"  地点: {result.location or '(未知)'}")
    click.echo(f"  风格: {result.style}")
    click.echo(f"  关键词: {', '.join(result.keywords) if result.keywords else '(无)'}")


if __name__ == "__main__":
    cli()
