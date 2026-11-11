"""Небольшой обработчик требований Cargo к семантическим версиям."""

from dataclasses import dataclass
from functools import total_ordering
import re


ZERO_COMPONENT = 0
SINGLE_COMPONENT = 1
TWO_COMPONENTS = 2
SINGLE_DIGIT_LENGTH = 1


VERSION_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$"
)
PARTIAL_RE = re.compile(
    r"^(0|[1-9]\d*)"
    r"(?:\.(0|[1-9]\d*|[xX*]))?"
    r"(?:\.(0|[1-9]\d*|[xX*]))?"
    r"(?:-([0-9A-Za-z.-]+))?$"
)


@total_ordering
@dataclass(frozen=True)
class SemVer:
    """Разобранная семантическая версия без метаданных сборки."""

    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()

    def __lt__(self, other: object) -> bool:
        """Сравнивает семантические версии."""
        if not isinstance(other, SemVer):
            return NotImplemented
        left = (self.major, self.minor, self.patch)
        right = (other.major, other.minor, other.patch)
        if left != right:
            return left < right
        return _prerelease_less(self.prerelease, other.prerelease)


def parse_version(value: str) -> SemVer:
    """Разбирает точную семантическую версию из трёх компонентов."""
    match = VERSION_RE.fullmatch(value)
    if match is None:
        raise ValueError(f"Invalid semantic version: {value}")
    prerelease = tuple((match.group(4) or "").split("."))
    if prerelease == ("",):
        prerelease = ()
    _validate_prerelease(prerelease)
    return SemVer(
        int(match.group(1)), int(match.group(2)), int(match.group(3)),
        prerelease,
    )


def matches_requirement(version: str, requirement: str) -> bool:
    """Проверяет соответствие точной версии требованию Cargo."""
    candidate = parse_version(version)
    pieces = [part.strip() for part in requirement.split(",")]
    if not pieces or any(not part for part in pieces):
        raise ValueError(f"Invalid Cargo version requirement: {requirement}")
    if candidate.prerelease and not _allows_prerelease(candidate, pieces):
        return False
    return all(_matches_piece(candidate, piece) for piece in pieces)


