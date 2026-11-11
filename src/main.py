"""Command-line entry point."""

import argparse
import sys

from src.config import Config, ConfigurationError, validate_config


def build_parser() -> argparse.ArgumentParser:
    """Create the command-line parser and declare all user options."""
    parser = argparse.ArgumentParser(
        description="Build and visualize a Cargo package dependency graph."
    )
    parser.add_argument("--package", required=True, help="Package name.")
    parser.add_argument(
        "--repo", required=True, help="Registry URL or JSON file."
    )
    parser.add_argument(
        "--test-mode", action="store_true", help="Read a test JSON."
    )
    parser.add_argument(
        "--version", required=True, help="Exact root package version."
    )
    parser.add_argument(
        "--output", default="dependency-graph.png", help="PNG output path."
    )
    parser.add_argument(
        "--filter", default=None, help="Ignore names containing text."
    )
    parser.add_argument(
        "--reverse", action="store_true", help="Show reverse dependencies."
    )
    return parser


def print_config(config: Config) -> None:
    """Print the six configurable task parameters as key-value pairs."""
    values = (
        ("package", config.package),
        ("repository", config.repository),
        ("test_mode", config.test_mode),
        ("version", config.version),
        ("output", str(config.output)),
        ("filter", config.filter_substring),
    )
    for key, value in values:
        print(f"{key} = {value}")


def main(argv: list[str] | None = None) -> int:
    """Parse options, validate them and display the initial configuration."""
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = validate_config(args)
    except ConfigurationError as error:
        parser.error(str(error))
    print_config(config)
    return 0


if __name__ == "__main__":
    sys.exit(main())
