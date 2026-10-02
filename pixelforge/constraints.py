"""Version constraint sets: unions of left-closed, right-open intervals."""

from __future__ import annotations

from typing import Optional, Tuple

from .version import Version

# An interval endpoint: None means unbounded.
Bound = Optional[Version]


class Interval:
    """A left-closed, right-open interval [lower, upper)."""

    __slots__ = ("lower", "upper")

    def __init__(self, lower: Bound, upper: Bound) -> None:
        self.lower = lower
        self.upper = upper

    def contains(self, version: Version) -> bool:
        if self.lower is not None and version < self.lower:
            return False
        if self.upper is not None and version >= self.upper:
            return False
        return True

    def is_empty(self) -> bool:
        return (self.lower is not None and self.upper is not None
                and self.lower >= self.upper)

    def __repr__(self) -> str:
        return f"Interval({self.lower}, {self.upper})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Interval):
            return NotImplemented
        return self.lower == other.lower and self.upper == other.upper

    def __hash__(self) -> int:
        return hash((self.lower, self.upper))


def _sort_key(interval: Interval) -> tuple:
    # None (unbounded lower) sorts before any concrete version.
    return (interval.lower is not None, interval.lower)


def _normalize(intervals) -> Tuple[Interval, ...]:
    """Sort and merge overlapping or adjacent intervals."""
    cleaned = [iv for iv in intervals if not iv.is_empty()]
    cleaned.sort(key=_sort_key)
    merged = []
    for iv in cleaned:
        if merged:
            last = merged[-1]
            # Overlap or adjacency: last.upper is None (unbounded) or
            # last.upper >= iv.lower.
            if last.upper is None or iv.lower is None or last.upper >= iv.lower:
                if last.upper is None or iv.upper is None:
                    upper = None
                else:
                    upper = max(last.upper, iv.upper)
                merged[-1] = Interval(last.lower, upper)
                continue
        merged.append(iv)
    return tuple(merged)


class VersionSet:
    """A finite union of disjoint, sorted Intervals."""

    __slots__ = ("intervals",)

    def __init__(self, intervals: Tuple[Interval, ...] = ()) -> None:
        self.intervals = tuple(intervals)

    @classmethod
    def any(cls) -> "VersionSet":
        return cls((Interval(None, None),))

    @classmethod
    def exact(cls, version: Version) -> "VersionSet":
        return cls((Interval(version, _next_version(version)),))

    @classmethod
    def range(cls, lower: Bound, upper: Bound) -> "VersionSet":
        return cls(_normalize([Interval(lower, upper)]))

    def contains(self, version: Version) -> bool:
        return any(iv.contains(version) for iv in self.intervals)

    def intersect(self, other: "VersionSet") -> "VersionSet":
        pieces = []
        for a in self.intervals:
            for b in other.intervals:
                lower = _max_bound(a.lower, b.lower)
                upper = _min_bound(a.upper, b.upper)
                pieces.append(Interval(lower, upper))
        return VersionSet(_normalize(pieces))

    def union(self, other: "VersionSet") -> "VersionSet":
        return VersionSet(_normalize(self.intervals + other.intervals))

    def is_empty(self) -> bool:
        return not self.intervals

    def __repr__(self) -> str:
        return f"VersionSet({self.intervals!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VersionSet):
            return NotImplemented
        return self.intervals == other.intervals

    def __hash__(self) -> int:
        return hash(self.intervals)


def _max_bound(a: Bound, b: Bound) -> Bound:
    if a is None:
        return b
    if b is None:
        return a
    return max(a, b)


def _min_bound(a: Bound, b: Bound) -> Bound:
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)


def _next_version(version: Version) -> Version:
    """Smallest version strictly greater than ``version``.

    For a version with a pre-release, appending the numeric identifier 0
    yields the immediate successor (0 is the smallest possible next
    identifier). For a plain release, the immediate successor is the
    ``-0`` pre-release of the next patch version: nothing sorts strictly
    between ``1.2.0`` and ``1.2.1-0``.
    """
    if not version.prerelease:
        return Version(version.major, version.minor, version.patch + 1, (0,))
    return Version(version.major, version.minor, version.patch,
                   version.prerelease + (0,))
