"""SemVer 2.0.0 version parsing and ordering (no build metadata)."""

from __future__ import annotations

import re
from typing import Tuple, Union

_CORE = r"(0|[1-9]\d*)"
_IDENT = r"(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
_PATTERN = re.compile(
    r"^" + _CORE + r"\." + _CORE + r"\." + _CORE +
    r"(?:-(" + _IDENT + r"(?:\." + _IDENT + r")*))?$"
)

#: One pre-release identifier: either a non-negative int or an ASCII string.
PreReleaseId = Union[int, str]


def _parse_identifier(text: str) -> PreReleaseId:
    if text.isdigit():
        return int(text)
    return text


def _compare_prerelease(left: Tuple[PreReleaseId, ...],
                        right: Tuple[PreReleaseId, ...]) -> int:
    # A version without pre-release has higher precedence than one with.
    if not left and not right:
        return 0
    if not left:
        return 1
    if not right:
        return -1
    for a, b in zip(left, right):
        if a == b:
            continue
        # Numeric identifiers compare lower than alphanumeric ones.
        if isinstance(a, int) and isinstance(b, int):
            return -1 if a < b else 1
        if isinstance(a, int):
            return -1
        if isinstance(b, int):
            return 1
        return -1 if a < b else 1
    # The smaller set of identifiers has lower precedence.
    if len(left) == len(right):
        return 0
    return -1 if len(left) < len(right) else 1


class Version:
    """A SemVer 2.0.0 version without build metadata.

    Supports pre-release identifiers with standard precedence rules.
    """

    __slots__ = ("major", "minor", "patch", "prerelease")

    def __init__(self, major: int, minor: int, patch: int,
                 prerelease: Tuple[PreReleaseId, ...] = ()) -> None:
        self.major = major
        self.minor = minor
        self.patch = patch
        self.prerelease = tuple(prerelease)

    @classmethod
    def parse(cls, text: str) -> "Version":
        match = _PATTERN.match(text)
        if match is None:
            raise ValueError(f"invalid SemVer version: {text!r}")
        prerelease: Tuple[PreReleaseId, ...] = ()
        if match.group(4) is not None:
            prerelease = tuple(
                _parse_identifier(part)
                for part in match.group(4).split(".")
            )
        return cls(int(match.group(1)), int(match.group(2)),
                   int(match.group(3)), prerelease)

    def _key(self) -> Tuple[int, int, int, Tuple[PreReleaseId, ...]]:
        return (self.major, self.minor, self.patch, self.prerelease)

    def _compare(self, other: "Version") -> int:
        if not isinstance(other, Version):
            return NotImplemented
        core_a = (self.major, self.minor, self.patch)
        core_b = (other.major, other.minor, other.patch)
        if core_a != core_b:
            return -1 if core_a < core_b else 1
        return _compare_prerelease(self.prerelease, other.prerelease)

    def __str__(self) -> str:
        text = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            text += "-" + ".".join(str(p) for p in self.prerelease)
        return text

    def __repr__(self) -> str:
        return f"Version({str(self)!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._key() == other._key()

    def __hash__(self) -> int:
        return hash(self._key())

    def __lt__(self, other: "Version") -> bool:
        return self._compare(other) < 0

    def __le__(self, other: "Version") -> bool:
        return self._compare(other) <= 0

    def __gt__(self, other: "Version") -> bool:
        return self._compare(other) > 0

    def __ge__(self, other: "Version") -> bool:
        return self._compare(other) >= 0
