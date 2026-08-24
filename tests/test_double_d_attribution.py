# SPDX-License-Identifier: Apache-2.0
"""Occurrence-safe defining evidence for principal-axis Double-D bores."""

from __future__ import annotations

import ast
import copy
from pathlib import Path

import pytest
from build123d import (
    Align,
    Box,
    Compound,
    Cylinder,
    GeomType,
    Pos,
    Rot,
    Shell,
    export_step,
    import_step,
)

from b123d_recognisers._adjacency import FaceEdges, FaceGraph, edge_face_map
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers.profiled_bores import (
    _discover_double_d_bores,
    _valid_wall_chain_facts,
    recognise_double_d_bores,
)
from b123d_recognisers.result import _take_inventory

_CENTRE = (Align.CENTER, Align.CENTER, Align.CENTER)


def _chain_facts(
    first: tuple[str, ...] = ("a",),
    *,
    first_intervals: dict[str, tuple[float, float]] | None = None,
    first_edges: tuple[tuple[str, str], ...] = (),
    high: tuple[int, ...] = (0, 1, 2, 3),
) -> bool:
    chains = (first, ("b",), ("c",), ("d",))
    intervals = {"b": (-5, 5), "c": (-5, 5), "d": (-5, 5)}
    intervals.update(first_intervals or {"a": (-5, 5)})
    ids = {name: at for at, name in enumerate(intervals)}
    return _valid_wall_chain_facts(
        tuple(tuple(ids[name] for name in chain) for chain in chains),
        high,
        {ids[name]: interval for name, interval in intervals.items()},
        tuple((ids[left], ids[right]) for left, right in first_edges),
        lo=-5,
        hi=5,
        tol=1e-6,
    )


def test_pure_wall_chain_reducer_accepts_full_and_consecutive_patch_roles() -> None:
    assert _chain_facts()
    assert _chain_facts(
        ("a0", "a1", "a2"),
        first_intervals={"a0": (-5, -1), "a1": (-1, 2), "a2": (2, 5)},
        first_edges=(("a0", "a1"), ("a1", "a2")),
    )


@pytest.mark.parametrize(
    ("first", "intervals", "edges", "high"),
    [
        (("a0", "a1"), {"a0": (-5, -1), "a1": (0, 5)}, (("a0", "a1"),), (0, 1, 2, 3)),
        (("a0", "a1"), {"a0": (-5, 1), "a1": (0, 5)}, (("a0", "a1"),), (0, 1, 2, 3)),
        (
            ("a0", "a1", "a2"),
            {"a0": (-5, -1), "a1": (-1, 2), "a2": (2, 5)},
            (("a0", "a1"), ("a1", "a2"), ("a0", "a2")),
            (0, 1, 2, 3),
        ),
        (
            ("a0", "a1"),
            {"a0": (-5, 0), "a1": (0, 5)},
            (("a0", "a1"), ("a0", "a1")),
            (0, 1, 2, 3),
        ),
        (("a",), {"a": (-5, 5)}, (), (0, 0, 2, 3)),
        (("a", "b"), {"a": (-5, 0)}, (("a", "b"),), (0, 1, 2, 3)),
    ],
)
def test_pure_wall_chain_reducer_refuses_gap_overlap_cycle_and_role_ambiguity(
    first, intervals, edges, high
) -> None:
    assert not _chain_facts(first, first_intervals=intervals, first_edges=edges, high=high)


def _qualified_calls(tree: ast.AST) -> list[tuple[str, ast.Call]]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                aliases[local] = alias.name if alias.asname else alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                aliases[alias.asname or alias.name] = f"{node.module}.{alias.name}"

    def name(node: ast.expr) -> str:
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            base = name(node.value)
            return f"{base}.{node.attr}" if base else node.attr
        return ""

    return [(name(node.func), node) for node in ast.walk(tree) if isinstance(node, ast.Call)]


def _tool(height: float = 20, *, across: float = 7.2):
    return Cylinder(5, height, align=_CENTRE) & Box(
        across, 20, 2 * height, align=_CENTRE
    )


def _plate():
    return Box(30, 30, 10, align=_CENTRE) - _tool()


