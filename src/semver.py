"""A small Cargo-compatible semantic-version requirement evaluator."""

from dataclasses import dataclass
from functools import total_ordering
import re


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
    """A parsed semantic version without build metadata."""

    major: int
    minor: int
    patch: int
    prerelease: tuple[str, ...] = ()

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        left = (self.major, self.minor, self.patch)
        right = (other.major, other.minor, other.patch)
        if left != right:
            return left < right
        return _prerelease_less(self.prerelease, other.prerelease)


def parse_version(value: str) -> SemVer:
    """Parse an exact three-component semantic version."""
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
    """Return whether an exact version satisfies a Cargo requirement."""
    candidate = parse_version(version)
    pieces = [part.strip() for part in requirement.split(",")]
    if not pieces or any(not part for part in pieces):
        raise ValueError(f"Invalid Cargo version requirement: {requirement}")
    if candidate.prerelease and not _allows_prerelease(candidate, pieces):
        return False
    return all(_matches_piece(candidate, piece) for piece in pieces)


def _prerelease_less(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    """Compare SemVer prerelease identifiers according to SemVer 2.0."""
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
    """Reject empty or zero-padded numeric prerelease identifiers."""
    for part in parts:
        if not part:
            raise ValueError("Empty prerelease identifier.")
        if part.isdigit() and len(part) > 1 and part.startswith("0"):
            raise ValueError(
                "Numeric prerelease identifiers cannot have zeros."
            )


def _parse_partial(value: str) -> tuple[tuple[int, ...], tuple[str, ...]]:
    """Parse one-, two- or three-component versions used in ranges."""
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
    """Evaluate a single comma-separated Cargo requirement piece."""
    match = re.match(r"^(>=|<=|>|<|=|\^|~)?\s*(.+)$", piece)
    if match is None:
        raise ValueError(f"Invalid Cargo requirement piece: {piece}")
    operator = match.group(1) or "^"
    value = match.group(2).strip()
    if "*" in value or "x" in value.lower():
        return _matches_wildcard(candidate, operator, value)
    parts, prerelease = _parse_partial(value)
    bound = _make_bound(parts, prerelease)
    return _compare_requirement(candidate, operator, bound, parts)


def _make_bound(parts: tuple[int, ...], pre: tuple[str, ...]) -> SemVer:
    """Fill omitted minor and patch components with zeroes."""
    numbers = (*parts, 0, 0)
    return SemVer(numbers[0], numbers[1], numbers[2], pre)


def _compare_requirement(
    candidate: SemVer,
    operator: str,
    bound: SemVer,
    parts: tuple[int, ...],
) -> bool:
    """Apply comparison, caret or tilde semantics to a parsed bound."""
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
    """Match exact comparators with the specified component precision."""
    actual = (candidate.major, candidate.minor, candidate.patch)
    expected = (bound.major, bound.minor, bound.patch)
    return actual[:precision] == expected[:precision]


def _upper_bound(parts: tuple[int, ...], operator: str) -> SemVer:
    """Calculate the exclusive upper bound of caret or tilde ranges."""
    bound = _make_bound(parts, ())
    major, minor, patch = bound.major, bound.minor, bound.patch
    if operator == "~":
        return SemVer(major + 1, 0, 0) if len(parts) == 1 else SemVer(
            major, minor + 1, 0
        )
    if major > 0 or len(parts) == 1:
        return SemVer(major + 1, 0, 0)
    if minor > 0 or len(parts) == 2:
        return SemVer(0, minor + 1, 0)
    return SemVer(0, 0, patch + 1)


def _matches_wildcard(
    candidate: SemVer, operator: str, value: str
) -> bool:
    """Handle wildcard ranges such as 1.* and 1.2.*."""
    if operator not in ("^", "="):
        raise ValueError("Wildcard ranges cannot use comparison operators.")
    parts = value.split(".")
    wildcard_at = next(
        (index for index, part in enumerate(parts)
         if part.lower() in ("x", "*")),
        len(parts),
    )
    if wildcard_at == 0:
        return True
    numbers = tuple(int(part) for part in parts[:wildcard_at])
    lower = _make_bound(numbers, ())
    upper = _wildcard_upper(numbers)
    return candidate >= lower and candidate < upper


def _wildcard_upper(parts: tuple[int, ...]) -> SemVer:
    """Return the next major or minor boundary for a wildcard range."""
    if len(parts) == 1:
        return SemVer(parts[0] + 1, 0, 0)
    return SemVer(parts[0], parts[1] + 1, 0)


def _allows_prerelease(
    candidate: SemVer, pieces: list[str]
) -> bool:
    """Allow prereleases only when a requirement names that release line."""
    core = (candidate.major, candidate.minor, candidate.patch)
    for piece in pieces:
        match = re.search(r"(\d+)\.(\d+)\.(\d+)-", piece)
        if match and tuple(map(int, match.groups())) == core:
            return True
    return False
