"""CLI 主入口 —— 串联整个工作流：分析 → 生成 → 导出。

设计理由：
  1. 使用 Click 而非 argparse：Click 天然支持子命令（mock/analyze），自动生成 --help。
  2. 每个命令完成完整管线（分析→生成→导出），用户一次调用就拿到 .nbt 文件。
  3. --output 可选，默认根据图片名自动生成文件名，减少用户输入。
"""

import json
from pathlib import Path

import click

from src.analysis.ai_analyzer import analyze as ai_analyze
from src.analysis.mock_analyzer import analyze as mock_analyze
from src.exporter.nbt_exporter import export as export_nbt
from src.generator.block_builder import BlockBuilder
from src.models.building import BuildingDescription, MinecraftVersion


def _build_structure(desc: BuildingDescription, output: Path) -> None:
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
    help="输出路径（默认: data/structures/<图片名>.json）",
)
def mock(image: str, version: str, output: str | None):
    """使用 Mock 分析器（无需 API 密钥），测试完整管线。"""
    mc_version = _resolve_version(version)
    click.echo(f"  Mock 分析: {image}")
    click.echo(f"  目标版本: {mc_version.value}")

    desc = mock_analyze(image, mc_version)
    click.echo(f"  建筑类型: {desc.building_type} ({desc.width}x{desc.height}x{desc.length})")

    if output is None:
        stem = Path(image).stem
        output = str(Path("data/structures") / f"{stem}_mock.nbt")

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _build_structure(desc, output_path)


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
def analyze(image: str, api_key: str | None, version: str, output: str | None):
    """使用 AI 视觉模型分析图片并生成 Minecraft 结构文件。"""
    mc_version = _resolve_version(version)
    click.echo(f"  分析图片: {image}")
    click.echo(f"  目标版本: {mc_version.value}")

    desc = ai_analyze(image, mc_version, api_key=api_key)
    click.echo(f"  建筑类型: {desc.building_type} ({desc.width}x{desc.height}x{desc.length})")

    if output is None:
        stem = Path(image).stem
        output = str(Path("data/structures") / f"{stem}.nbt")

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _build_structure(desc, output_path)


if __name__ == "__main__":
    cli()
