"""Runnable demo: python3 examples/demo.py"""

from pixelforge import (Catalog, Constraint, Dependency, Release, RootRequest,
                        Version, resolve)
from pixelforge.catalog import PASSED

p = Version.parse
targets = frozenset({"linux", "windows"})

catalog = Catalog((
    Release("app", p("1.0.0"),
            (Dependency("lib", Constraint.range(p("1.0.0"), p("2.0.0"))),),
            {"linux": PASSED, "windows": PASSED}),
    Release("app", p("2.0.0"),
            (Dependency("lib", Constraint.range(p("2.0.0"), p("3.0.0"))),),
            {"linux": PASSED, "windows": PASSED}),
    Release("lib", p("1.5.0"), (), {"linux": PASSED, "windows": PASSED}),
    Release("lib", p("2.5.0"), (), {"linux": PASSED, "windows": PASSED}),
))

roots = [
    RootRequest("app", Constraint.any()),
    RootRequest("lib", Constraint.range(p("1.0.0"), p("2.0.0"))),
]
print("case 1 (downgrade needed):", resolve(catalog, roots, targets))

roots = [
    RootRequest("app", Constraint.exact(p("1.0.0"))),
    RootRequest("app", Constraint.exact(p("2.0.0"))),
    RootRequest("lib", Constraint.any()),
]
print("case 2 (irreducible conflict):", resolve(catalog, roots, targets))
