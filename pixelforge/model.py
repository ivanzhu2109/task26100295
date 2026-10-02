"""Data model: catalog, releases, root requests, and resolution results."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple

from .constraints import VersionSet
from .version import Version

#: Platform test status values.
PASSED = "passed"
FAILED = "failed"
UNTESTED = "untested"


@dataclass(frozen=True)
class Dependency:
    """A direct dependency edge of a release."""

    name: str
    constraint: VersionSet


@dataclass(frozen=True)
class Release:
    """One published version of a component (an immutable snapshot entry)."""

    name: str
    version: Version
    dependencies: Tuple[Dependency, ...] = ()
    #: platforms on which this release passed testing; any platform not
    #: listed (or failed/untested at the source) makes it unusable.
    passed_platforms: FrozenSet = frozenset()


@dataclass
class Catalog:
    """A snapshot of published releases: name -> version -> Release."""

    releases: Dict[str, Dict[Version, Release]] = field(default_factory=dict)

    def add(self, release: Release) -> None:
        self.releases.setdefault(release.name, {})[release.version] = release

    def get(self, name: str, version: Version) -> Optional[Release]:
        return self.releases.get(name, {}).get(version)

    def versions(self, name: str) -> List[Version]:
        return sorted(self.releases.get(name, ()))


@dataclass(frozen=True)
class RootRequest:
    """One root request. Duplicate names are allowed and are
    distinguished by position in the roots list."""

    name: str
    constraint: VersionSet


@dataclass(frozen=True)
class Solution:
    """A flat set of selected releases: name -> version."""

    selections: Tuple[Tuple[str, Version], ...]


@dataclass(frozen=True)
class Conflict:
    """An irreducible subset of root request positions that is itself
    unsatisfiable, and becomes satisfiable when any one item is removed."""

    root_indices: Tuple[int, ...]
