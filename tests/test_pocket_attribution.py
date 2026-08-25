"""Issue #236 Pocket evidence lifecycle and closed failure boundaries."""

from __future__ import annotations

import ast
import inspect
from copy import deepcopy
from pathlib import Path

import pytest
from build123d import Box, Compound, Cylinder, Edge, Plane, Pos, Rot, export_step, import_step
from OCP.BRepFeat import BRepFeat_SplitShape

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._recess_features import _discover_pockets, _PocketAttributionError
from b123d_recognisers._registry import PHYSICAL_DEFINITIONS, FullyAttributed

ROOT = Path(__file__).parents[1]


def _obround(length: float, width: float, depth: float):
    end = Cylinder(width / 2, depth)
    return Box(length, width, depth) + Pos(-length / 2, 0, 0) * end + Pos(length / 2, 0, 0) * end


@pytest.mark.parametrize(
    ("part", "planar", "curved", "expected"),
    [
        (
            Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8),
            2,
            0,
            ("y", "x", 12.0, 20.0, 6.0, 0.0, -10.0, 10.0, 0.0, 6.0, 1, False),
        ),
        (
            Box(60, 40, 12) - Pos(25, 15, 4) * Box(20, 20, 8),
            3,
            0,
            ("x", "y", 15.0, 15.0, 6.0, 22.5, 5.0, 20.0, 0.0, 6.0, 1, True),
        ),
        (
            Box(80, 50, 14) - Pos(0, 0, 4) * _obround(30, 10, 10),
            2,
            2,
            ("y", "x", 10.0, 40.0, 8.0, 0.0, -20.0, 20.0, -1.0, 7.0, 1, False),
        ),
        (
            Box(60, 40, 12) - Pos(0, 0, 4) * _obround(3, 10, 8),
            0,
            2,
            ("y", "x", 10.0, 13.0, 6.0, 0.0, -6.5, 6.5, 0.0, 6.0, 1, False),
        ),
    ],
)
def test_route_selected_sources_are_complete_and_one_body(part, planar, curved, expected) -> None:
    ledger = ClaimLedger(FaceGraph(part))
    records = _discover_pockets(part, writer=ledger.writer)
    candidates = ledger.candidate_set(FamilyId.POCKETS).candidates
    assert len(records) == len(candidates) == 1
    assert candidates[0].record is records[0]
    record = records[0]
    assert (
        record.width_axis,
        record.long_axis,
        record.width,
        record.length,
        record.depth,
        record.w_center,
        record.lo,
        record.hi,
        record.d_lo,
        record.d_hi,
        record.open_sign,
        record.edge_anchored,
    ) == expected
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
        candidate.record is record for candidate, record in zip(candidates, records, strict=True)
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


def test_step_split_obround_cap_publishes_every_original_patch(tmp_path: Path) -> None:
    """Select the physical cap from fresh topology before writer/Candidate inspection."""

    part = Box(80, 50, 14) - Pos(0, 0, 4) * _obround(30, 10, 10)
    graph = FaceGraph(part)
    curved = [node for node in graph.nodes if not graph.is_planar(node)]
    assert len(curved) == 2
    cap = max(curved, key=lambda node: graph.bounds(node)[0][1])
    face = graph.face(cap)
    bounds = face.bounding_box()
    seam = Edge.make_line((20, 0, bounds.min.Z), (20, 0, bounds.max.Z))
    splitter = BRepFeat_SplitShape(part.wrapped)
    splitter.Add(seam.wrapped, face.wrapped)
    splitter.Build()
    assert splitter.IsDone()
    split = type(part).cast(splitter.Shape())
    path = tmp_path / "pocket-split-cap.step"
    assert export_step(split, path)
    imported = import_step(path)
    fresh = FaceGraph(imported)
    expected_curved = frozenset(node for node in fresh.nodes if not fresh.is_planar(node))
    assert len(expected_curved) == 3
    ledger = ClaimLedger(fresh)
    (record,) = _discover_pockets(imported, writer=ledger.writer)
    (candidate,) = ledger.candidate_set(FamilyId.POCKETS).candidates
    defining = ledger.defining_of(candidate)
    assert candidate.record is record
    assert expected_curved.issubset(defining)
    assert sum(fresh.is_planar(node) for node in defining) == 2


