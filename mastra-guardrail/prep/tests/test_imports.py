"""The cheap guard on the whole build (spec §1's DAG, §14).

Walks every module directly inside `mastra_prep/` with `ast` — never executing
or importing them — and asserts:

  * `test_no_circular_imports`     — the intra-package import graph is acyclic,
                                      and `budget.py`/`logging_.py` (the two
                                      pinned leaves) import nothing intra-package.
  * `test_never_imports_carver_showcase` — no module imports `carver_showcase`
                                      (goal #13 — different repo, different venv).
  * `test_no_stdlib_shadowing`     — no module is named `logging`/`json`/`types`
                                      (why `logging_.py` carries its underscore).

This is a static analysis over source text. It costs nothing to run and does
not require `mastra_prep/__init__.py` (or any module) to exist yet — an empty
package has an empty, trivially acyclic graph, and stays green as later phases
add modules.
"""
from __future__ import annotations

import ast
from pathlib import Path

PACKAGE_NAME = "mastra_prep"
PACKAGE_DIR = Path(__file__).resolve().parents[1] / PACKAGE_NAME

# stdlib module names a project module must never shadow by taking their name
# (an intra-package `import logging` would otherwise resolve to our own file).
STDLIB_SHADOW_NAMES = frozenset({"logging", "json", "types"})

# The two modules the spec pins as leaves with an EMPTY intra-package import set.
PINNED_EMPTY_LEAVES = ("budget", "logging_")

FORBIDDEN_IMPORT_ROOT = "carver_showcase"


def _iter_module_files(package_dir: Path = PACKAGE_DIR):
    """Yield (module_name, path) for every top-level `.py` file in `package_dir`.

    Excludes `__init__.py` itself (it has no "module name" distinct from the
    package). Silently yields nothing if `package_dir` does not exist yet.
    """
    if not package_dir.is_dir():
        return
    for path in sorted(package_dir.glob("*.py")):
        if path.stem == "__init__":
            continue
        yield path.stem, path


def _parse_imports(path: Path) -> tuple[set[str], set[str]]:
    """Return (intra_package_module_names, all_imported_root_names) for one file.

    `intra_package_module_names` is the set of sibling `mastra_prep` module
    names this file imports directly, resolved from both relative imports
    (`from .foo import bar`, `from . import foo`) and absolute
    `mastra_prep.foo`-style imports. `all_imported_root_names` is every
    top-level import root the file references at all (used for the
    `carver_showcase` ban, which must catch `import carver_showcase` and
    `from carver_showcase import x` alike).
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    intra: set[str] = set()
    all_roots: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                all_roots.add(parts[0])
                if parts[0] == PACKAGE_NAME and len(parts) > 1:
                    intra.add(parts[1])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 1:
                # single-dot relative import (`from .foo import bar`,
                # `from . import foo`): intra-package by definition, since
                # every module here lives directly inside mastra_prep/ with
                # no subpackages. `level >= 2` (`from ..x import y`) instead
                # ESCAPES mastra_prep entirely and must not be counted as a
                # sibling edge — miscounting it could mask a real violation
                # (an escape import) as an ordinary intra-package one, or
                # falsely trip the pinned-leaf assertion.
                if node.module:
                    sibling = node.module.split(".")[0]
                    intra.add(sibling)
                    all_roots.add(sibling)
                else:
                    # `from . import foo[, bar]`
                    for alias in node.names:
                        intra.add(alias.name)
                        all_roots.add(alias.name)
            elif node.module:
                parts = node.module.split(".")
                all_roots.add(parts[0])
                if parts[0] == PACKAGE_NAME:
                    if len(parts) > 1:
                        # from mastra_prep.foo import bar
                        intra.add(parts[1])
                    else:
                        # from mastra_prep import foo[, bar] — each imported
                        # name IS a sibling module, same shape as `from . import foo`
                        for alias in node.names:
                            intra.add(alias.name)

    return intra, all_roots


def _build_import_graph(package_dir: Path = PACKAGE_DIR) -> dict[str, set[str]]:
    """Map each `mastra_prep` module name to the sibling module names it imports."""
    graph: dict[str, set[str]] = {}
    for module_name, path in _iter_module_files(package_dir):
        intra, _ = _parse_imports(path)
        graph[module_name] = intra
    return graph


def _find_cycle(graph: dict[str, set[str]]) -> list[str] | None:
    """Return one cycle as a list of module names (closed: first == last), or None.

    Standard 3-color DFS. Edges to names absent from `graph` (a module that
    imports a sibling which does not exist yet, or an external package) are
    ignored — they cannot participate in an intra-package cycle by definition.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {name: WHITE for name in graph}
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        color[node] = GRAY
        stack.append(node)
        for neighbor in graph.get(node, ()):
            if neighbor not in graph:
                continue
            if color[neighbor] == GRAY:
                start = stack.index(neighbor)
                return stack[start:] + [neighbor]
            if color[neighbor] == WHITE:
                found = visit(neighbor)
                if found:
                    return found
        stack.pop()
        color[node] = BLACK
        return None

    for node in graph:
        if color[node] == WHITE:
            found = visit(node)
            if found:
                return found
    return None


def test_no_circular_imports():
    # The package directory itself must exist — a MISSING directory would
    # otherwise make this guard vouch vacuously for a build that was never
    # inspected (distinct from an existing-but-still-empty package, which is
    # the expected, intentionally-green state before Phase 1's modules land).
    assert PACKAGE_DIR.is_dir(), f"{PACKAGE_DIR} does not exist"

    graph = _build_import_graph()

    cycle = _find_cycle(graph)
    assert cycle is None, f"circular import detected: {' -> '.join(cycle)}"

    for leaf in PINNED_EMPTY_LEAVES:
        if leaf in graph:
            assert graph[leaf] == set(), (
                f"{leaf}.py must be a leaf with an empty intra-package import "
                f"set, but imports: {sorted(graph[leaf])}"
            )


def test_never_imports_carver_showcase():
    offenders = []
    for module_name, path in _iter_module_files():
        _, all_roots = _parse_imports(path)
        if FORBIDDEN_IMPORT_ROOT in all_roots:
            offenders.append(module_name)
    assert not offenders, (
        f"module(s) import forbidden '{FORBIDDEN_IMPORT_ROOT}' (goal #13 — "
        f"different repo, different venv): {offenders}"
    )


def test_no_stdlib_shadowing():
    offenders = [
        module_name
        for module_name, _ in _iter_module_files()
        if module_name in STDLIB_SHADOW_NAMES
    ]
    assert not offenders, (
        f"module name(s) shadow stdlib modules, breaking `import {{name}}` "
        f"inside the package: {offenders}"
    )
