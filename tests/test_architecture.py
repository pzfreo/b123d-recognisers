# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

import ast
import importlib
import typing
from pathlib import Path

import b123d_recognisers as recognition

ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "src" / "b123d_recognisers"

PUBLIC_MODULES = {
    "angled_steps",
    "capabilities",
    "census",
    "chamfers",
    "countersinks",
    "fillets",
    "flats",
    "grooves",
    "levels",
    "pads",
    "passages",
    "plates",
    "polygonal_bosses",
    "profiled_bores",
    "repeating_profiles",
    "result",
    "slots",
    "turned",
}

MODULE_SEAM_EDGES = {
    # Base layer: the kernel, the shared type aliases, and `_geometry`'s alignment threshold.
    "_adjacency": {"_geometry", "_typing"},
    # Interpretation depends on geometric fact; the reverse edge is what keeps `FaceGraph`
    # immutable, so it must stay absent.
    "_claims": {"_adjacency"},
    "_cylinder_substrate": {"_geometry", "_typing"},
    "_hole_features": {
        "_adjacency",
        "_cylinder_substrate",
        "_geometry",
        "_record",
        "_typing",
        "countersinks",
    },
    "_pattern_geometry": {"_geometry"},
    "_hole_patterns": {"_hole_features", "_pattern_geometry", "_record", "_typing"},
    "_recess_records": {"_record", "_typing"},
    "_recess_core": {"_adjacency", "_geometry", "_recess_records", "_typing"},
    "_recess_features": {"_adjacency", "_claims", "_recess_core", "_recess_records", "_typing"},
    # The reconciler names both families it decides between, so it sits above them and neither
    # sits above it -- a recogniser importing this is the order dependence ADR 0003 forbids.
    "_reconcile": {"_claims", "_recess_records", "_typing", "passages"},
    "_recess_patterns": {"_pattern_geometry", "_recess_records"},
}


