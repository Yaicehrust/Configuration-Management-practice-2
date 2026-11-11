"""Reader for the local JSON repository used by the test mode."""

import json
from pathlib import Path
import re

from src.models import Dependency, Package


PACKAGE_NAME_RE = re.compile(r"^[A-Z]+$")


class RepositoryFormatError(ValueError):
    """Raised when a local test repository has an invalid structure."""


class TestRepository:
    """Load a directed graph whose package names are uppercase letters."""

    def __init__(self, dependencies: dict[str, list[str]]) -> None:
        self.dependencies = dependencies

    @classmethod
    def load(cls, path: str | Path) -> "TestRepository":
        """Read and validate a JSON adjacency list from a local file."""
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
        """Return the immediate dependencies of a test package."""
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

    def package_names(self) -> set[str]:
        """Return all package names in the local repository."""
        return set(self.dependencies)

    def reverse_adjacency(self) -> dict[str, list[str]]:
        """Build an adjacency list with every dependency edge reversed."""
        reverse = {name: [] for name in self.dependencies}
        for package, names in self.dependencies.items():
            for dependency in names:
                reverse[dependency].append(package)
        return {
            name: sorted(dependents)
            for name, dependents in reverse.items()
        }


def _validate_graph_data(data: object) -> dict[str, list[str]]:
    """Validate uppercase package names and all referenced vertices."""
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
    """Ensure every edge points to a package declared in the file."""
    known = set(graph)
    referenced = {item for values in graph.values() for item in values}
    missing = sorted(referenced - known)
    if missing:
        names = ", ".join(missing)
        raise RepositoryFormatError(f"Undefined packages in graph: {names}.")
