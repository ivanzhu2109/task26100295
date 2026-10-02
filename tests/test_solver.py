import unittest

from pixelforge import (Catalog, Conflict, Constraint, Dependency, Release,
                        RootRequest, Solution, Version, resolve)
from pixelforge.catalog import FAILED, PASSED, UNTESTED

p = Version.parse
LINUX = "linux"
WINDOWS = "windows"
BOTH = frozenset({LINUX, WINDOWS})


def rel(name, version, deps=(), status=None):
    return Release(name, p(version), tuple(deps),
                   status if status is not None else {LINUX: PASSED, WINDOWS: PASSED})


def dep(name, lo=None, hi=None, exact=None):
    if exact is not None:
        return Dependency(name, Constraint.exact(p(exact)))
    return Dependency(name, Constraint.range(p(lo) if lo else None,
                                             p(hi) if hi else None))


def root(name, lo=None, hi=None, exact=None):
    if exact is not None:
        return RootRequest(name, Constraint.exact(p(exact)))
    if lo is None and hi is None:
        return RootRequest(name, Constraint.any())
    return RootRequest(name, Constraint.range(p(lo) if lo else None,
                                              p(hi) if hi else None))


class TestBacktracking(unittest.TestCase):
    def test_high_version_shared_dep_conflict_downgrade_solves(self):
        # app 2.0.0 needs lib [2,3); the other root pins lib to [1,2).
        # Trying app 2.0.0 first must be undone: lib 2.x constraints from
        # the abandoned app 2.0.0 release must not leak into the final pick.
        catalog = Catalog((
            rel("app", "1.0.0", (dep("lib", "1.0.0", "2.0.0"),)),
            rel("app", "2.0.0", (dep("lib", "2.0.0", "3.0.0"),)),
            rel("lib", "1.5.0"),
            rel("lib", "2.5.0"),
        ))
        out = resolve(catalog, [root("app"), root("lib", "1.0.0", "2.0.0")], BOTH)
        self.assertIsInstance(out, Solution)
        self.assertEqual(out.versions, {"app": p("1.0.0"), "lib": p("1.5.0")})

    def test_abandoned_release_leaves_no_dependency_trace(self):
        # app 2.0.0 depends on ghost, which has no usable release; after
        # backtracking to app 1.0.0, ghost must not appear in the solution.
        catalog = Catalog((
            rel("app", "1.0.0"),
            rel("app", "2.0.0", (dep("ghost", "1.0.0", "2.0.0"),)),
            rel("ghost", "1.5.0", status={LINUX: FAILED, WINDOWS: PASSED}),
        ))
        out = resolve(catalog, [root("app")], BOTH)
        self.assertIsInstance(out, Solution)
        self.assertEqual(out.versions, {"app": p("1.0.0")})

    def test_high_version_cycle_downgrade_solves(self):
        # a 2.0.0 <-> b 1.0.0 form a cycle; a 1.0.0 stands alone.
        catalog = Catalog((
            rel("a", "1.0.0"),
            rel("a", "2.0.0", (dep("b", "1.0.0", "2.0.0"),)),
            rel("b", "1.0.0", (dep("a", exact="2.0.0"),)),
        ))
        out = resolve(catalog, [root("a")], BOTH)
        self.assertIsInstance(out, Solution)
        self.assertEqual(out.versions, {"a": p("1.0.0")})

    def test_self_loop_rejected(self):
        catalog = Catalog((
            rel("c", "0.9.0"),
            rel("c", "1.0.0", (dep("c", "1.0.0", "2.0.0"),)),
        ))
        out = resolve(catalog, [root("c")], BOTH)
        self.assertIsInstance(out, Solution)
        self.assertEqual(out.versions, {"c": p("0.9.0")})

    def test_all_versions_cyclic_means_conflict(self):
        catalog = Catalog((
            rel("a", "1.0.0", (dep("b", "1.0.0", "2.0.0"),)),
            rel("b", "1.0.0", (dep("a", "1.0.0", "2.0.0"),)),
        ))
        out = resolve(catalog, [root("a")], BOTH)
        self.assertIsInstance(out, Conflict)
        self.assertEqual(out.root_indices, (0,))


class TestPlatformFilter(unittest.TestCase):
    def test_failed_untested_missing_all_unusable(self):
        catalog = Catalog((
            rel("x", "1.0.0", status={LINUX: PASSED, WINDOWS: PASSED}),
            rel("x", "2.0.0", status={LINUX: PASSED, WINDOWS: FAILED}),
            rel("y", "1.0.0", status={LINUX: PASSED, WINDOWS: UNTESTED}),
            rel("y", "2.0.0", status={LINUX: PASSED}),  # windows missing
        ))
        out = resolve(catalog, [root("x")], BOTH)
        self.assertEqual(out.versions, {"x": p("1.0.0")})
        out = resolve(catalog, [root("y")], BOTH)
        self.assertIsInstance(out, Conflict)
        # A narrower target set admits the previously unusable releases.
        out = resolve(catalog, [root("y")], frozenset({LINUX}))
        self.assertEqual(out.versions, {"y": p("2.0.0")})

    def test_empty_targets_rejected(self):
        with self.assertRaises(ValueError):
            resolve(Catalog(()), [], frozenset())


class TestConflict(unittest.TestCase):
    def test_irreducible_subset_with_duplicate_roots(self):
        catalog = Catalog((rel("a", "1.0.0"), rel("a", "2.0.0"), rel("b", "1.0.0")))
        roots = [root("b"), root("a", exact="1.0.0"), root("a", exact="2.0.0")]
        out = resolve(catalog, roots, BOTH)
        self.assertIsInstance(out, Conflict)
        # The two contradictory "a" requests form the conflict; "b" is dropped.
        self.assertEqual(out.root_indices, (1, 2))

    def test_missing_component(self):
        out = resolve(Catalog(()), [root("nope")], BOTH)
        self.assertIsInstance(out, Conflict)
        self.assertEqual(out.root_indices, (0,))


class TestBasics(unittest.TestCase):
    def test_empty_roots_empty_solution(self):
        out = resolve(Catalog(()), [], BOTH)
        self.assertIsInstance(out, Solution)
        self.assertEqual(out.versions, {})

    def test_transitive_closure_only(self):
        catalog = Catalog((
            rel("app", "1.0.0", (dep("mid", "1.0.0", "2.0.0"),)),
            rel("mid", "1.0.0", (dep("leaf", "1.0.0", "2.0.0"),)),
            rel("leaf", "1.0.0"),
            rel("stray", "9.9.9"),
        ))
        out = resolve(catalog, [root("app")], BOTH)
        self.assertEqual(out.versions,
                         {"app": p("1.0.0"), "mid": p("1.0.0"), "leaf": p("1.0.0")})

    def test_prerelease_versions_participate(self):
        catalog = Catalog((
            rel("a", "1.0.0-alpha"),
            rel("a", "1.0.0-beta.2"),
            rel("a", "1.0.0"),
        ))
        out = resolve(catalog, [root("a", "1.0.0-alpha", "1.0.0")], BOTH)
        self.assertEqual(out.versions, {"a": p("1.0.0-beta.2")})
        out = resolve(catalog, [root("a", exact="1.0.0-alpha")], BOTH)
        self.assertEqual(out.versions, {"a": p("1.0.0-alpha")})


if __name__ == "__main__":
    unittest.main()
