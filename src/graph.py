"""Non-recursive breadth-first traversal of package dependency graphs."""

from collections import deque
from collections.abc import Callable, Iterable

from src.models import Package


DependencyGraph = dict[Package, list[Package]]
DependencyGetter = Callable[[Package], Iterable[Package]]


class GraphError(ValueError):
    """Raised when the requested graph cannot be constructed."""


def build_dependency_graph(
    root: Package,
    get_dependencies: DependencyGetter,
    filter_substring: str | None = None,
) -> DependencyGraph:
    """Build all reachable edges with iterative breadth-first search."""
    _validate_root_filter(root, filter_substring)
    graph: DependencyGraph = {}
    visited = {root}
    queue = deque([root])
    while queue:
        current = queue.popleft()
        dependencies = _filtered_dependencies(
            get_dependencies(current), filter_substring
        )
        graph[current] = dependencies
        _enqueue_new_nodes(dependencies, visited, queue, graph)
    return graph


def _validate_root_filter(
    root: Package, filter_substring: str | None
) -> None:
    """Reject a filter that removes the package selected for analysis."""
    if filter_substring and filter_substring in root.name:
        raise GraphError("The filter excludes the selected root package.")


def _filtered_dependencies(
    dependencies: Iterable[Package], filter_substring: str | None
) -> list[Package]:
    """Remove ignored names and duplicate edges, then sort deterministically."""
    unique = set(dependencies)
    if filter_substring:
        unique = {
            item for item in unique if filter_substring not in item.name
        }
    return sorted(unique)


def _enqueue_new_nodes(
    dependencies: list[Package],
    visited: set[Package],
    queue: deque[Package],
    graph: DependencyGraph,
) -> None:
    """Queue each new package once while retaining every graph edge."""
    for dependency in dependencies:
        graph.setdefault(dependency, [])
        if dependency not in visited:
            visited.add(dependency)
            queue.append(dependency)


def has_cycle(graph: DependencyGraph) -> bool:
    """Detect a directed cycle using Kahn's queue-based algorithm."""
    indegree = {package: 0 for package in graph}
    for dependencies in graph.values():
        for dependency in dependencies:
            indegree[dependency] += 1
    queue = deque(
        package for package, degree in indegree.items() if degree == 0
    )
    processed = 0
    while queue:
        current = queue.popleft()
        processed += 1
        for dependency in graph[current]:
            indegree[dependency] -= 1
            if indegree[dependency] == 0:
                queue.append(dependency)
    return processed != len(graph)


def graph_counts(graph: DependencyGraph) -> tuple[int, int]:
    """Return the number of unique package nodes and directed edges."""
    return len(graph), sum(len(items) for items in graph.values())


def format_graph(graph: DependencyGraph) -> str:
    """Format every node and its direct outgoing edges for the console."""
    lines = []
    for package in sorted(graph):
        lines.append(f"{package.label}:")
        dependencies = graph[package]
        if not dependencies:
            lines.append("  (no dependencies)")
        for dependency in dependencies:
            lines.append(f"  -> {dependency.label}")
    return "\n".join(lines)
