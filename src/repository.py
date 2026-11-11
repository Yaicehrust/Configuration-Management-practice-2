"""Чтение локального JSON-репозитория в тестовом режиме."""

import json
from pathlib import Path
import re

from src.models import Dependency, Package


PACKAGE_NAME_RE = re.compile(r"^[A-Z]+$")


class RepositoryFormatError(ValueError):
    """Возникает, если структура локального тестового репозитория неверна."""


class TestRepository:
    """Загружает ориентированный граф с именами пакетов заглавными буквами."""

    def __init__(self, dependencies: dict[str, list[str]]) -> None:
        """Инициализирует объект."""
        self.dependencies = dependencies

    @classmethod
    def load(cls, path: str | Path) -> "TestRepository":
        """Читает и проверяет список смежности JSON из локального файла."""
        source = Path(path)
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except OSError as error:
            raise RepositoryFormatError(str(error)) from error
        except json.JSONDecodeError as error:
            message = f"Invalid JSON at line {error.lineno}."
            raise RepositoryFormatError(message) from error
        return cls(_validate_graph_data(data))

    def direct_dependencies(self, package: Package) -> list[Dependency]:
        """Возвращает непосредственные зависимости тестового пакета."""
        names = self.dependencies.get(package.name)
        if names is None:
            raise RepositoryFormatError(
                f"Package {package.name} is absent from the test repository."
            )
        return [
            Dependency(
                Package(name, package.version),
                f"={package.version}",
                "normal",
                False,
                None,
            )
            for name in names
        ]

    def package_dependencies(self, package: Package) -> list[Package]:
        """Возвращает идентификаторы пакетов для обхода графа."""
        return [
            item.package for item in self.direct_dependencies(package)
        ]

    def reverse_dependencies(self, package: Package) -> list[Package]:
        """Возвращает прямые обратные зависимости из локального графа."""
        if package.name not in self.dependencies:
            raise RepositoryFormatError(
                f"Package {package.name} is absent from the test repository."
            )
        return [
            Package(name, package.version)
            for name in self.reverse_adjacency()[package.name]
        ]

    def package_names(self) -> set[str]:
        """Возвращает имена всех пакетов локального репозитория."""
        return set(self.dependencies)

    def reverse_adjacency(self) -> dict[str, list[str]]:
        """Строит список смежности с обратным направлением всех рёбер."""
        reverse = {name: [] for name in self.dependencies}
        for package, names in self.dependencies.items():
            for dependency in names:
                reverse[dependency].append(package)
        return {
            name: sorted(dependents)
            for name, dependents in reverse.items()
        }


def _validate_graph_data(data: object) -> dict[str, list[str]]:
    """Проверяет заглавные имена пакетов и все упомянутые вершины."""
    if not isinstance(data, dict) or not data:
        message = "Repository must be a non-empty JSON object."
        raise RepositoryFormatError(message)
    graph: dict[str, list[str]] = {}
    for name, dependencies in data.items():
        if not isinstance(name, str) or not PACKAGE_NAME_RE.fullmatch(name):
            message = "Package names must be uppercase letters."
            raise RepositoryFormatError(message)
        if not isinstance(dependencies, list):
            message = f"Dependencies of {name} must be a list."
            raise RepositoryFormatError(message)
        if any(
            not isinstance(item, str) or not PACKAGE_NAME_RE.fullmatch(item)
            for item in dependencies
        ):
            message = "Dependency names must be uppercase letters."
            raise RepositoryFormatError(message)
        graph[name] = sorted(set(dependencies))
    _validate_references(graph)
    return graph


def _validate_references(graph: dict[str, list[str]]) -> None:
    """Проверяет, что каждое ребро ведёт к пакету из файла."""
    known = set(graph)
    referenced = {item for values in graph.values() for item in values}
    missing = sorted(referenced - known)
    if missing:
        names = ", ".join(missing)
        raise RepositoryFormatError(f"Undefined packages in graph: {names}.")
