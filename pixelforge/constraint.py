"""Version constraints: exact versions or unions of [lo, hi) intervals."""

from __future__ import annotations

from .version import Version

__all__ = ["Interval", "Constraint"]


class Interval:
    """Left-closed interval [lo, hi); either endpoint may be unbounded (None).

    ``hi_inclusive`` is only meaningful for exact points, where lo == hi and
    the single version itself is included.
    """

    __slots__ = ("lo", "hi", "hi_inclusive")

    def __init__(self, lo: Version | None, hi: Version | None,
                 hi_inclusive: bool = False) -> None:
        self.lo = lo
        self.hi = hi
        self.hi_inclusive = hi_inclusive

    @classmethod
    def exact(cls, version: Version) -> "Interval":
        return cls(version, version, hi_inclusive=True)

    def __repr__(self) -> str:
        if self.hi_inclusive and self.lo == self.hi:
            return f"Interval(exact={self.lo})"
        return f"Interval(lo={self.lo}, hi={self.hi})"

    def is_empty(self) -> bool:
        if self.lo is None or self.hi is None:
            return False
        if self.lo > self.hi:
            return True
        return self.lo == self.hi and not self.hi_inclusive

    def contains(self, version: Version) -> bool:
        if self.lo is not None and version < self.lo:
            return False
        if self.hi is not None:
            if version > self.hi:
                return False
            if version == self.hi and not self.hi_inclusive:
                return False
        return True

    def intersect(self, other: "Interval") -> "Interval | None":
        if self.lo is None:
            lo = other.lo
        elif other.lo is None:
            lo = self.lo
        else:
            lo = max(self.lo, other.lo)
        if self.hi is None:
            hi, hi_inc = other.hi, other.hi_inclusive
        elif other.hi is None:
            hi, hi_inc = self.hi, self.hi_inclusive
        elif self.hi < other.hi:
            hi, hi_inc = self.hi, self.hi_inclusive
        elif other.hi < self.hi:
            hi, hi_inc = other.hi, other.hi_inclusive
        else:
            hi, hi_inc = self.hi, self.hi_inclusive and other.hi_inclusive
        result = Interval(lo, hi, hi_inc)
        return None if result.is_empty() else result


class Constraint:
    """A union of intervals, kept sorted and free of empty parts."""

    __slots__ = ("intervals",)

    def __init__(self, intervals: tuple[Interval, ...] = ()) -> None:
        kept = [iv for iv in intervals if not iv.is_empty()]
        kept.sort(key=lambda iv: (iv.lo is not None, iv.lo))
        self.intervals = tuple(kept)

    def __repr__(self) -> str:
        return f"Constraint({self.intervals!r})"

    @classmethod
    def any(cls) -> "Constraint":
        return cls((Interval(None, None),))

    @classmethod
    def exact(cls, version: Version) -> "Constraint":
        return cls((Interval.exact(version),))

    @classmethod
    def range(cls, lo: Version | None, hi: Version | None) -> "Constraint":
        return cls((Interval(lo, hi),))

    def is_empty(self) -> bool:
        return not self.intervals

    def contains(self, version: Version) -> bool:
        return any(iv.contains(version) for iv in self.intervals)

    def intersect(self, other: "Constraint") -> "Constraint":
        parts = []
        for left in self.intervals:
            for right in other.intervals:
                merged = left.intersect(right)
                if merged is not None:
                    parts.append(merged)
        return Constraint(tuple(parts))