def _claimed(part):
    public = recognise_double_d_bores(part)
    ledger = ClaimLedger(FaceGraph(part))
    records = _discover_double_d_bores(part, writer=ledger.writer)
    candidates = ledger.candidate_set_for(FamilyId.DOUBLE_D_BORES, records).candidates
    assert [type(record) for record in records] == [type(record) for record in public]
    assert records == public
    assert [record.to_dict() for record in records] == [record.to_dict() for record in public]
    assert len(candidates) == len(records)
    assert all(
        candidate.record is record
        for candidate, record in zip(candidates, records, strict=True)
    )
    return ledger, records, candidates


def _assert_wall_role(ledger, record, candidate) -> None:
    defining = ledger.defining_of(candidate)
    axis = next(at for at, value in enumerate(record.axis) if value)
    low = record.location[axis] - record.depth
    high = record.location[axis]
    metric_tol = record.major_diameter * 1e-3
    owner = ledger.graph.common_valid_solid(defining)
    assert owner is not None
    faces = [ledger.graph.face(node) for node in ledger.graph.nodes]
    incidence = edge_face_map(faces, face_edges=FaceEdges())

    def opening_sets(at: float) -> list[frozenset]:
        found: list[frozenset] = []
        for node in ledger.graph.nodes:
            if ledger.graph.common_valid_solid((node,)) is not owner:
                continue
            face = ledger.graph.face(node)
            if face.geom_type != GeomType.PLANE:
                continue
            bounds = ledger.graph.bounds(node)[axis]
            if abs(bounds[0] - at) > metric_tol or abs(bounds[1] - at) > metric_tol:
                continue
            for wire in face.inner_wires():
                edges = wire.edges()
                if len(edges) != 4:
                    continue
                center = wire.bounding_box().center()
                point = (float(center.X), float(center.Y), float(center.Z))
                if any(
                    abs(point[i] - record.location[i]) > metric_tol
                    for i in range(3)
                    if i != axis
                ):
                    continue
                partners = []
                for edge in edges:
                    others = [
                        other
                        for other in incidence.get(edge, ())
                        if not other.wrapped.IsSame(face.wrapped)
                    ]
                    assert len(others) == 1
                    partners.append(ledger.graph.require_node(others[0]))
                found.append(frozenset(partners))
        return found

    low_sets = opening_sets(low)
    high_sets = opening_sets(high)
    assert len(low_sets) == len(high_sets) == 1
    assert low_sets[0] == high_sets[0]
    expected = low_sets[0]
    assert expected == defining
    wall_faces = [ledger.graph.face(node) for node in expected]
    assert [face.geom_type for face in wall_faces].count(GeomType.PLANE) == 2
    assert [face.geom_type for face in wall_faces].count(GeomType.CYLINDER) == 2


@pytest.mark.parametrize("rotation", [Rot(), Rot(0, 90, 0), Rot(90, 0, 0)])
def test_each_principal_axis_issues_the_complete_wall_set(rotation) -> None:
    ledger, records, candidates = _claimed(rotation * _plate())
    assert len(records) == 1
    _assert_wall_role(ledger, records[0], candidates[0])


def test_multiple_occurrences_keep_sorted_record_identity_and_wall_ownership() -> None:
    part = Compound(
        [
            Pos(-30, 0, 0) * _plate(),
            Pos(30, 0, 0) * (Box(34, 34, 12, align=_CENTRE) - _tool(20, across=6.4)),
        ]
    )
    ledger, records, candidates = _claimed(part)
    assert len(records) == 2
    assert [record.location[0] for record in records] == [-30.0, 30.0]
    for record, candidate in zip(records, candidates, strict=True):
        _assert_wall_role(ledger, record, candidate)
    assert ledger.defining_of(candidates[0]).isdisjoint(ledger.defining_of(candidates[1]))


def test_equal_full_records_from_distinct_solids_remain_identity_distinct() -> None:
    first = _plate()
    part = Compound([first, copy.deepcopy(first)])
    ledger, records, candidates = _claimed(part)
    assert len(records) == len(candidates) == 2
    assert records[0] == records[1] and records[0] is not records[1]
    assert candidates[0].record is records[0]
    assert candidates[1].record is records[1]
    for record, candidate in zip(records, candidates, strict=True):
        _assert_wall_role(ledger, record, candidate)
    assert ledger.defining_of(candidates[0]).isdisjoint(ledger.defining_of(candidates[1]))
    owners = [
        ledger.graph.common_valid_solid(ledger.defining_of(candidate))
        for candidate in candidates
    ]
    assert owners[0] is not owners[1]


