"""Randomized small catalogs cross-checked against an independent
brute-force enumerator, covering prereleases and platform filtering."""

import itertools
import random
import unittest

from pixelforge import (Catalog, Conflict, Constraint, Dependency, Release,
                        RootRequest, Solution, Version, resolve)
from pixelforge.catalog import PASSED
from pixelforge.solver import _has_cycle

p = Version.parse

VERSION_POOL = ["0.9.0", "1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-beta.2",
                "1.0.0", "1.1.0", "2.0.0-rc.1", "2.0.0"]
NAME_POOL = ["alpha", "beta", "gamma", "delta"]
PLATFORMS = ("linux", "windows")
STATUSES = (PASSED,) * 4 + ("failed", "untested", None)  # None = missing


def brute_force_solutions(catalog, roots, targets):
    """Independently enumerate every valid assignment."""
    names = catalog.names()
    choices = []
    for name in names:
        usable = [r for r in catalog.releases_of(name) if r.usable_on(targets)]
        choices.append([None] + usable)
    valid = []
    for combo in itertools.product(*choices):
        assignment = {n: r for n, r in zip(names, combo) if r is not None}
        if _is_valid(assignment, roots):
            valid.append(assignment)
    return valid


def _is_valid(assignment, roots):
    selected = set(assignment)
    for request in roots:
        release = assignment.get(request.name)
        if release is None or not request.constraint.contains(release.version):
            return False
    for release in assignment.values():
        for dep in release.dependencies:
            target = assignment.get(dep.name)
            if target is None or not dep.constraint.contains(target.version):
                return False
    # Exactly roots plus recursively introduced dependencies: no extras.
    reachable = set()
    stack = [request.name for request in roots]
    while stack:
        name = stack.pop()
        if name in reachable:
            continue
        reachable.add(name)
        release = assignment.get(name)
        if release is not None:
            stack.extend(dep.name for dep in release.dependencies)
    if selected != reachable:
        return False
    return not _has_cycle(assignment)


def random_constraint(rng, version_pool, anchor=None):
    kind = rng.randrange(4)
    if kind == 0:
        return Constraint.any()
    if kind == 1:
        return Constraint.exact(p(anchor or rng.choice(version_pool)))
    if anchor is not None and rng.random() < 0.8:
        # Bracket an existing version so the constraint is often satisfiable.
        others = [v for v in version_pool if v != anchor]
        lo = rng.choice([None, anchor] + others)
        hi = rng.choice([None] + others)
        if lo is not None and p(lo) > p(anchor):
            lo = None
        if hi is not None and p(hi) <= p(anchor):
            hi = None
    else:
        lo = rng.choice([None] + version_pool)
        hi = rng.choice([None] + version_pool)
    if lo is not None and hi is not None and p(lo) > p(hi):
        lo, hi = hi, lo
    return Constraint.range(p(lo) if lo else None, p(hi) if hi else None)


def random_instance(rng):
    names = rng.sample(NAME_POOL, rng.randint(2, 4))
    versions_of = {name: rng.sample(VERSION_POOL, rng.randint(1, 3))
                   for name in names}
    releases = []
    for name in names:
        for version in versions_of[name]:
            deps = []
            for _ in range(rng.randrange(3) if rng.random() < 0.6 else 1):
                target = rng.choice(names)
                anchor = rng.choice(versions_of[target])
                deps.append(Dependency(
                    target, random_constraint(rng, VERSION_POOL, anchor)))
            if rng.random() < 0.55:
                status = {platform: PASSED for platform in PLATFORMS}
            else:
                status = {}
                for platform in PLATFORMS:
                    value = rng.choice(STATUSES)
                    if value is not None:
                        status[platform] = value
            releases.append(Release(name, p(version), tuple(deps), status))
    catalog = Catalog(tuple(releases))
    roots = []
    for _ in range(rng.randint(1, 3)):
        name = rng.choice(names)
        roots.append(RootRequest(
            name, random_constraint(rng, VERSION_POOL,
                                    rng.choice(versions_of[name]))))
    targets = frozenset(rng.sample(PLATFORMS, rng.randint(1, 2)))
    return catalog, roots, targets


def random_planted_instance(rng):
    """Instance built around a planted valid assignment, plus noise."""
    names = rng.sample(NAME_POOL, rng.randint(3, 4))
    versions_of = {name: rng.sample(VERSION_POOL, rng.randint(1, 3))
                   for name in names}
    planted = {name: rng.choice(versions_of[name]) for name in names}
    releases = []
    for index, name in enumerate(names):
        deps = []
        later = names[index + 1:]  # DAG by construction: no cycles back
        for target in rng.sample(later, min(len(later), rng.randrange(3))):
            deps.append(Dependency(
                target, random_constraint(rng, VERSION_POOL, planted[target])))
        if rng.random() < 0.3:  # noise dep may occasionally break the plant
            target = rng.choice(names)
            deps.append(Dependency(target, random_constraint(rng, VERSION_POOL)))
        releases.append(Release(name, p(planted[name]), tuple(deps),
                                {platform: PASSED for platform in PLATFORMS}))
        for version in versions_of[name]:
            if version == planted[name]:
                continue
            noise_deps = [Dependency(rng.choice(names),
                                     random_constraint(rng, VERSION_POOL))
                          for _ in range(rng.randrange(3))]
            status = {}
            for platform in PLATFORMS:
                value = rng.choice(STATUSES)
                if value is not None:
                    status[platform] = value
            releases.append(Release(name, p(version), tuple(noise_deps), status))
    catalog = Catalog(tuple(releases))
    roots = []
    for _ in range(rng.randint(1, 3)):
        name = rng.choice(names)
        roots.append(RootRequest(
            name, random_constraint(rng, VERSION_POOL, planted[name])))
    targets = frozenset(rng.sample(PLATFORMS, rng.randint(1, 2)))
    return catalog, roots, targets


class TestRandomizedCrossCheck(unittest.TestCase):
    def test_against_brute_force(self):
        for seed in range(400):
            rng = random.Random(seed)
            if seed % 2 == 0:
                catalog, roots, targets = random_planted_instance(rng)
            else:
                catalog, roots, targets = random_instance(rng)
            with self.subTest(seed=seed):
                expected = brute_force_solutions(catalog, roots, targets)
                out = resolve(catalog, roots, targets)
                if expected:
                    self.assertIsInstance(out, Solution)
                    assignment = {}
                    for name, version in out.versions.items():
                        match = [r for r in catalog.releases_of(name)
                                 if r.version == version]
                        self.assertEqual(len(match), 1)
                        self.assertTrue(match[0].usable_on(targets))
                        assignment[name] = match[0]
                    self.assertTrue(_is_valid(assignment, roots))
                else:
                    self.assertIsInstance(out, Conflict)
                    indices = out.root_indices
                    self.assertTrue(indices)
                    self.assertEqual(len(set(indices)), len(indices))
                    subset = [roots[i] for i in indices]
                    self.assertEqual(
                        brute_force_solutions(catalog, subset, targets), [],
                        "conflict subset must itself be unsolvable")
                    for dropped in indices:
                        reduced = [roots[i] for i in indices if i != dropped]
                        self.assertNotEqual(
                            brute_force_solutions(catalog, reduced, targets), [],
                            f"dropping root {dropped} must make it solvable")


if __name__ == "__main__":
    unittest.main()
