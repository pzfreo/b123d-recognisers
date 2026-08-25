"""Issue #236 Pocket evidence lifecycle and closed failure boundaries."""

from __future__ import annotations

import ast
import inspect
from copy import deepcopy
from pathlib import Path

import pytest
from build123d import Box, Compound, Cylinder, Plane, Pos, Rot

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._recess_features import _discover_pockets, _PocketAttributionError
from b123d_recognisers._registry import PHYSICAL_DEFINITIONS, FullyAttributed

ROOT = Path(__file__).parents[1]


def _obround(length: float, width: float, depth: float):
    end = Cylinder(width / 2, depth)
    return Box(length, width, depth) + Pos(-length / 2, 0, 0) * end + Pos(
        length / 2, 0, 0
    ) * end


@pytest.mark.parametrize(
    ("part", "planar", "curved"),
    [
        (Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8), 2, 0),
        (Box(60, 40, 12) - Pos(25, 15, 4) * Box(20, 20, 8), 3, 0),
        (Box(80, 50, 14) - Pos(0, 0, 4) * _obround(30, 10, 10), 2, 2),
        (Box(60, 40, 12) - Pos(0, 0, 4) * _obround(3, 10, 8), 0, 2),
    ],
)
def test_route_selected_sources_are_complete_and_one_body(part, planar, curved) -> None:
    ledger = ClaimLedger(FaceGraph(part))
    records = _discover_pockets(part, writer=ledger.writer)
    candidates = ledger.candidate_set(FamilyId.POCKETS).candidates
    assert len(records) == len(candidates) == 1
    assert candidates[0].record is records[0]
    nodes = ledger.defining_of(candidates[0])
    assert sum(ledger.graph.is_planar(node) for node in nodes) == planar
    assert sum(not ledger.graph.is_planar(node) for node in nodes) == curved
    assert ledger.graph.common_valid_solid(nodes) is not None


def test_equal_coincident_bodies_remain_distinct_occurrences() -> None:
    pocket = Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)
    part = Compound([pocket, deepcopy(pocket)])
    ledger = ClaimLedger(FaceGraph(part))
    records = _discover_pockets(part, writer=ledger.writer)
    candidates = ledger.candidate_set(FamilyId.POCKETS).candidates
    assert len(records) == len(candidates) == 2
    assert all(
        candidate.record is record
        for candidate, record in zip(candidates, records, strict=True)
    )


def test_foreign_graph_refuses_without_prefix() -> None:
    part = Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)
    ledger = ClaimLedger(FaceGraph(Pos(100, 0, 0) * part))
    with pytest.raises(_PocketAttributionError, match="identity"):
        _discover_pockets(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.POCKETS).candidates == ()


def test_unexpected_geometry_value_error_is_not_relabelled(monkeypatch) -> None:
    import b123d_recognisers._recess_features as module

    part = Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)
    ledger = ClaimLedger(FaceGraph(part))

    def fail(*args, **kwargs):
        raise ValueError("geometry defect")

    monkeypatch.setattr(module, "_body_scoped_proposals", fail)
    with pytest.raises(ValueError, match="geometry defect"):
        _discover_pockets(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.POCKETS).candidates == ()


@pytest.mark.parametrize(
    "part",
    [
        Pos(17, -23, 11) * (Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)),
        Rot(90, 0, 0) * (Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)),
        Rot(0, 90, 0) * (Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)),
        (Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)).mirror(Plane.YZ),
        (Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)).scale(0.2),
        (Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)).scale(5),
    ],
)
def test_axis_transform_mirror_and_scale_keep_writer_parity(part) -> None:
    ledger = ClaimLedger(FaceGraph(part))
    written = _discover_pockets(part, writer=ledger.writer)
    plain = _discover_pockets(part)
    assert [item.to_dict() for item in written] == [item.to_dict() for item in plain]
    assert len(written) == len(ledger.candidate_set(FamilyId.POCKETS).candidates) == 1


@pytest.mark.parametrize(
    "part",
    [
        Box(60, 40, 12) - Box(20, 12, 12),  # through Slot: zero floors
        Box(60, 40, 12) - Cylinder(5, 12),  # full cylinder
        Box(60, 40, 12),
        Box(60, 40, 12) - Pos(0, 0, 4) * Box(60, 12, 8),  # full-span Channel
    ],
)
def test_non_pocket_routes_have_no_candidate_or_prefix(part) -> None:
    ledger = ClaimLedger(FaceGraph(part))
    assert _discover_pockets(part, writer=ledger.writer) == []
    assert ledger.candidate_set(FamilyId.POCKETS).candidates == ()


def test_private_writer_roster_and_prohibited_reads_are_closed_alias_aware() -> None:
    package = ROOT / "src/b123d_recognisers"
    calls = []
    importers = []
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        aliases = {"_discover_pockets"}
        modules = set()
        for statement in tree.body:
            if isinstance(statement, ast.ImportFrom) and statement.module:
                for alias in statement.names:
                    if alias.name == "_discover_pockets":
                        aliases.add(alias.asname or alias.name)
                        importers.append(path.name)
            elif isinstance(statement, ast.Import):
                for alias in statement.names:
                    if alias.name == "b123d_recognisers._recess_features":
                        modules.add(alias.asname or alias.name)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            direct = isinstance(node.func, ast.Name) and node.func.id in aliases
            qualified = (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "_discover_pockets"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in modules
            )
            if direct or qualified:
                calls.append((path.name, node))
    assert importers == ["_registry.py"]
    assert {path for path, _call in calls} == {"_registry.py", "_recess_features.py"}
    registry_call = next(call for path, call in calls if path == "_registry.py")
    keywords = {keyword.arg: keyword.value for keyword in registry_call.keywords}
    writer = keywords["writer"]
    assert isinstance(writer, ast.Attribute) and writer.attr == "writer"
    assert isinstance(writer.value, ast.Name) and writer.value.id == "s"
    assert tuple(inspect.signature(_discover_pockets).parameters) == (
        "part",
        "face_edges",
        "graph",
        "writer",
        "_wrap_errors",
    )
    definition = next(item for item in PHYSICAL_DEFINITIONS if item.family is FamilyId.POCKETS)
    assert isinstance(definition.attribution, FullyAttributed)
    source = (package / "_recess_features.py").read_text(encoding="utf-8")
    for forbidden in (
        "CandidateSet",
        "EvidenceIndex",
        "InventoryProduct",
        "ReconciliationResult",
        "CompletedInputs",
    ):
        assert forbidden not in source
