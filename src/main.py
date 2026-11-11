"""Точка входа приложения анализа зависимостей."""

import argparse
import sys

from src.cargo_registry import CratesIoClient, RegistryError
from src.config import Config, ConfigurationError, validate_config
from src.graph import (
    GraphError,
    build_dependency_graph,
    format_graph,
    graph_counts,
    has_cycle,
)
from src.models import Dependency, Package
from src.repository import RepositoryFormatError, TestRepository
from src.visualization import (
    VisualizationError, render_png, write_d2_file,
)


def build_parser() -> argparse.ArgumentParser:
    """Создаёт разборщик командной строки и объявляет параметры."""
    parser = argparse.ArgumentParser(
        description="Build and visualize a Cargo package dependency graph."
    )
    parser.add_argument("--package", required=True, help="Package name.")
    parser.add_argument(
        "--repo", required=True, help="Registry URL or JSON file."
    )
    parser.add_argument(
        "--test-mode", action="store_true", help="Read a test JSON."
    )
    parser.add_argument(
        "--version", required=True, help="Exact root package version."
    )
    parser.add_argument(
        "--output", default="dependency-graph.png", help="PNG output path."
    )
    parser.add_argument(
        "--filter", default=None, help="Ignore names containing text."
    )
    parser.add_argument(
        "--reverse", action="store_true", help="Show reverse dependencies."
    )
    return parser


def print_config(config: Config) -> None:
    """Выводит шесть настраиваемых параметров в формате ключ — значение."""
    values = (
        ("package", config.package),
        ("repository", config.repository),
        ("test_mode", config.test_mode),
        ("version", config.version),
        ("output", str(config.output)),
        ("filter", config.filter_substring),
    )
    for key, value in values:
        print(f"{key} = {value}")


def print_dependencies(
    package: Package, dependencies: list[Dependency]
) -> None:
    """Выводит имена прямых зависимостей, требования и типы связей Cargo."""
    print(f"\nDirect dependencies of {package.label}:")
    if not dependencies:
        print("  (none)")
        return
    for item in dependencies:
        print(_format_dependency(item))


def _format_dependency(item: Dependency) -> str:
    """Форматирует одно ребро зависимости для вывода в терминал."""
    markers = [item.kind]
    if item.optional:
        markers.append("optional")
    if item.target:
        markers.append(f"target={item.target}")
    details = ", ".join(markers)
    return (
        f"  - {item.package.name} {item.package.version} "
        f"(requirement {item.requirement}; {details})"
    )


def _load_source(config: Config) -> TestRepository | CratesIoClient:
    """Создаёт источник данных, не меняя логику построения графа."""
    if config.test_mode:
        return TestRepository.load(config.repository)
    return CratesIoClient(config.repository)


def main(argv: list[str] | None = None) -> int:
    """Разбирает настройки, загружает прямые зависимости и ошибки."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = validate_config(args)
        print_config(config)
        source = _load_source(config)
        package = Package(config.package, config.version)
        if args.reverse:
            dependents = source.reverse_dependencies(package)
            print_reverse_dependencies(package, dependents)
            getter = source.reverse_dependencies
            title = "Reverse dependency graph"
        else:
            dependencies = source.direct_dependencies(package)
            print_dependencies(package, dependencies)
            getter = source.package_dependencies
            title = "Dependency graph"
        graph = build_dependency_graph(
            package, getter, config.filter_substring
        )
        _print_graph_report(graph, title)
        d2_path = write_d2_file(graph, config.output)
        png_path = render_png(d2_path, config.output)
        print(f"\nD2 source: {d2_path}")
        print(f"PNG image: {png_path}")
    except (
        ConfigurationError,
        RepositoryFormatError,
        RegistryError,
        GraphError,
        VisualizationError,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    return 0


def print_reverse_dependencies(
    package: Package, dependents: list[Package]
) -> None:
    """Выводит пакеты, напрямую зависящие от выбранного пакета."""
    print(f"\nDirect reverse dependencies of {package.label}:")
    if not dependents:
        print("  (none)")
        return
    for dependent in dependents:
        print(f"  - {dependent.label}")


def _print_graph_report(
    graph: dict[Package, list[Package]], title: str
) -> None:
    """Выводит достижимый граф и сообщает о наличии циклов."""
    nodes, edges = graph_counts(graph)
    print(f"\n{title}:")
    print(format_graph(graph))
    print(f"\nPackages: {nodes}; edges: {edges}")
    status = "detected" if has_cycle(graph) else "not detected"
    print(f"Cycle: {status}")


if __name__ == "__main__":
    sys.exit(main())
