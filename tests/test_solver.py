"""Scenario tests for the resolver."""

import unittest

from pixelforge import (Catalog, Conflict, Dependency, Release, RootRequest,
                        Solution, Version, VersionSet, resolve)


def v(text):
    return Version.parse(text)


def exact(text):
    return VersionSet.exact(v(text))


def rng(low, high):
    return VersionSet.range(v(low) if low else None,
                            v(high) if high else None)


PLATS = frozenset({"linux", "win"})


def rel(name, version, deps=(), platforms=PLATS):
    return Release(name, v(version), tuple(
        Dependency(dname, constraint) for dname, constraint in deps
    ), frozenset(platforms))


class BasicSolveTest(unittest.TestCase):
    def test_simple_chain(self):
        cat = Catalog()
        cat.add(rel("a", "1.0.0", [("b", rng("1.0.0", "2.0.0"))]))
        cat.add(rel("b", "1.5.0"))
        sol = resolve(cat, [RootRequest("a", exact("1.0.0"))],
                      {"linux", "win"})
        self.assertIsInstance(sol, Solution)
        self.assertEqual(dict(sol.selections),
                         {"a": v("1.0.0"), "b": v("1.5.0")})

    def test_empty_roots_gives_empty_solution(self):
        sol = resolve(Catalog(), [], {"linux"})
        self.assertIsInstance(sol, Solution)
        self.assertEqual(sol.selections, ())

    def test_empty_targets_rejected(self):
        with self.assertRaises(ValueError):
            resolve(Catalog(), [], set())

    def test_duplicate_roots_intersect(self):
        cat = Catalog()
        cat.add(rel("a", "1.0.0"))
        cat.add(rel("a", "1.5.0"))
        cat.add(rel("a", "2.0.0"))
        roots = [RootRequest("a", rng("1.0.0", "2.0.0")),
                 RootRequest("a", rng("1.4.0", None))]
        sol = resolve(cat, roots, {"linux"})
        self.assertEqual(dict(sol.selections), {"a": v("1.5.0")})

    def test_solution_contains_only_required_components(self):
        cat = Catalog()
        cat.add(rel("a", "1.0.0"))
        cat.add(rel("unrelated", "3.0.0"))
        sol = resolve(cat, [RootRequest("a", exact("1.0.0"))], {"linux"})
        self.assertEqual(dict(sol.selections), {"a": v("1.0.0")})


class PlatformFilterTest(unittest.TestCase):
    def setUp(self):
        self.cat = Catalog()
        self.cat.add(rel("a", "1.0.0", platforms={"linux"}))
        self.cat.add(rel("a", "1.1.0", platforms={"linux", "win"}))
        self.cat.add(rel("b", "2.0.0", platforms=set()))  # untested
        self.cat.add(rel("c", "2.0.0", platforms={"linux"}))

    def test_failed_or_untested_release_skipped(self):
        sol = resolve(self.cat, [RootRequest("a", rng(None, None))],
                      {"linux", "win"})
        self.assertEqual(dict(sol.selections), {"a": v("1.1.0")})

    def test_untested_component_unsatisfiable(self):
        result = resolve(self.cat, [RootRequest("b", exact("2.0.0"))],
                         {"linux"})
        self.assertIsInstance(result, Conflict)
        self.assertEqual(result.root_indices, (0,))

    def test_missing_platform_entry_means_unusable(self):
        # "c" passed only linux; requiring win too makes it unusable.
        result = resolve(self.cat, [RootRequest("c", exact("2.0.0"))],
                         {"linux", "win"})
        self.assertIsInstance(result, Conflict)