@pytest.mark.parametrize(
    "part",
    [
        Pos(17, -9, 4) * _plate(),
        _plate().mirror(),
        _plate().scale(0.1),
        _plate().scale(10),
    ],
)
def test_transform_and_scale_routes_keep_exact_wall_roles(part) -> None:
    ledger, records, candidates = _claimed(part)
    assert len(records) == 1
    _assert_wall_role(ledger, records[0], candidates[0])


def test_step_round_trip_retains_original_imported_wall_roles(tmp_path) -> None:
    target = tmp_path / "double-d.step"
    assert export_step(_plate(), target)
    imported = import_step(target)
    ledger, records, candidates = _claimed(imported)
    assert len(records) == 1
    _assert_wall_role(ledger, records[0], candidates[0])


def test_aggregate_inventory_publishes_terminal_double_d_wall_evidence() -> None:
    product = _take_inventory(_plate())
    candidates = product.physical.candidate_set(FamilyId.DOUBLE_D_BORES).candidates
    assert tuple(candidate.record for candidate in candidates) == product.result.double_d_bores
    assert product.accepted.candidate_set(FamilyId.DOUBLE_D_BORES).candidates == candidates
    assert len(candidates) == 1
    assert len(product.evidence.defining_of(candidates[0])) == 4


@pytest.mark.parametrize(
    "part",
    [
        Box(30, 30, 10, align=_CENTRE) - Pos(0, 0, 3) * _tool(4),
        Rot(0, 15, 0) * _plate(),
    ],
)
def test_rejected_geometry_issues_no_candidate(part) -> None:
    ledger = ClaimLedger(FaceGraph(part))
    assert _discover_double_d_bores(part, writer=ledger.writer) == []
    assert ledger.candidate_set_for(FamilyId.DOUBLE_D_BORES, ()).candidates == ()


def test_late_body_validation_failure_leaves_no_prefix(monkeypatch) -> None:
    part = Pos(-20, 0, 0) * _plate() + Pos(20, 0, 0) * _plate()
    ledger = ClaimLedger(FaceGraph(part))
    original = ledger.graph.common_valid_solid
    calls = 0

    def fail_second(nodes):
        nonlocal calls
        calls += 1
        return original(nodes) if calls == 1 else None

    monkeypatch.setattr(ledger.graph, "common_valid_solid", fail_second)
    with pytest.raises(ValueError, match="one valid owner solid"):
        _discover_double_d_bores(part, writer=ledger.writer)
    assert ledger.candidate_set_for(FamilyId.DOUBLE_D_BORES, ()).candidates == ()


def test_late_binding_failure_leaves_no_prefix(monkeypatch) -> None:
    part = Compound([Pos(-30, 0, 0) * _plate(), Pos(30, 0, 0) * _plate()])
    ledger = ClaimLedger(FaceGraph(part))
    original = ledger.graph.require_node
    calls = 0

    def fail_late(face):
        nonlocal calls
        calls += 1
        if calls > 4:
            raise ValueError("late binding refusal")
        return original(face)

    monkeypatch.setattr(ledger.graph, "require_node", fail_late)
    with pytest.raises(ValueError, match="late binding refusal"):
        _discover_double_d_bores(part, writer=ledger.writer)
    assert ledger.candidate_set_for(FamilyId.DOUBLE_D_BORES, ()).candidates == ()


def test_cross_occurrence_wall_reuse_refuses_before_publication(monkeypatch) -> None:
    import b123d_recognisers.profiled_bores as module

    part = Compound([Pos(-30, 0, 0) * _plate(), Pos(30, 0, 0) * _plate()])
    ledger = ClaimLedger(FaceGraph(part))
    original = module._complete_wall_component
    first = None

    def reuse_first(*args, **kwargs):
        nonlocal first
        walls = original(*args, **kwargs)
        if first is None:
            first = walls
        return first

    monkeypatch.setattr(module, "_complete_wall_component", reuse_first)
    with pytest.raises(ValueError, match="assigned across occurrences"):
        _discover_double_d_bores(part, writer=ledger.writer)
    assert ledger.candidate_set_for(FamilyId.DOUBLE_D_BORES, ()).candidates == ()


