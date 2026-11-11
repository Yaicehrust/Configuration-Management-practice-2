"""Small immutable models shared by data sources and graph operations."""

from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Package:
    """A package identity consisting of its crate name and exact version."""

    name: str
    version: str

    @property
    def key(self) -> str:
        """Return a stable identity suitable for graph node identifiers."""
        return f"{self.name}@{self.version}"

    @property
    def label(self) -> str:
        """Return a readable package label for command-line output."""
        return f"{self.name} {self.version}"


@dataclass(frozen=True)
class Dependency:
    """A dependency edge and the version selected for its target package."""

    package: Package
    requirement: str
    kind: str
    optional: bool
    target: str | None