def test_reversed_face_traversal_preserves_records_and_roles(monkeypatch) -> None:
    part = Box(60, 40, 12) - Pos(25, 15, 4) * Box(20, 20, 8)

    def run():
        ledger = ClaimLedger(FaceGraph(part))
        records = _discover_pockets(part, writer=ledger.writer)
        roles = [
            frozenset(ledger.graph.face(node) for node in ledger.defining_of(candidate))
            for candidate in ledger.candidate_set(FamilyId.POCKETS).candidates
        ]
        return records, roles

    before_records, before_roles = run()
    original = type(part).faces
    monkeypatch.setattr(type(part), "faces", lambda self: list(reversed(original(self))))
    after_records, after_roles = run()
    assert [record.to_dict() for record in after_records] == [
        record.to_dict() for record in before_records
    ]
    assert len(before_roles) == len(after_roles)
    for before, after in zip(before_roles, after_roles, strict=True):
        assert all(any(face.is_same(other) for other in after) for face in before)


def test_checked_1000_shared_walls_are_distinct_same_solid_occurrences() -> None:
    part = import_step(ROOT / "tests/corpus/mfcadpp/1000.step")
    ledger = ClaimLedger(FaceGraph(part))
    public = _discover_pockets(part)
    records = _discover_pockets(part, writer=ledger.writer)
    candidates = ledger.candidate_set(FamilyId.POCKETS).candidates
    assert len(records) == len(candidates) == 11
    assert [record.to_dict() for record in records] == [record.to_dict() for record in public]
    assert all(
        candidate.record is record for candidate, record in zip(candidates, records, strict=True)
    )
    roles = [ledger.defining_of(candidate) for candidate in candidates]
    overlaps = {
        (left, right): roles[left] & roles[right]
        for left in range(len(roles))
        for right in range(left + 1, len(roles))
        if roles[left] & roles[right]
    }
    assert set(overlaps) == {(0, 9), (2, 9), (3, 10), (5, 10)}
    assert all(len(nodes) == 1 for nodes in overlaps.values())
    owners = [ledger.graph.common_valid_solid(nodes) for nodes in roles]
    assert owners[0] is not None and all(owner == owners[0] for owner in owners)


def test_same_record_competing_bound_role_sets_refuse_without_prefix(monkeypatch) -> None:
    import b123d_recognisers._recess_features as module
    from b123d_recognisers._recess_reduce import _RecessProposal

    part = Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)
    graph = FaceGraph(part)
    record = _discover_pockets(part)[0]
    planar = [node for node in graph.nodes if graph.is_planar(node)]
    proposals = [
        _RecessProposal(record, frozenset(planar[:2])),
        _RecessProposal(record, frozenset(planar[2:4])),
    ]
    monkeypatch.setattr(module, "_body_scoped_proposals", lambda *_args, **_kwargs: proposals)
    ledger = ClaimLedger(graph)
    with pytest.raises(_PocketAttributionError, match="competing source assignments"):
        _discover_pockets(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.POCKETS).candidates == ()


def test_graph_identical_duplicate_returns_and_issues_one_exact_record(monkeypatch) -> None:
    import b123d_recognisers._recess_features as module
    from b123d_recognisers._recess_reduce import _RecessProposal

    part = Box(60, 40, 12) - Pos(0, 0, 4) * Box(20, 12, 8)
    graph = FaceGraph(part)
    record = _discover_pockets(part)[0]
    nodes = frozenset(node for node in graph.nodes if graph.is_planar(node))
    proposal = _RecessProposal(record, nodes)
    monkeypatch.setattr(
        module, "_body_scoped_proposals", lambda *_args, **_kwargs: [proposal, proposal]
    )
    ledger = ClaimLedger(graph)
    returned = _discover_pockets(part, writer=ledger.writer)
    candidates = ledger.candidate_set(FamilyId.POCKETS).candidates
    assert returned == [record]
    assert len(candidates) == 1 and candidates[0].record is returned[0]
    assert ledger.defining_of(candidates[0]) == nodes
