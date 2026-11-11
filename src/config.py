"""Command-line configuration and input validation."""

from dataclasses import dataclass
from pathlib import Path
import re
from urllib.parse import urlparse

from src.semver import parse_version
PACKAGE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
TEST_PACKAGE_PATTERN = re.compile(r"^[A-Z]+$")


class ConfigurationError(ValueError):
    """Raised when a command-line option has an invalid value."""


@dataclass(frozen=True)
class Config:
    """Validated settings supplied by the user."""

    package: str
    repository: str
    test_mode: bool
    version: str
    output: Path
    filter_substring: str | None
    reverse: bool = False


def validate_config(args: object) -> Config:
    """Validate parsed arguments and return an immutable configuration."""
    package = _validate_package(args.package, args.test_mode)
    repository = _validate_repository(args.repo, args.test_mode)
    version = _validate_version(args.version)
    output = _validate_output(args.output)
    filter_text = _validate_filter(args.filter)
    return Config(
        package=package,
        repository=repository,
        test_mode=args.test_mode,
        version=version,
        output=output,
        filter_substring=filter_text,
        reverse=getattr(args, "reverse", False),
    )


def _validate_package(value: str, test_mode: bool) -> str:
    """Validate a package name for the selected repository mode."""
    if not value or not PACKAGE_PATTERN.fullmatch(value):
        message = "package must contain letters, digits, '-' or '_'."
        raise ConfigurationError(message)
    if test_mode and not TEST_PACKAGE_PATTERN.fullmatch(value):
        raise ConfigurationError(
            "test packages must use uppercase Latin letters only."
        )
    return value


def _validate_repository(value: str, test_mode: bool) -> str:
    """Validate a local test file or an HTTPS registry URL."""
    if not value or not value.strip():
        raise ConfigurationError("repo must not be empty.")
    if test_mode:
        path = Path(value).expanduser()
        if path.suffix.lower() != ".json":
            raise ConfigurationError("test repository must be a .json file.")
        if not path.is_file():
            raise ConfigurationError(f"test repository not found: {path}")
        return str(path.resolve())
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ConfigurationError("repo must be a valid HTTPS registry URL.")
    if parsed.query or parsed.fragment or parsed.username:
        message = "repo URL must not contain credentials or query."
        raise ConfigurationError(message)
    path = parsed.path.rstrip("/")
    if path not in ("", "/api/v1"):
        raise ConfigurationError("repo URL must point to the registry root.")
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _validate_version(value: str) -> str:
    """Require an exact semantic version for the selected root package."""
    try:
        parse_version(value)
    except ValueError as error:
        message = "version must be an exact semantic version, e.g. 1.2.3."
        raise ConfigurationError(message) from error
    return value


def _validate_output(value: str) -> Path:
    """Require a PNG output path with a usable parent directory."""
    if not value or not value.strip():
        raise ConfigurationError("output must not be empty.")
    path = Path(value).expanduser()
    if path.suffix.lower() != ".png":
        raise ConfigurationError("output file must have the .png extension.")
    if path.exists() and path.is_dir():
        raise ConfigurationError("output path points to a directory.")
    if path.parent.exists() and not path.parent.is_dir():
        raise ConfigurationError("output parent path is not a directory.")
    return path


def _validate_filter(value: str | None) -> str | None:
    """Reject an explicitly empty filter while allowing no filter."""
    if value is not None and not value.strip():
        raise ConfigurationError("filter must not be empty when provided.")
    return value
