"""Нерекурсивный обход графа зависимостей поиском в ширину (BFS)."""

from collections import deque
from collections.abc import Callable, Iterable

from src.models import Package


DependencyGraph = dict[Package, list[Package]]
DependencyGetter = Callable[[Package], Iterable[Package]]


class GraphError(ValueError):
    """Возникает, если невозможно построить запрошенный граф."""


def build_dependency_graph(
    root: Package,
    get_dependencies: DependencyGetter,
    filter_substring: str | None = None,
) -> DependencyGraph:
    """Строит достижимую часть графа итеративным алгоритмом BFS."""
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
    """Запрещает фильтр, исключающий выбранный для анализа пакет."""
    if filter_substring and filter_substring in root.name:
        raise GraphError("The filter excludes the selected root package.")


def _filtered_dependencies(
    dependencies: Iterable[Package], filter_substring: str | None
) -> list[Package]:
    """Удаляет исключённые имена и повторные рёбра, затем сортирует их."""
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
    """Добавляет пакет в очередь один раз, сохраняя все рёбра графа."""
    for dependency in dependencies:
        graph.setdefault(dependency, [])
        if dependency not in visited:
            visited.add(dependency)
            queue.append(dependency)


def has_cycle(graph: DependencyGraph) -> bool:
    """Находит ориентированный цикл алгоритмом Кана с очередью."""
    indegree = {package: 0 for package in graph}
    for dependencies in graph.values():
        for dependency in dependencies:
            indegree[dependency] += 1
    queue = deque(
        package for package, degree in indegree.items() if not degree
    )
    processed = 0
    while queue:
        current = queue.popleft()
        processed += 1
        for dependency in graph[current]:
            indegree[dependency] -= 1
            if not indegree[dependency]:
                queue.append(dependency)
    return processed != len(graph)


def graph_counts(graph: DependencyGraph) -> tuple[int, int]:
    """Возвращает число уникальных вершин и ориентированных рёбер."""
    return len(graph), sum(len(items) for items in graph.values())


def format_graph(graph: DependencyGraph) -> str:
    """Форматирует вершины и исходящие рёбра для вывода в консоль."""
    lines = []
    for package in sorted(graph):
        lines.append(f"{package.label}:")
        dependencies = graph[package]
        if not dependencies:
            lines.append("  (no dependencies)")
        for dependency in dependencies:
            lines.append(f"  -> {dependency.label}")
    return "\n".join(lines)