class BacktrackingTest(unittest.TestCase):
    def test_downgrade_resolves_shared_dependency_conflict(self):
        """High version of "app" forces shared "lib" >= 2.0, but the other
        root needs lib < 2.0; only downgrading app to 1.0.0 works. The
        solver must retract the lib>=2.0 constraint introduced by the
        abandoned app 2.0.0 release."""
        cat = Catalog()
        cat.add(rel("app", "2.0.0", [("lib", rng("2.0.0", "3.0.0"))]))
        cat.add(rel("app", "1.0.0", [("lib", rng("1.0.0", "2.0.0"))]))
        cat.add(rel("lib", "2.0.0"))
        cat.add(rel("lib", "1.5.0"))
        cat.add(rel("tool", "1.0.0", [("lib", rng(None, "2.0.0"))]))
        roots = [RootRequest("app", rng("1.0.0", None)),
                 RootRequest("tool", exact("1.0.0"))]
        sol = resolve(cat, roots, {"linux", "win"})
        self.assertIsInstance(sol, Solution)
        picked = dict(sol.selections)
        self.assertEqual(picked["app"], v("1.0.0"))
        self.assertEqual(picked["lib"], v("1.5.0"))
        self.assertEqual(picked["tool"], v("1.0.0"))

    def test_downgrade_avoids_cycle_introduced_by_high_version(self):
        """app 2.0.0 depends on ext which depends back on app>=2.0.0
        (a cycle); app 1.0.0 has no such dependency and must be chosen."""
        cat = Catalog()
        cat.add(rel("app", "2.0.0", [("ext", exact("1.0.0"))]))
        cat.add(rel("app", "1.0.0"))
        cat.add(rel("ext", "1.0.0", [("app", rng("2.0.0", None))]))
        sol = resolve(cat, [RootRequest("app", rng("1.0.0", None))],
                      {"linux"})
        self.assertIsInstance(sol, Solution)
        self.assertEqual(dict(sol.selections), {"app": v("1.0.0")})

    def test_abandoned_release_leaves_no_phantom_dependency(self):
        """If the solver first tries app 2.0.0 (which pulls in ghost) and
        backtracks, the final solution must not contain ghost."""
        cat = Catalog()
        cat.add(rel("app", "2.0.0", [("ghost", exact("9.9.9"))]))
        cat.add(rel("app", "1.0.0"))
        # ghost exists but conflicts: it requires app<2.0.0... make ghost
        # simply unusable so 2.0.0 fails and the solver backtracks.
        cat.add(rel("ghost", "9.9.9", platforms=set()))
        sol = resolve(cat, [RootRequest("app", rng("1.0.0", None))],
                      {"linux"})
        self.assertIsInstance(sol, Solution)
        self.assertEqual(dict(sol.selections), {"app": v("1.0.0")})

    def test_deep_backtrack_over_shared_dep(self):
        """Diamond: a->b, a->c, b->d[2,*), c->d[*,2). Lowering a avoids
        the impossible d constraint combination."""
        cat = Catalog()
        cat.add(rel("a", "2.0.0", [("b", exact("1.0.0")),
                                   ("c", exact("1.0.0"))]))
        cat.add(rel("a", "1.0.0", [("d", rng("1.0.0", "3.0.0"))]))
        cat.add(rel("b", "1.0.0", [("d", rng("2.0.0", None))]))
        cat.add(rel("c", "1.0.0", [("d", rng(None, "2.0.0"))]))
        cat.add(rel("d", "1.0.0"))
        cat.add(rel("d", "2.0.0"))
        sol = resolve(cat, [RootRequest("a", rng("1.0.0", None))],
                      {"linux", "win"})
        self.assertIsInstance(sol, Solution)
        picked = dict(sol.selections)
        self.assertEqual(picked["a"], v("1.0.0"))
        self.assertNotIn("b", picked)
        self.assertNotIn("c", picked)


