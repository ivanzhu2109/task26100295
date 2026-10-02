"""SemVer 2.0.0 versions (with prerelease, without build metadata)."""

from __future__ import annotations

import re

__all__ = ["Version"]

_CORE_RE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"
)
_IDENT_RE = re.compile(r"^[0-9A-Za-z-]+$")
_NUMERIC_RE = re.compile(r"^[0-9]+$")


class Version:
    """A SemVer 2.0.0 version: MAJOR.MINOR.PATCH with optional prerelease.

    Build metadata is not supported; prerelease identifiers follow the
    standard ordering (numeric < alphanumeric, numeric compared as integers,
    alphanumeric compared in ASCII order, shorter prefix < longer).
    """

    __slots__ = ("major", "minor", "patch", "prerelease")

    def __init__(self, major: int, minor: int, patch: int,
                 prerelease: tuple = ()) -> None:
        if major < 0 or minor < 0 or patch < 0:
            raise ValueError("version core numbers must be non-negative")
        for ident in prerelease:
            if not isinstance(ident, str) or not _IDENT_RE.match(ident):
                raise ValueError(f"invalid prerelease identifier: {ident!r}")
            if _NUMERIC_RE.match(ident) and len(ident) > 1 and ident[0] == "0":
                raise ValueError(
                    f"numeric prerelease identifier has leading zero: {ident!r}")
        self.major = major
        self.minor = minor
        self.patch = patch
        self.prerelease = tuple(prerelease)

    @classmethod
    def parse(cls, text: str) -> "Version":
        if "+" in text:
            raise ValueError(f"build metadata is not supported: {text!r}")
        core, sep, pre = text.partition("-")
        match = _CORE_RE.match(core)
        if match is None:
            raise ValueError(f"invalid version core: {text!r}")
        prerelease: tuple = ()
        if sep:
            if not pre:
                raise ValueError(f"empty prerelease: {text!r}")
            prerelease = tuple(pre.split("."))
        return cls(int(match.group(1)), int(match.group(2)),
                   int(match.group(3)), prerelease)

    def __str__(self) -> str:
        core = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            return core + "-" + ".".join(self.prerelease)
        return core

    def __repr__(self) -> str:
        return f"Version({str(self)!r})"

    def _key(self) -> tuple:
        return (self.major, self.minor, self.patch)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return (self._key() == other._key()
                and self.prerelease == other.prerelease)

    def __hash__(self) -> int:
        return hash((self._key(), self.prerelease))

    @staticmethod
    def _compare_identifiers(left: tuple, right: tuple) -> int:
        # A release outranks any of its prereleases.
        if not left and not right:
            return 0
        if not left:
            return 1
        if not right:
            return -1
        for a, b in zip(left, right):
            if a == b:
                continue
            a_num = _NUMERIC_RE.match(a) is not None
            b_num = _NUMERIC_RE.match(b) is not None
            if a_num and b_num:
                return -1 if int(a) < int(b) else 1
            if a_num:
                return -1  # numeric identifiers sort below alphanumeric
            if b_num:
                return 1
            return -1 if a < b else 1
        if len(left) == len(right):
            return 0
        return -1 if len(left) < len(right) else 1

    def _compare(self, other: "Version") -> int:
        if self._key() != other._key():
            return -1 if self._key() < other._key() else 1
        return self._compare_identifiers(self.prerelease, other.prerelease)

    def __lt__(self, other: "Version") -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._compare(other) < 0

    def __le__(self, other: "Version") -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._compare(other) <= 0

    def __gt__(self, other: "Version") -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._compare(other) > 0

    def __ge__(self, other: "Version") -> bool:
        if not isinstance(other, Version):
            return NotImplemented
        return self._compare(other) >= 0
