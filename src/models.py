"""Общие неизменяемые модели источников данных и операций с графом."""

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Package:
    """Идентификатор пакета: имя crate и точная версия."""

    name: str
    version: str

    @property
    def key(self) -> str:
        """Возвращает стабильный идентификатор вершины графа."""
        return f"{self.name}@{self.version}"

    @property
    def label(self) -> str:
        """Возвращает понятное имя пакета для вывода в командную строку."""
        return f"{self.name} {self.version}"


@dataclass(frozen=True)
class Dependency:
    """Ребро зависимости и выбранная версия целевого пакета."""

    package: Package
    requirement: str
    kind: str
    optional: bool
    target: str | None
