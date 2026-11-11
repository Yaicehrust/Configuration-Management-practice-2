"""Tests for local test repository loading."""

import unittest
from pathlib import Path

from src.models import Package
from src.repository import (
    RepositoryFormatError, TestRepository, _validate_graph_data,
)


DATA = Path(__file__).parent / "data"


class RepositoryTests(unittest.TestCase):
    """Check graph loading, direct edges and reverse adjacency."""

    def test_loads_direct_dependencies(self) -> None:
        repository = TestRepository.load(DATA / "repository.json")
        dependencies = repository.direct_dependencies(Package("A", "1.0.0"))
        self.assertEqual(
            [item.package.name for item in dependencies], ["B", "C"]
        )

    def test_loads_leaf_package(self) -> None:
        repository = TestRepository.load(DATA / "simple.json")
        dependencies = repository.direct_dependencies(Package("B", "1.0.0"))
        self.assertEqual(dependencies, [])

    def test_rejects_undefined_references(self) -> None:
        with self.assertRaises(RepositoryFormatError):
            _validate_graph_data({"A": ["B"]})

    def test_rejects_lowercase_names(self) -> None:
        with self.assertRaises(RepositoryFormatError):
            _validate_graph_data({"a": []})

    def test_reverse_dependencies_for_package(self) -> None:
        repository = TestRepository.load(DATA / "repository.json")
        dependents = repository.reverse_dependencies(Package("E", "1.0.0"))
        self.assertEqual(
            [item.name for item in dependents], ["C", "D"]
        )

    def test_reverse_adjacency(self) -> None:
        repository = TestRepository.load(DATA / "repository.json")
        reverse = repository.reverse_adjacency()
        self.assertEqual(reverse["B"], ["A", "E"])
        self.assertEqual(reverse["E"], ["C", "D"])


if __name__ == "__main__":
    unittest.main()
