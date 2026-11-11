"""Tests for BFS traversal, filtering and directed-cycle handling."""

import unittest
from pathlib import Path

from src.graph import (
    GraphError, build_dependency_graph, graph_counts, has_cycle,
)
from src.models import Package
from src.repository import TestRepository


DATA = Path(__file__).parent / "data"


class GraphTests(unittest.TestCase):
    """Exercise BFS with branches, duplicate reachability and cycles."""

    def setUp(self) -> None:
        self.repository = TestRepository.load(DATA / "repository.json")
        self.root = Package("A", "1.0.0")

    def test_bfs_visits_all_nodes_and_keeps_cycle_edge(self) -> None:
        graph = build_dependency_graph(
            self.root, self.repository.package_dependencies
        )
        names = {package.name for package in graph}
        self.assertEqual(names, {"A", "B", "C", "D", "E"})
        edge_names = {
            (source.name, target.name)
            for source, targets in graph.items()
            for target in targets
        }
        self.assertIn(("E", "B"), edge_names)
        self.assertEqual(graph_counts(graph), (5, 7))

    def test_each_package_is_expanded_once(self) -> None:
        calls: list[str] = []

        def get_dependencies(package: Package) -> list[Package]:
            calls.append(package.name)
            return self.repository.package_dependencies(package)

        build_dependency_graph(self.root, get_dependencies)
        self.assertEqual(sorted(calls), ["A", "B", "C", "D", "E"])

    def test_cycle_is_detected(self) -> None:
        graph = build_dependency_graph(
            self.root, self.repository.package_dependencies
        )
        self.assertTrue(has_cycle(graph))

    def test_acyclic_graph_is_not_reported_as_cycle(self) -> None:
        simple = TestRepository.load(DATA / "simple.json")
        graph = build_dependency_graph(
            Package("A", "1.0.0"), simple.package_dependencies
        )
        self.assertFalse(has_cycle(graph))

    def test_filter_removes_matching_nodes_and_edges(self) -> None:
        graph = build_dependency_graph(
            self.root, self.repository.package_dependencies, "D"
        )
        names = {package.name for package in graph}
        self.assertNotIn("D", names)
        for dependencies in graph.values():
            self.assertNotIn("D", {item.name for item in dependencies})

    def test_filter_can_leave_a_node_without_dependencies(self) -> None:
        repository = TestRepository.load(DATA / "branching.json")
        graph = build_dependency_graph(
            self.root, repository.package_dependencies, "D"
        )
        package_b = Package("B", "1.0.0")
        self.assertEqual(graph[package_b], [])

    def test_filter_cannot_remove_root_package(self) -> None:
        with self.assertRaises(GraphError):
            build_dependency_graph(
                self.root, self.repository.package_dependencies, "A"
            )


if __name__ == "__main__":
    unittest.main()
