"""Tests for command-line configuration validation."""

import argparse
import tempfile
import unittest
from pathlib import Path

from src.config import ConfigurationError, validate_config


class ConfigTests(unittest.TestCase):
    """Check valid inputs and errors for every configurable field."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp_dir.name) / "repo.json"
        self.repo.write_text('{"A": []}', encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def make_args(self, **updates: object) -> argparse.Namespace:
        values = {
            "package": "A",
            "repo": str(self.repo),
            "test_mode": True,
            "version": "1.0.0",
            "output": "graph.png",
            "filter": None,
        }
        values.update(updates)
        return argparse.Namespace(**values)

    def test_valid_test_configuration(self) -> None:
        config = validate_config(self.make_args())
        self.assertEqual(config.package, "A")
        self.assertTrue(config.test_mode)
        self.assertEqual(config.version, "1.0.0")

    def test_rejects_invalid_test_package(self) -> None:
        with self.assertRaises(ConfigurationError):
            validate_config(self.make_args(package="alpha"))

    def test_rejects_missing_repository(self) -> None:
        with self.assertRaises(ConfigurationError):
            validate_config(self.make_args(repo="missing.json"))

    def test_rejects_empty_repository(self) -> None:
        with self.assertRaises(ConfigurationError):
            validate_config(self.make_args(repo=""))

    def test_rejects_invalid_version(self) -> None:
        with self.assertRaises(ConfigurationError):
            validate_config(self.make_args(version="latest"))

    def test_rejects_invalid_output_extension(self) -> None:
        with self.assertRaises(ConfigurationError):
            validate_config(self.make_args(output="graph.jpg"))

    def test_rejects_empty_filter(self) -> None:
        with self.assertRaises(ConfigurationError):
            validate_config(self.make_args(filter="   "))

    def test_real_repository_requires_https(self) -> None:
        with self.assertRaises(ConfigurationError):
            validate_config(
                self.make_args(test_mode=False, repo="http://crates.io")
            )


if __name__ == "__main__":
    unittest.main()
