"""Backtracking dependency solver and irreducible-conflict extraction."""

from __future__ import annotations

from .catalog import Catalog, Release
from .constraint import Constraint
from .version import Version

__all__ = ["RootRequest", "Solution", "Conflict", "resolve"]


class RootRequest:
    """One root request: component name plus constraint.

    Duplicate components are allowed; requests are distinguished by their
    position in the roots list.
    """

    __slots__ = ("name", "constraint")

    def __init__(self, name: str, constraint: Constraint) -> None:
        self.name = name
        self.constraint = constraint

    def __repr__(self) -> str:
        return f"RootRequest({self.name!r}, {self.constraint!r})"


class Solution:
    """A flat set of chosen versions: exactly one version per component."""

    __slots__ = ("versions",)

    def __init__(self, versions: dict[str, Version]) -> None:
        self.versions = dict(versions)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Solution):
            return NotImplemented
        return self.versions == other.versions

    def __repr__(self) -> str:
        inner = ", ".join(f"{k}: {v}" for k, v in sorted(self.versions.items()))
        return f"Solution({{{inner}}})"


class Conflict:
    """An irreducible subset of root-request positions with no solution.

    The subset itself is unsolvable under the same catalog and targets;
    dropping any single request from it makes it solvable.
    """

    __slots__ = ("root_indices",)

    def __init__(self, root_indices: tuple[int, ...]) -> None:
        self.root_indices = tuple(root_indices)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Conflict):
            return NotImplemented
        return self.root_indices == other.root_indices

    def __repr__(self) -> str:
        return f"Conflict(root_indices={self.root_indices!r})"


def _has_cycle(assignment: dict[str, Release]) -> bool:
    """True if the dependency graph of the selected releases has a cycle."""
    graph = {
        name: [dep.name for dep in release.dependencies
               if dep.name in assignment]
        for name, release in assignment.items()
    }
    WHITE, GRAY, BLACK = 0, 1, 2
    color = dict.fromkeys(graph, WHITE)

    def visit(node: str) -> bool:
        color[node] = GRAY
        for nxt in graph[node]:
            if color[nxt] == GRAY:
                return True
            if color[nxt] == WHITE and visit(nxt):
                return True
        color[node] = BLACK
        return False

    return any(color[node] == WHITE and visit(node) for node in graph)


def _search(catalog: Catalog, roots: list[RootRequest],
            targets: frozenset[str]) -> dict[str, Release] | None:
    """Return a valid assignment {name: Release}, or None if unsolvable."""
    constraints: dict[str, Constraint] = {}
    for request in roots:
        merged = constraints.get(request.name, Constraint.any())
        merged = merged.intersect(request.constraint)
        if merged.is_empty():
            return None
        constraints[request.name] = merged

    def recurse(assignment: dict[str, Release],
                constraints: dict[str, Constraint]) -> dict[str, Release] | None:
        pending = [name for name in constraints if name not in assignment]
        if not pending:
            return None if _has_cycle(assignment) else assignment

        def candidates(name: str) -> list[Release]:
            constraint = constraints[name]
            return [rel for rel in catalog.releases_of(name)
                    if rel.usable_on(targets)
                    and constraint.contains(rel.version)]

        # Branch on the component with the fewest usable candidates.
        name = min(pending, key=lambda n: len(candidates(n)))
        for release in sorted(candidates(name), key=lambda r: r.version,
                              reverse=True):
            next_constraints = dict(constraints)
            next_assignment = dict(assignment)
            next_assignment[name] = release
            ok = True
            for dep in release.dependencies:
                merged = next_constraints.get(dep.name, Constraint.any())
                merged = merged.intersect(dep.constraint)
                if merged.is_empty():
                    ok = False
                    break
                chosen = next_assignment.get(dep.name)
                if chosen is not None and not merged.contains(chosen.version):
                    ok = False
                    break
                next_constraints[dep.name] = merged
            if not ok:
                continue
            result = recurse(next_assignment, next_constraints)
            if result is not None:
                return result
        return None

    return recurse({}, constraints)


def resolve(catalog: Catalog, roots: list[RootRequest],
            targets: frozenset[str]) -> Solution | Conflict:
    """Resolve ``roots`` against ``catalog`` on every platform in ``targets``.

    Returns a Solution with one version per required component, or a
    Conflict naming an irreducible unsolvable subset of root positions.
    """
    if not targets:
        raise ValueError("targets must be a non-empty set of platforms")
    targets = frozenset(targets)

    found = _search(catalog, roots, targets)
    if found is not None:
        return Solution({name: rel.version for name, rel in found.items()})

    # Deletion-based minimization: the result is irreducible because
    # satisfiability is monotone under removing root requests.
    remaining = list(range(len(roots)))
    for index in list(remaining):
        trial = [i for i in remaining if i != index]
        trial_roots = [roots[i] for i in trial]
        if _search(catalog, trial_roots, targets) is None:
            remaining = trial
    return Conflict(tuple(remaining))
