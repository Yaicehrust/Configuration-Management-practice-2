"""Создание исходного текста D2 и PNG через командную строку D2."""

import json
from pathlib import Path
import shutil
import subprocess

from src.graph import DependencyGraph


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
RENDER_TIMEOUT = 120
SUCCESS_EXIT_CODE = 0


class VisualizationError(RuntimeError):
    """Возникает, если D2 отсутствует или не может построить диаграмму."""


def build_d2_source(graph: DependencyGraph) -> str:
    """Создаёт воспроизводимое описание D2 для вершин и рёбер графа."""
    packages = sorted(graph)
    identifiers = {
        package: f"node_{index}" for index, package in enumerate(packages)
    }
    lines = ["direction: right", ""]
    for package in packages:
        label = json.dumps(package.label, ensure_ascii=False)
        lines.append(f"{identifiers[package]}: {label}")
    lines.append("")
    for package in packages:
        for dependency in sorted(graph[package]):
            left = identifiers[package]
            right = identifiers[dependency]
            lines.append(f"{left} -> {right}")
    return "\n".join(lines) + "\n"


def write_d2_file(graph: DependencyGraph, output: Path) -> Path:
    """Записывает описание D2 в UTF-8 рядом с целевым PNG-файлом."""
    source = output.with_suffix(".d2")
    try:
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(build_d2_source(graph), encoding="utf-8")
    except OSError as error:
        raise VisualizationError(
            f"Cannot write D2 source file: {source}"
        ) from error
    return source


def render_png(source: Path, output: Path) -> Path:
    """Запускает D2 и проверяет корректность созданного PNG-файла."""
    executable = shutil.which("d2")
    if executable is None:
        raise VisualizationError(
            "D2 CLI was not found. Install D2 and add d2.exe to PATH."
        )
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(
            [executable, str(source), str(output)],
            capture_output=True,
            text=True,
            check=False,
            timeout=RENDER_TIMEOUT,
        )
    except subprocess.TimeoutExpired as error:
        raise VisualizationError(
            f"D2 rendering exceeded {RENDER_TIMEOUT} seconds."
        ) from error
    except OSError as error:
        raise VisualizationError("Could not start the D2 process.") from error
    _check_process_result(result)
    _verify_png(output)
    return output


def _check_process_result(result: subprocess.CompletedProcess) -> None:
    """Преобразует ошибочный код завершения D2 в понятное сообщение."""
    if result.returncode == SUCCESS_EXIT_CODE:
        return
    details = result.stderr.strip() or result.stdout.strip()
    if not details:
        details = f"exit code {result.returncode}"
    raise VisualizationError(f"D2 rendering failed: {details}")


def _verify_png(output: Path) -> None:
    """Проверяет сигнатуру PNG после успешного завершения D2."""
    try:
        with output.open("rb") as image_file:
            signature = image_file.read(len(PNG_SIGNATURE))
    except OSError as error:
        raise VisualizationError(
            f"D2 did not create the output image: {output}"
        ) from error
    if signature != PNG_SIGNATURE:
        raise VisualizationError("D2 output is not a valid PNG image.")
