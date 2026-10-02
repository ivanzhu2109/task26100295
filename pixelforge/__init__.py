"""PixelForge multi-platform dependency resolution library."""

from .constraints import Interval, VersionSet
from .model import (FAILED, PASSED, UNTESTED, Catalog, Conflict, Dependency,
                    Release, RootRequest, Solution)
from .solver import resolve
from .version import Version

__all__ = [
    "Version",
    "Interval",
    "VersionSet",
    "Catalog",
    "Release",
    "Dependency",
    "RootRequest",
    "Solution",
    "Conflict",
    "resolve",
    "PASSED",
    "FAILED",
    "UNTESTED",
]