def _package_import_graph() -> dict[str, set[str]]:
    paths = {path.stem: path for path in PACKAGE.glob("*.py")}
    graph: dict[str, set[str]] = {module: set() for module in paths}
    package = "b123d_recognisers"
    prefix = f"{package}."
    for module, path in paths.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == package:
                # `from b123d_recognisers import chamfers` names the module as an alias, not in
                # node.module. Reading only node.module made this form invisible, so a seam or
                # cycle violation written this way passed every check in this file.
                names = [f"{prefix}{alias.name}" for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            elif isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            else:
                continue
            for name in names:
                if name.startswith(prefix) and (target := name.removeprefix(prefix)) in paths:
                    graph[module].add(target)
    return graph


def test_runtime_package_does_not_import_draftwright():
    violations = []
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(name == "draftwright" or name.startswith("draftwright.") for name in names):
                violations.append(f"{path.name}:{node.lineno}")
    assert violations == []


def test_every_defined_public_recogniser_is_exported_and_snapshotted():
    defined = set()
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        defined.update(
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("recognise_")
        )

    exported = {name for name in recognition.__all__ if name.startswith("recognise_")}
    assert exported == defined


def test_module_graph_is_acyclic() -> None:
    graph = _package_import_graph()
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(module: str, path: tuple[str, ...] = ()) -> None:
        assert module not in visiting, " -> ".join((*path, module))
        if module in visited:
            return
        visiting.add(module)
        for dependency in sorted(graph[module]):
            visit(dependency, (*path, module))
        visiting.remove(module)
        visited.add(module)

    for module in sorted(graph):
        visit(module)


def test_internal_module_seams_match_adr_0007() -> None:
    """No module may import outside the seam ADR 0007 allows it.

    A containment check, not equality. The invariant is that nothing reaches across a seam;
    whether a module happens to use every import it is permitted is an implementation detail,
    and requiring exact equality turned "this function no longer needs that helper" into a
    test failure.
    """

    graph = _package_import_graph()

    crossings = {
        module: sorted(graph[module] - allowed)
        for module, allowed in MODULE_SEAM_EDGES.items()
        if graph[module] - allowed
    }
    assert crossings == {}


def test_no_accidental_public_modules() -> None:
    modules = {path.stem for path in PACKAGE.glob("*.py") if path.stem != "__init__"}
    public = {module for module in modules if not module.startswith("_")}

    assert public == PUBLIC_MODULES
    assert set(MODULE_SEAM_EDGES) <= modules


def test_compatibility_facades_preserve_export_identity_and_module_paths() -> None:
    feature_facade = importlib.import_module("b123d_recognisers._features")
    recess_facade = importlib.import_module("b123d_recognisers.slots")
    implementations = {
        **{
            name: importlib.import_module("b123d_recognisers._cylinder_substrate")
            for name in ("analyse_cylinders", "full_cylinders")
        },
        **{
            name: importlib.import_module("b123d_recognisers._hole_features")
            for name in (
                "BossRecord",
                "CounterBore",
                "HoleRecord",
                "feature_diameters",
                "recognise_bosses",
                "recognise_holes",
            )
        },
        **{
            name: importlib.import_module("b123d_recognisers._hole_patterns")
            for name in (
                "BoltCircle",
                "HoleSpec",
                "LinearArray",
                "RectGrid",
                "recognise_hole_patterns",
            )
        },
    }
    for name, implementation in implementations.items():
        assert getattr(recognition, name) is getattr(feature_facade, name)
        assert getattr(feature_facade, name) is getattr(implementation, name)
        assert getattr(recognition, name).__module__ == "b123d_recognisers._features"

    # The property that matters is that a consumer can resolve these annotations after the
    # move, not that they are spelled with particular characters. Comparing the literal strings
    # made `tuple[float, ...] | None` and an equivalent spelling of the same type a test
    # failure, while a genuinely unresolvable annotation would have passed.
    for name in ("Channel", "Pocket", "Slot"):
        hints = typing.get_type_hints(getattr(recognition, name))
        assert "width_axis" in hints
    assert typing.get_type_hints(recognition.recognise_slots)

    recess_records = importlib.import_module("b123d_recognisers._recess_records")
    recess_features = importlib.import_module("b123d_recognisers._recess_features")
    recess_patterns = importlib.import_module("b123d_recognisers._recess_patterns")
    for name in ("Channel", "Pocket", "PocketArray", "PocketGrid", "Slot", "SlotArray", "SlotGrid"):
        assert getattr(recognition, name) is getattr(recess_facade, name)
        assert getattr(recess_facade, name) is getattr(recess_records, name)
        assert getattr(recognition, name).__module__ == "b123d_recognisers.slots"
    for name in ("recognise_channels", "recognise_pockets", "recognise_slots"):
        assert getattr(recognition, name) is getattr(recess_facade, name)
        assert getattr(recess_facade, name) is getattr(recess_features, name)
        assert getattr(recognition, name).__module__ == "b123d_recognisers.slots"
    for name in ("recognise_pocket_patterns", "recognise_slot_patterns"):
        assert getattr(recognition, name) is getattr(recess_facade, name)
        assert getattr(recess_facade, name) is getattr(recess_patterns, name)
        assert getattr(recognition, name).__module__ == "b123d_recognisers.slots"
    for name in (
        "BoltCircle",
        "BossRecord",
        "CounterBore",
        "HoleRecord",
        "HoleSpec",
        "LinearArray",
        "RectGrid",
    ):
        assert getattr(recognition, name).__module__ == "b123d_recognisers._features"

    moved_records = (
        "BoltCircle",
        "BossRecord",
        "Channel",
        "CounterBore",
        "HoleRecord",
        "HoleSpec",
        "LinearArray",
        "Pocket",
        "PocketArray",
        "PocketGrid",
        "RectGrid",
        "Slot",
        "SlotArray",
        "SlotGrid",
    )
    for name in moved_records:
        assert typing.get_type_hints(getattr(recognition, name))


def test_recess_families_keep_one_shared_face_inventory_and_patterns_are_pure() -> None:
    core = ast.parse(
        (PACKAGE / "_recess_core.py").read_text(encoding="utf-8"),
        filename="_recess_core.py",
    )
    functions = {
        node.name: node for node in core.body if isinstance(node, ast.FunctionDef)
    }
    for name in ("_recognise_slots_one", "_recognise_pockets_one", "_recognise_channels_one"):
        scans = [
            node
            for node in ast.walk(functions[name])
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_planar_faces"
        ]
        assert len(scans) == 1, name

    for module_name in ("_hole_patterns.py", "_pattern_geometry.py", "_recess_patterns.py"):
        tree = ast.parse(
            (PACKAGE / module_name).read_text(encoding="utf-8"), filename=module_name
        )
        topology_reads = [
            node.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Attribute)
            and node.attr in {"edges", "faces", "solids"}
        ]
        assert topology_reads == [], module_name
