"""Tests for Cargo semantic-version requirement matching."""

import unittest

from src.semver import matches_requirement, parse_version


class SemVerTests(unittest.TestCase):
    """Check ordering and common Cargo requirement forms."""

    def test_stable_version_is_newer_than_prerelease(self) -> None:
        self.assertGreater(
            parse_version("1.0.0"), parse_version("1.0.0-rc.1")
        )

    def test_caret_requirement(self) -> None:
        self.assertTrue(matches_requirement("1.9.0", "^1.2.3"))
        self.assertFalse(matches_requirement("2.0.0", "^1.2.3"))

    def test_caret_zero_major_requirement(self) -> None:
        self.assertTrue(matches_requirement("0.2.9", "0.2.3"))
        self.assertFalse(matches_requirement("0.3.0", "0.2.3"))

    def test_caret_zero_minor_requirement(self) -> None:
        self.assertTrue(matches_requirement("0.0.3", "0.0.3"))
        self.assertFalse(matches_requirement("0.0.4", "0.0.3"))

    def test_tilde_requirement(self) -> None:
        self.assertTrue(matches_requirement("1.2.9", "~1.2.3"))
        self.assertFalse(matches_requirement("1.3.0", "~1.2.3"))

    def test_wildcard_requirement(self) -> None:
        self.assertTrue(matches_requirement("1.2.9", "1.2.*"))
        self.assertFalse(matches_requirement("1.3.0", "1.2.*"))

    def test_comparison_requirements(self) -> None:
        self.assertTrue(
            matches_requirement("1.4.0", ">=1.2.0, <2.0.0")
        )
        self.assertFalse(
            matches_requirement("2.0.0", ">=1.2.0, <2.0.0")
        )

    def test_prerelease_requires_explicit_line(self) -> None:
        self.assertFalse(matches_requirement("1.0.0-alpha", "^1.0.0"))
        self.assertTrue(
            matches_requirement("1.0.0-beta", "^1.0.0-alpha")
        )

    def test_invalid_requirement_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            matches_requirement("1.0.0", "not-a-version")


if __name__ == "__main__":
    unittest.main()