def _prerelease_less(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    """Сравнивает идентификаторы предварительных версий по SemVer 2.0."""
    if not left or not right:
        return bool(left) and not right
    for first, second in zip(left, right):
        if first == second:
            continue
        first_num = first.isdigit()
        second_num = second.isdigit()
        if first_num and second_num:
            return int(first) < int(second)
        if first_num != second_num:
            return first_num
        return first < second
    return len(left) < len(right)


def _validate_prerelease(parts: tuple[str, ...]) -> None:
    """Отклоняет пустые и дополненные нулями числовые идентификаторы."""
    for part in parts:
        if not part:
            raise ValueError("Empty prerelease identifier.")
        has_leading_zero = (
            part.isdigit()
            and len(part) > SINGLE_DIGIT_LENGTH
            and part.startswith("0")
        )
        if has_leading_zero:
            raise ValueError(
                "Numeric prerelease identifiers cannot have zeros."
            )


def _parse_partial(value: str) -> tuple[tuple[int, ...], tuple[str, ...]]:
    """Разбирает версии из одного, двух или трёх компонентов."""
    value = value.split("+", 1)[0]
    match = PARTIAL_RE.fullmatch(value)
    if match is None:
        raise ValueError(f"Unsupported Cargo version requirement: {value}")
    raw_parts = match.group(1, 2, 3)
    numeric = tuple(int(part) for part in raw_parts if part is not None)
    prerelease = tuple((match.group(4) or "").split("."))
    if prerelease == ("",):
        prerelease = ()
    _validate_prerelease(prerelease)
    return numeric, prerelease


def _matches_piece(candidate: SemVer, piece: str) -> bool:
    """Проверяет одну часть требования Cargo, разделённого запятыми."""
    match = re.match(r"^(>=|<=|>|<|=|\^|~)?\s*(.+)$", piece)
    if match is None:
        raise ValueError(f"Invalid Cargo requirement piece: {piece}")
    operator = match.group(1) or "^"
    value = match.group(2).strip()
    components = value.split(".")
    has_wildcard = any(
        part.lower() in ("x", "*") for part in components
    )
    if has_wildcard:
        return _matches_wildcard(candidate, operator, value)
    parts, prerelease = _parse_partial(value)
    bound = _make_bound(parts, prerelease)
    return _compare_requirement(candidate, operator, bound, parts)


def _make_bound(parts: tuple[int, ...], pre: tuple[str, ...]) -> SemVer:
    """Заполняет отсутствующие компоненты minor и patch нулями."""
    numbers = (*parts, 0, 0)
    return SemVer(numbers[0], numbers[1], numbers[2], pre)


def _compare_requirement(
    candidate: SemVer,
    operator: str,
    bound: SemVer,
    parts: tuple[int, ...],
) -> bool:
    """Применяет правила сравнения, caret или tilde к границе версии."""
    if operator == ">=":
        return candidate >= bound
    if operator == ">":
        return candidate > bound
    if operator == "<=":
        return candidate <= bound
    if operator == "<":
        return candidate < bound
    if operator == "=":
        return _matches_partial_exact(candidate, bound, len(parts))
    upper = _upper_bound(parts, operator)
    return candidate >= bound and candidate < upper


def _matches_partial_exact(
    candidate: SemVer, bound: SemVer, precision: int
) -> bool:
    """Сопоставляет точные версии с учётом числа заданных компонентов."""
    actual = (candidate.major, candidate.minor, candidate.patch)
    expected = (bound.major, bound.minor, bound.patch)
    return actual[:precision] == expected[:precision]


def _upper_bound(parts: tuple[int, ...], operator: str) -> SemVer:
    """Вычисляет исключающую верхнюю границу диапазона caret или tilde."""
    bound = _make_bound(parts, ())
    major, minor, patch = bound.major, bound.minor, bound.patch
    if operator == "~":
        if len(parts) == SINGLE_COMPONENT:
            return SemVer(major + 1, 0, 0)
        return SemVer(major, minor + 1, 0)
    if major > ZERO_COMPONENT or len(parts) == SINGLE_COMPONENT:
        return SemVer(major + 1, 0, 0)
    if minor > ZERO_COMPONENT or len(parts) == TWO_COMPONENTS:
        return SemVer(0, minor + 1, 0)
    return SemVer(0, 0, patch + 1)


def _matches_wildcard(
    candidate: SemVer, operator: str, value: str
) -> bool:
    """Обрабатывает диапазоны с подстановкой, например 1.* и 1.2.*."""
    if operator not in ("^", "="):
        raise ValueError("Wildcard ranges cannot use comparison operators.")
    parts = value.split(".")
    wildcard_at = next(
        (index for index, part in enumerate(parts)
         if part.lower() in ("x", "*")),
        len(parts),
    )
    if any(
        part.lower() not in ("x", "*")
        for part in parts[wildcard_at:]
    ):
        raise ValueError("Wildcard must be the final version component.")
    if wildcard_at == ZERO_COMPONENT:
        return True
    numbers = tuple(int(part) for part in parts[:wildcard_at])
    lower = _make_bound(numbers, ())
    upper = _wildcard_upper(numbers)
    return candidate >= lower and candidate < upper


def _wildcard_upper(parts: tuple[int, ...]) -> SemVer:
    """Возвращает следующую границу major или minor для диапазона с *."""
    if len(parts) == SINGLE_COMPONENT:
        return SemVer(parts[0] + 1, 0, 0)
    return SemVer(parts[0], parts[1] + 1, 0)


def _allows_prerelease(
    candidate: SemVer, pieces: list[str]
) -> bool:
    """Допускает prerelease только при явном указании этой линии версий."""
    core = (candidate.major, candidate.minor, candidate.patch)
    for piece in pieces:
        match = re.search(r"(\d+)\.(\d+)\.(\d+)-", piece)
        if match and tuple(map(int, match.groups())) == core:
            return True
    return False