class CycleTest(unittest.TestCase):
    def test_self_loop_rejected(self):
        cat = Catalog()
        cat.add(rel("a", "1.0.0", [("a", exact("1.0.0"))]))
        result = resolve(cat, [RootRequest("a", exact("1.0.0"))], {"linux"})
        self.assertIsInstance(result, Conflict)

    def test_two_node_cycle_rejected(self):
        cat = Catalog()
        cat.add(rel("a", "1.0.0", [("b", exact("1.0.0"))]))
        cat.add(rel("b", "1.0.0", [("a", exact("1.0.0"))]))
        result = resolve(cat, [RootRequest("a", exact("1.0.0"))], {"linux"})
        self.assertIsInstance(result, Conflict)

    def test_dag_diamond_is_not_a_cycle(self):
        cat = Catalog()
        cat.add(rel("a", "1.0.0", [("b", exact("1.0.0")),
                                   ("c", exact("1.0.0"))]))
        cat.add(rel("b", "1.0.0", [("d", exact("1.0.0"))]))
        cat.add(rel("c", "1.0.0", [("d", exact("1.0.0"))]))
        cat.add(rel("d", "1.0.0"))
        sol = resolve(cat, [RootRequest("a", exact("1.0.0"))], {"linux"})
        self.assertIsInstance(sol, Solution)
        self.assertEqual(len(sol.selections), 4)


class PrereleaseTest(unittest.TestCase):
    def test_prerelease_participates_in_ranges(self):
        cat = Catalog()
        cat.add(rel("a", "1.0.0-alpha"))
        cat.add(rel("a", "1.0.0"))
        # Range includes prereleases by standard ordering, no filtering.
        sol = resolve(cat, [RootRequest("a", rng("1.0.0-alpha", "1.0.0"))],
                      {"linux"})
        self.assertEqual(dict(sol.selections), {"a": v("1.0.0-alpha")})

    def test_exact_prerelease_selected(self):
        cat = Catalog()
        cat.add(rel("a", "2.0.0-rc.1"))
        cat.add(rel("a", "2.0.0"))
        sol = resolve(cat, [RootRequest("a", exact("2.0.0-rc.1"))],
                      {"linux"})
        self.assertEqual(dict(sol.selections), {"a": v("2.0.0-rc.1")})


class ConflictTest(unittest.TestCase):
    def test_conflict_reports_minimal_root_subset(self):
        cat = Catalog()
        cat.add(rel("a", "1.0.0"))
        cat.add(rel("b", "1.0.0"))
        roots = [RootRequest("a", exact("1.0.0")),   # 0: fine
                 RootRequest("b", exact("2.0.0")),   # 1: impossible
                 RootRequest("a", rng(None, None))]  # 2: fine
        result = resolve(cat, roots, {"linux"})
        self.assertIsInstance(result, Conflict)
        self.assertEqual(result.root_indices, (1,))

    def test_conflict_pair_distinguished_by_position(self):
        cat = Catalog()
        cat.add(rel("a", "1.0.0"))
        cat.add(rel("a", "2.5.0"))
        roots = [RootRequest("a", exact("1.0.0")),
                 RootRequest("a", exact("1.0.0")),   # duplicate, fine
                 RootRequest("a", rng("2.0.0", None))]  # contradicts 0 and 1
        result = resolve(cat, roots, {"linux"})
        self.assertIsInstance(result, Conflict)
        # Irreducible: {0,2} or {1,2}; both size 2.
        self.assertEqual(len(result.root_indices), 2)
        self.assertIn(2, result.root_indices)

    def test_conflict_through_dependency(self):
        cat = Catalog()
        cat.add(rel("app", "1.0.0", [("lib", rng("2.0.0", None))]))
        cat.add(rel("lib", "1.0.0"))
        cat.add(rel("lib", "2.0.0"))
        roots = [RootRequest("app", exact("1.0.0")),
                 RootRequest("lib", rng(None, "2.0.0"))]
        result = resolve(cat, roots, {"linux"})
        self.assertIsInstance(result, Conflict)
        self.assertEqual(result.root_indices, (0, 1))


if __name__ == "__main__":
    unittest.main()
