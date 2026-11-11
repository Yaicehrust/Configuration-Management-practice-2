"""Tests for crates.io API response parsing and dependency resolution."""

import unittest
from unittest.mock import Mock

from src.cargo_registry import CratesIoClient, RegistryError, _api_base
from src.models import Package


class CargoRegistryTests(unittest.TestCase):
    """Check registry URL construction and response conversion."""

    def test_api_base_from_registry_root(self) -> None:
        self.assertEqual(
            _api_base("https://crates.io"),
            "https://crates.io/api/v1/",
        )

    def test_api_base_from_api_root(self) -> None:
        self.assertEqual(
            _api_base("https://crates.io/api/v1"),
            "https://crates.io/api/v1/",
        )

    def test_selects_newest_compatible_release(self) -> None:
        client = CratesIoClient("https://crates.io")
        client._load_versions = Mock(return_value=[
            {"num": "2.0.0", "yanked": False},
            {"num": "1.9.0", "yanked": False},
            {"num": "1.8.0", "yanked": True},
        ])
        selected = client._select_version("demo", "^1.2.0")
        self.assertEqual(selected, "1.9.0")

    def test_resolves_direct_dependency_metadata(self) -> None:
        client = CratesIoClient("https://crates.io")
        client._request_json = Mock(return_value={
            "dependencies": [{
                "crate_id": "serde",
                "req": "^1.0",
                "kind": "normal",
                "optional": False,
                "target": None,
            }]
        })
        client._load_versions = Mock(return_value=[
            {"num": "1.0.5", "yanked": False},
            {"num": "2.0.0", "yanked": False},
        ])
        items = client.direct_dependencies(Package("demo", "1.0.0"))
        self.assertEqual(items[0].package, Package("serde", "1.0.5"))
        self.assertEqual(items[0].requirement, "^1.0")

    def test_reports_no_compatible_release(self) -> None:
        client = CratesIoClient("https://crates.io")
        client._load_versions = Mock(return_value=[])
        with self.assertRaises(RegistryError):
            client._select_version("demo", "^1.0")

    def test_maps_reverse_dependency_versions(self) -> None:
        result: dict[str, list[str]] = {}
        payload = {
            "dependencies": [
                {"version_id": 11},
                {"version_id": 12},
            ],
            "versions": [
                {"id": 11, "crate": "dependent", "num": "1.0.0"},
                {"id": 12, "crate": "dependent", "num": "1.2.0"},
            ],
        }
        CratesIoClient._collect_reverse_page(payload, result)
        self.assertEqual(result, {"dependent": ["1.0.0", "1.2.0"]})


if __name__ == "__main__":
    unittest.main()
