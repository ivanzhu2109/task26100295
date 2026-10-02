"""Randomized cross-check of the solver against an independent
brute-force enumerator over small catalogs."""

import itertools
import random
import unittest

from pixelforge import (Catalog, Conflict, Dependency, Release, RootRequest,
                        Solution, Version, VersionSet, resolve)

VERSION_POOL = [
    "1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-beta", "1.0.0",
    "1.1.0-rc.1", "1.1.0", "2.0.0",
]
PLATFORMS = ("linux", "win", "mac")


def brute_force_solutions(catalog, roots, targets):
    """Independently enumerate every valid flat selection."""
    names = sorted(catalog.releases)
    choices = []
    for name in names:
        usable = [ver for ver in catalog.versions(name)
                  if targets <= catalog.get(name, ver).passed_platforms]
        choices.append([None] + usable)
    valid = []
    for combo in itertools.product(*choices):
        selection = {name: ver for name, ver in zip(names, combo)
                     if ver is not None}
        if _is_valid(catalog, roots, selection):
            valid.append(selection)
    return valid


def _is_valid(catalog, roots, selection):
    # Every root request satisfied.
    for request in roots:
        if request.name not in selection:
            return False
        if not request.constraint.contains(selection[request.name]):
            return False
    # Dependency closure and constraint satisfaction.
    for name, ver in selection.items():
        for dep in catalog.get(name, ver).dependencies:
            if dep.name not in selection:
                return False
            if not dep.constraint.contains(selection[dep.name]):
                return False
    # Only components reachable from roots may be selected.
    reachable = set()
    stack = [request.name for request in roots]
    while stack:
        current = stack.pop()
        if current in reachable or current not in selection:
            continue
        reachable.add(current)
        stack.extend(dep.name
                     for dep in catalog.get(
                         current, selection[current]).dependencies)
    if set(selection) != reachable:
        return False
    # The dependency graph over selected releases must be acyclic.
    edges = {name: [dep.name
                    for dep in catalog.get(name, ver).dependencies]
             for name, ver in selection.items()}
    visiting, done = set(), set()

    def visit(node):
        if node in done:
            return True
        if node in visiting:
            return False
        visiting.add(node)
        for nxt in edges.get(node, ()):
            if nxt in edges and not visit(nxt):
                return False
        visiting.discard(node)
        done.add(node)
        return True

    return all(visit(node) for node in edges)


def random_constraint(rng):
    kind = rng.randrange(3)
    if kind == 0:
        return VersionSet.exact(Version.parse(rng.choice(VERSION_POOL)))
    low = rng.choice([None] + VERSION_POOL)
    high = rng.choice([None] + VERSION_POOL)
    low_v = Version.parse(low) if low else None
    high_v = Version.parse(high) if high else None
    if low_v is not None and high_v is not None and low_v > high_v:
        low_v, high_v = high_v, low_v
    return VersionSet.range(low_v, high_v)


def random_instance(rng):
    catalog = Catalog()
    names = ["c%d" % i for i in range(rng.randint(2, 4))]
    for name in names:
        for text in VERSION_POOL:
            if rng.random() < 0.45:
                deps = []
                for other in names:
                    if rng.random() < 0.25:
                        deps.append(Dependency(
                            other, random_constraint(rng)))
                passed = frozenset(
                    p for p in PLATFORMS if rng.random() < 0.7)
                catalog.add(Release(name, Version.parse(text),
                                    tuple(deps), passed))
    targets = set(p for p in PLATFORMS if rng.random() < 0.7)
    if not targets:
        targets = {rng.choice(PLATFORMS)}
    roots = [RootRequest(rng.choice(names), random_constraint(rng))
             for _ in range(rng.randint(1, 4))]
    return catalog, roots, targets


class ExhaustiveCrossCheckTest(unittest.TestCase):
    def check_instance(self, catalog, roots, targets):
        expected = brute_force_solutions(catalog, roots, targets)
        result = resolve(catalog, roots, targets)
        if expected:
            self.assertIsInstance(result, Solution)
            picked = dict(result.selections)
            self.assertTrue(
                _is_valid(catalog, roots, picked),
                f"solver returned invalid solution {picked}")
            for name, ver in picked.items():
                self.assertLessEqual(
                    targets, set(catalog.get(name, ver).passed_platforms))
        else:
            self.assertIsInstance(result, Conflict)
            indices = result.root_indices
            self.assertTrue(indices)
            self.assertEqual(sorted(indices), list(indices))
            sub = [roots[i] for i in indices]
            self.assertEqual(
                brute_force_solutions(catalog, sub, targets), [],
                "conflict subset is satisfiable")
            for drop in range(len(indices)):
                reduced = [roots[i] for j, i in enumerate(indices)
                           if j != drop]
                self.assertNotEqual(
                    brute_force_solutions(catalog, reduced, targets), [],
                    f"conflict subset not irreducible: {indices} "
                    f"minus position {indices[drop]} still unsat")

    def test_random_instances(self):
        for seed in range(400):
            rng = random.Random(seed)
            catalog, roots, targets = random_instance(rng)
            with self.subTest(seed=seed):
                self.check_instance(catalog, roots, targets)


if __name__ == "__main__":
    unittest.main()