def test_repeated_same_wall_reference_collapses_once(monkeypatch) -> None:
    import b123d_recognisers.profiled_bores as module

    part = _plate()
    ledger = ClaimLedger(FaceGraph(part))
    original = module._complete_wall_component

    def repeated(*args, **kwargs):
        walls = original(*args, **kwargs)
        return (*walls, walls[0])

    monkeypatch.setattr(module, "_complete_wall_component", repeated)
    records = _discover_double_d_bores(part, writer=ledger.writer)
    candidate = ledger.candidate_set_for(FamilyId.DOUBLE_D_BORES, records).candidates[0]
    assert len(ledger.defining_of(candidate)) == 4


@pytest.mark.parametrize("translated", [False, True])
def test_deep_or_translated_wall_clone_refuses_before_publication(
    monkeypatch, translated: bool
) -> None:
    import b123d_recognisers.profiled_bores as module

    part = _plate()
    ledger = ClaimLedger(FaceGraph(part))
    original = module._complete_wall_component

    def cloned(*args, **kwargs):
        walls = original(*args, **kwargs)
        changed = [copy.deepcopy(face) for face in walls]
        if translated:
            changed = [face.translate((1, 0, 0)) for face in changed]
        return tuple(changed)

    monkeypatch.setattr(module, "_complete_wall_component", cloned)
    with pytest.raises(ValueError):
        _discover_double_d_bores(part, writer=ledger.writer)
    assert ledger.candidate_set_for(FamilyId.DOUBLE_D_BORES, ()).candidates == ()


def test_open_shell_keeps_public_compatibility_but_refuses_aggregate() -> None:
    shell = Shell(_plate().faces())
    assert len(recognise_double_d_bores(shell)) == 1
    ledger = ClaimLedger(FaceGraph(shell))
    with pytest.raises(ValueError, match="one valid owner solid"):
        _discover_double_d_bores(shell, writer=ledger.writer)
    assert ledger.candidate_set_for(FamilyId.DOUBLE_D_BORES, ()).candidates == ()


def test_foreign_writer_refuses_before_publication() -> None:
    part = _plate()
    foreign = ClaimLedger(FaceGraph(Pos(50, 0, 0) * _plate()))
    with pytest.raises(ValueError, match="different part|does not belong"):
        _discover_double_d_bores(part, writer=foreign.writer)
    assert foreign.candidate_set_for(FamilyId.DOUBLE_D_BORES, ()).candidates == ()


def test_only_registry_may_call_writer_enabled_core() -> None:
    root = Path(__file__).parents[1]
    sites: list[tuple[str, bool]] = []
    importers: list[str] = []
    for path in (root / "src").rglob("*.py"):
        if path.name == "profiled_bores.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            isinstance(node, ast.ImportFrom)
            and node.module == "b123d_recognisers.profiled_bores"
            and any(alias.name == "_discover_double_d_bores" for alias in node.names)
            for node in ast.walk(tree)
        ):
            importers.append(path.name)
        for qualified, node in _qualified_calls(tree):
            if qualified == "b123d_recognisers.profiled_bores._discover_double_d_bores":
                sites.append(
                    (
                        path.name,
                        any(
                            keyword.arg == "writer" and ast.unparse(keyword.value) == "s.writer"
                            for keyword in node.keywords
                        ),
                    )
                )
    assert importers == ["_registry.py"]
    assert sites == [("_registry.py", True)]


def test_constructor_and_void_prism_path_roster_is_closed() -> None:
    path = Path(__file__).parents[1] / "src/b123d_recognisers/profiled_bores.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    sites: list[tuple[str, str]] = []
    for qualified, node in _qualified_calls(tree):
        if qualified in {"DoubleDBore", "build123d.Solid.extrude"}:
            function = next(
                (
                    parent.name
                    for parent in ast.walk(tree)
                    if isinstance(parent, ast.FunctionDef) and node in ast.walk(parent)
                ),
                "",
            )
            sites.append((qualified, function))
    assert sites == [
        ("DoubleDBore", "double_d_bores_from_openings"),
        ("build123d.Solid.extrude", "double_d_bores_from_openings"),
        ("build123d.Solid.extrude", "read_double_d_tool"),
    ]
