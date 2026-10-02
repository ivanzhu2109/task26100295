"""PixelForge multi-platform dependency resolution library."""

from .catalog import (FAILED, PASSED, UNTESTED, Catalog, Dependency, Release)
from .constraint import Constraint, Interval
from .solver import Conflict, RootRequest, Solution, resolve
from .version import Version

__all__ = [
    "Catalog", "Conflict", "Constraint", "Dependency", "FAILED", "Interval",
    "PASSED", "Release", "RootRequest", "Solution", "UNTESTED", "Version",
    "resolve",
]
