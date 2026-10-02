"""Catalog data types: releases with dependencies and platform test status.

The catalog handed to ``resolve`` is a snapshot of published, unwithdrawn
versions; it is treated as immutable for the duration of one resolution.
"""

from __future__ import annotations

from .constraint import Constraint
from .version import Version

__all__ = ["PASSED", "FAILED", "UNTESTED", "Dependency", "Release", "Catalog"]

PASSED = "passed"
FAILED = "failed"
UNTESTED = "untested"


class Dependency:
    """A direct dependency: component name plus version constraint."""

    __slots__ = ("name", "constraint")

    def __init__(self, name: str, constraint: Constraint) -> None:
        self.name = name
        self.constraint = constraint

    def __repr__(self) -> str:
        return f"Dependency({self.name!r}, {self.constraint!r})"


class Release:
    """One published, unwithdrawn snapshot of a component version.

    ``platform_status`` maps platform name to PASSED / FAILED / UNTESTED;
    a platform missing from the mapping counts as untested.
    """

    __slots__ = ("name", "version", "dependencies", "platform_status")

    def __init__(self, name: str, version: Version,
                 dependencies: tuple[Dependency, ...] = (),
                 platform_status: dict[str, str] | None = None) -> None:
        self.name = name
        self.version = version
        self.dependencies = tuple(dependencies)
        self.platform_status = dict(platform_status or {})

    def __repr__(self) -> str:
        return f"Release({self.name!r}, {self.version!s})"

    def usable_on(self, targets: frozenset[str]) -> bool:
        """True iff status is PASSED on every target platform."""
        return all(self.platform_status.get(platform) == PASSED
                   for platform in targets)


class Catalog:
    """All known releases, grouped by component name."""

    def __init__(self, releases: tuple[Release, ...] = ()) -> None:
        by_name: dict[str, list[Release]] = {}
        for release in releases:
            by_name.setdefault(release.name, []).append(release)
        for group in by_name.values():
            group.sort(key=lambda release: release.version)
        self._by_name = {
            name: tuple(group) for name, group in by_name.items()
        }

    def releases_of(self, name: str) -> tuple[Release, ...]:
        """Releases of ``name``, sorted by ascending version."""
        return self._by_name.get(name, ())

    def names(self) -> tuple[str, ...]:
        return tuple(self._by_name)
