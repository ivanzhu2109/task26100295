"""Backtracking dependency solver."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Set, Union

from .constraints import VersionSet
from .model import Catalog, Conflict, Release, RootRequest, Solution


def resolve(catalog: Catalog,
            roots: Sequence[RootRequest],
            targets: Set[str]) -> Union[Solution, Conflict]:
    """Resolve roots against catalog for all target platforms.

    Returns a Solution with one version per component, or a Conflict
    carrying an irreducible unsatisfiable subset of root positions.
    """
    if not targets:
        raise ValueError("targets must be a non-empty set of platforms")
    solution = _solve(catalog, roots, targets)
    if solution is not None:
        return solution
    # Deletion-based minimization: drop every root request whose removal
    # keeps the remainder unsatisfiable. Satisfiability is monotone under
    # removing requests, so a single pass yields an irreducible subset.
    indices = list(range(len(roots)))
    for idx in list(indices):
        trial = [j for j in indices if j != idx]
        if _solve(catalog, [roots[j] for j in trial], targets) is None:
            indices = trial
    return Conflict(tuple(indices))


def _solve(catalog: Catalog,
           roots: Sequence[RootRequest],
           targets: Set[str]) -> Optional[Solution]:
    constraints: Dict[str, VersionSet] = {}
    for request in roots:
        merged = constraints.get(request.name, VersionSet.any())
        merged = merged.intersect(request.constraint)
        if merged.is_empty():
            return None
        constraints[request.name] = merged
    selected: Dict[str, Release] = {}
    if _search(catalog, targets, constraints, selected):
        return Solution(tuple(sorted(
            (name, release.version) for name, release in selected.items()
        )))
    return None


def _search(catalog: Catalog,
            targets: Set[str],
            constraints: Dict[str, VersionSet],
            selected: Dict[str, Release]) -> bool:
    pending = [name for name in constraints if name not in selected]
    if not pending:
        return True
    name = min(pending)
    allowed = constraints[name]
    for version in reversed(catalog.versions(name)):
        if not allowed.contains(version):
            continue
        release = catalog.get(name, version)
        if release is None or not targets <= release.passed_platforms:
            continue
        if _creates_cycle(selected, name, release):
            continue
        merged = _propagate(constraints, selected, release)
        if merged is None:
            continue
        if not _has_candidate_everywhere(catalog, targets, merged, selected):
            continue
        selected[name] = release
        if _search(catalog, targets, merged, selected):
            return True
        del selected[name]
    return False


def _propagate(constraints: Dict[str, VersionSet],
               selected: Dict[str, Release],
               release: Release) -> Optional[Dict[str, VersionSet]]:
    """Fold a candidate release's dependency constraints into the current
    constraint map. Returns None if any constraint becomes empty or
    contradicts an already selected release."""
    merged = dict(constraints)
    for dep in release.dependencies:
        current = merged.get(dep.name, VersionSet.any())
        current = current.intersect(dep.constraint)
        if current.is_empty():
            return None
        merged[dep.name] = current
    for name, chosen in selected.items():
        bound = merged.get(name)
        if bound is not None and not bound.contains(chosen.version):
            return None
    return merged


def _has_candidate_everywhere(catalog: Catalog,
                              targets: Set[str],
                              constraints: Dict[str, VersionSet],
                              selected: Dict[str, Release]) -> bool:
    """Forward check: every constrained but unselected component must
    still have at least one usable version."""
    for name, allowed in constraints.items():
        if name in selected:
            continue
        if not any(allowed.contains(version)
                   and targets <= catalog.get(name, version).passed_platforms
                   for version in catalog.versions(name)):
            return False
    return True


def _creates_cycle(selected: Dict[str, Release],
                   name: str,
                   release: Release) -> bool:
    """True if selecting ``release`` for ``name`` would close a dependency
    cycle through already selected releases (including a self-loop)."""
    for dep in release.dependencies:
        if dep.name == name:
            return True
        if _reachable(selected, dep.name, name):
            return True
    return False


def _reachable(selected: Dict[str, Release], start: str, goal: str) -> bool:
    """True if ``goal`` is reachable from ``start`` following dependency
    edges of selected releases."""
    stack = [start]
    seen = set()
    while stack:
        current = stack.pop()
        if current == goal:
            return True
        if current in seen:
            continue
        seen.add(current)
        release = selected.get(current)
        if release is not None:
            stack.extend(dep.name for dep in release.dependencies)
    return False
