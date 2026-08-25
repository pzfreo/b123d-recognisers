"""#235: Slots own every selected planar wall and cylindrical cap patch."""

from __future__ import annotations

import ast
import inspect
from copy import deepcopy
from pathlib import Path

import pytest
from build123d import Box, Compound, Cylinder, Edge, Plane, Pos, Rot, export_step, import_step
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepFeat import BRepFeat_SplitShape
from OCP.GeomAbs import GeomAbs_Cylinder

from b123d_recognisers import recognise_slots
from b123d_recognisers._adjacency import FaceEdges, FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._recess_features import _discover_slots, _SlotAttributionError
from b123d_recognisers._registry import PHYSICAL_DEFINITIONS, FullyAttributed
from b123d_recognisers._run import start
from b123d_recognisers.result import _discover_all, _take_inventory

ROOT = Path(__file__).parents[1]
_AXIS = {"x": 0, "y": 1, "z": 2}


def _obround(length: float, width: float, depth: float):
    end = Cylinder(width / 2, depth)
    return Box(length, width, depth) + Pos(-length / 2, 0, 0) * end + Pos(
        length / 2, 0, 0
    ) * end


def _expected(part):
    """Fresh graph traversal derives all wall/cap roles before Candidate inspection."""
    graph = FaceGraph(part)
    expected = []
    for record in recognise_slots(part):
        width_index = _AXIS[record.width_axis]
        long_index = _AXIS[record.long_axis]
        depth_index = _AXIS[record.depth_axis]
        walls = set()
        caps = [set(), set()]
        for node in graph.nodes:
            bounds = graph.bounds(node)
            if graph.is_planar(node):
                normal = graph.normal(node)
                if normal is None:
                    continue
                normal_index = max(range(3), key=lambda index: abs(normal[index]))
                if normal_index == width_index:
                    at = sum(bounds[width_index]) / 2
                    if (
                        abs(abs(at - record.w_center) - record.width / 2) <= 1e-6
                        and bounds[long_index][0] >= record.lo - 1e-6
                        and bounds[long_index][1] <= record.hi + 1e-6
                        and bounds[depth_index][0] == pytest.approx(record.d_lo)
                        and bounds[depth_index][1] == pytest.approx(record.d_hi)
                    ):
                        walls.add(node)
                elif normal_index == long_index and record.length == pytest.approx(record.width):
                    at = sum(bounds[long_index]) / 2
                    if abs(abs(at - (record.lo + record.hi) / 2) - record.length / 2) <= 1e-6:
                        walls.add(node)
                continue
            surface = BRepAdaptor_Surface(graph.face(node).wrapped)
            if surface.GetType() != GeomAbs_Cylinder:
                continue
            cylinder = surface.Cylinder()
            direction = cylinder.Axis().Direction()
            components = (abs(direction.X()), abs(direction.Y()), abs(direction.Z()))
            location = cylinder.Location()
            coords = (location.X(), location.Y(), location.Z())
            if (
                components[depth_index] != pytest.approx(1.0)
                or cylinder.Radius() != pytest.approx(record.width / 2)
                or coords[width_index] != pytest.approx(record.w_center)
                or bounds[depth_index][0] != pytest.approx(record.d_lo)
                or bounds[depth_index][1] != pytest.approx(record.d_hi)
            ):
                continue
            flats = (record.lo + record.width / 2, record.hi - record.width / 2)
            for index, flat in enumerate(flats):
                if coords[long_index] == pytest.approx(flat, abs=0.1):
                    caps[index].add(node)
        groups = tuple(frozenset(group) for group in caps if group)
        if groups and record.length < 2 * record.width:
            walls.clear()  # stubby cap-recovered route has no admissible paired-wall occurrence
        nodes = frozenset((*walls, *(node for group in groups for node in group)))
        expected.append((record, nodes, frozenset(walls), groups))
    return graph, expected


@pytest.mark.parametrize(
    ("part", "planar", "caps"),
    [
        (Box(80, 50, 16) - Box(28, 10, 16), 2, 0),
        (Box(120, 60, 20) - Box(20, 20, 20), 4, 0),
        (Box(120, 120, 20) - Box(60, 14, 20) - Box(14, 60, 20), 4, 0),
        (Box(100, 60, 20) - _obround(30, 12, 20), 2, 2),
        (Box(100, 60, 20) - _obround(3, 12, 20), 0, 2),
    ],
)
def test_route_matrix_matches_fresh_complete_role_inventory(part, planar: int, caps: int) -> None:
    fresh, expected = _expected(part)
    product = _take_inventory(part)
    candidates = product.physical.candidate_set(FamilyId.SLOTS).candidates
    records = tuple(candidate.record for candidate in candidates)
    assert [record.to_dict() for record in recognise_slots(part)] == [
        item[0].to_dict() for item in expected
    ]
    assert len(records) == len(candidates) == len(expected)
    for candidate, record, (_want, nodes, walls, groups) in zip(
        candidates, records, expected, strict=True
    ):
        assert candidate.record is record
        actual = product.evidence.defining_of(candidate)
        assert len(walls) == planar and len(groups) == caps
        assert len(actual) == len(nodes)
        expected_faces = [fresh.face(node) for node in nodes]
        actual_faces = [product.context.graph.face(node) for node in actual]
        assert all(any(face.is_same(want) for face in actual_faces) for want in expected_faces)
        assert product.context.graph.common_valid_solid(actual) is not None
        for node in actual:
            if product.context.graph.is_planar(node):
                normal = product.context.graph.normal(node)
                assert normal is not None
                axis = max(range(3), key=lambda index: abs(normal[index]))
                assert axis in {_AXIS[record.width_axis], _AXIS[record.long_axis]}
                assert abs(normal[axis]) == pytest.approx(1.0)
                lo, hi = product.context.graph.bounds(node)[axis]
                assert lo == pytest.approx(hi)
                if axis == _AXIS[record.width_axis]:
                    assert abs(lo - record.w_center) == pytest.approx(record.width / 2)
                else:
                    assert abs(lo - (record.lo + record.hi) / 2) == pytest.approx(
                        record.length / 2
                    )
            else:
                surface = BRepAdaptor_Surface(product.context.graph.face(node).wrapped)
                assert surface.GetType() == GeomAbs_Cylinder
                cylinder = surface.Cylinder()
                direction = cylinder.Axis().Direction()
                components = (abs(direction.X()), abs(direction.Y()), abs(direction.Z()))
                assert components[_AXIS[record.depth_axis]] == pytest.approx(1.0)
                assert cylinder.Radius() == pytest.approx(record.width / 2)


def test_public_claim_ledger_and_writer_use_the_same_complete_product() -> None:
    part = Box(100, 60, 20) - _obround(30, 12, 20)
    public_ledger = ClaimLedger(FaceGraph(part))
    via_ledger = recognise_slots(part, ledger=public_ledger)
    writer_ledger = ClaimLedger(FaceGraph(part))
    via_writer = recognise_slots(part, ledger=writer_ledger.writer)
    plain = recognise_slots(part)
    assert [item.to_dict() for item in via_ledger] == [item.to_dict() for item in plain]
    assert [item.to_dict() for item in via_writer] == [item.to_dict() for item in plain]
    assert [len(claim.defining) for claim in public_ledger.claims] == [4]
    assert [len(claim.defining) for claim in writer_ledger.claims] == [4]


def test_step_split_cap_publishes_every_original_patch(tmp_path: Path) -> None:
    part = Box(100, 60, 20) - _obround(30, 12, 20)
    graph, expected = _expected(part)
    _record, _nodes, _walls, cap_groups = expected[0]
    cap_node = max(
        (node for group in cap_groups for node in group), key=lambda node: graph.bounds(node)[0][1]
    )
    face = graph.face(cap_node)
    bounds = face.bounding_box()
    seam = Edge.make_line((21, 0, bounds.min.Z), (21, 0, bounds.max.Z))
    splitter = BRepFeat_SplitShape(part.wrapped)
    splitter.Add(seam.wrapped, face.wrapped)
    splitter.Build()
    assert splitter.IsDone()
    split = type(part).cast(splitter.Shape())
    path = tmp_path / "slot-split-cap.step"
    assert export_step(split, path)
    imported = import_step(path)
    ledger = ClaimLedger(FaceGraph(imported))
    (record,) = _discover_slots(imported, writer=ledger.writer)
    (candidate,) = ledger.candidate_set(FamilyId.SLOTS).candidates
    defining = ledger.defining_of(candidate)
    assert candidate.record is record
    assert sum(not ledger.graph.is_planar(node) for node in defining) == 3
    assert sum(ledger.graph.is_planar(node) for node in defining) == 2


def test_equal_coincident_and_separate_occurrences_keep_identity_and_body_scope() -> None:
    first = Box(80, 50, 16) - Box(28, 10, 16)
    for part in (
        Compound([first, deepcopy(first)]),
        Compound([first, Pos(150, 0, 0) * deepcopy(first)]),
    ):
        ledger = ClaimLedger(FaceGraph(part))
        records = _discover_slots(part, writer=ledger.writer)
        candidates = ledger.candidate_set(FamilyId.SLOTS).candidates
        assert len(records) == len(candidates) == 2
        assert all(
            candidate.record is record
            for candidate, record in zip(candidates, records, strict=True)
        )
        roles = [ledger.defining_of(candidate) for candidate in candidates]
        assert roles[0].isdisjoint(roles[1])
        assert all(ledger.graph.common_valid_solid(nodes) is not None for nodes in roles)


@pytest.mark.parametrize(
    "part",
    [
        Pos(37, -19, 11) * (Box(80, 50, 16) - Box(28, 10, 16)),
        Rot(90, 0, 0) * (Box(80, 50, 16) - Box(28, 10, 16)),
        Rot(0, 90, 0) * (Box(80, 50, 16) - Box(28, 10, 16)),
        (Box(80, 50, 16) - Box(28, 10, 16)).mirror(Plane.YZ),
        (Box(80, 50, 16) - Box(28, 10, 16)).scale(0.2),
        (Box(80, 50, 16) - Box(28, 10, 16)).scale(5),
        Rot(90, 0, 0) * (Box(100, 60, 20) - _obround(30, 12, 20)),
    ],
)
def test_principal_axes_translation_mirror_and_scale_preserve_complete_roles(part) -> None:
    ledger = ClaimLedger(FaceGraph(part))
    records = _discover_slots(part, writer=ledger.writer)
    assert [record.to_dict() for record in records] == [
        record.to_dict() for record in recognise_slots(part)
    ]
    candidates = ledger.candidate_set(FamilyId.SLOTS).candidates
    assert len(records) == len(candidates) == 1
    assert candidates[0].record is records[0]
    assert ledger.defining_of(candidates[0])
    assert ledger.graph.common_valid_solid(ledger.defining_of(candidates[0])) is not None


@pytest.mark.parametrize(
    "part",
    [
        Box(80, 60, 20) - Pos(0, 0, 5) * Box(30, 10, 10),  # floored Pocket
        Box(80, 60, 20) - Cylinder(6, 20),  # full cylindrical hole
        Box(80, 60, 20),
    ],
)
def test_non_slot_controls_publish_nothing(part) -> None:
    ledger = ClaimLedger(FaceGraph(part))
    assert _discover_slots(part, writer=ledger.writer) == []
    assert ledger.candidate_set(FamilyId.SLOTS).candidates == ()


def test_shared_graph_face_edges_and_foreign_authority_boundaries() -> None:
    part = Box(80, 50, 16) - Box(28, 10, 16)
    memo = FaceEdges()
    ledger = ClaimLedger(FaceGraph(part, face_edges=memo))
    assert _discover_slots(part, face_edges=memo, graph=ledger.graph) == recognise_slots(
        part, face_edges=memo
    )
    assert _discover_slots(part, face_edges=memo, writer=ledger.writer)
    foreign = ClaimLedger(FaceGraph(Pos(100, 0, 0) * part))
    with pytest.raises(_SlotAttributionError):
        _discover_slots(part, writer=foreign.writer)
    assert foreign.candidate_set(FamilyId.SLOTS).candidates == ()
    with pytest.raises(_SlotAttributionError, match="one authority"):
        _discover_slots(part, graph=ledger.graph, writer=foreign.writer)


def test_late_second_body_failure_is_atomic_and_uncompleted(monkeypatch) -> None:
    first = Box(80, 50, 16) - Box(28, 10, 16)
    part = Compound([first, Pos(150, 0, 0) * deepcopy(first)])
    context = start(part)
    ledger = ClaimLedger(context.graph, definitions=PHYSICAL_DEFINITIONS)
    real = ledger.graph.common_valid_solid
    owners = []

    def fail_second(nodes):
        owner = real(nodes)
        if owner is not None and owner not in owners:
            owners.append(owner)
        return None if len(owners) > 1 else owner

    monkeypatch.setattr(ledger.graph, "common_valid_solid", fail_second)
    with pytest.raises(_SlotAttributionError, match="one valid solid"):
        _discover_all(context, ledger)
    assert ledger.candidate_set(FamilyId.SLOTS).candidates == ()
    assert FamilyId.SLOTS not in ledger._issuer._completed
    assert FamilyId.SLOTS not in ledger._issuer._completed_occurrences


def test_status_registry_writer_and_private_module_seams_are_closed() -> None:
    definition = next(item for item in PHYSICAL_DEFINITIONS if item.family is FamilyId.SLOTS)
    assert isinstance(definition.attribution, FullyAttributed)
    package = ROOT / "src/b123d_recognisers"
    callers = []
    importers = []
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if any(
            isinstance(node, ast.ImportFrom)
            and any(alias.name == "_discover_slots" for alias in node.names)
            for node in ast.walk(tree)
        ):
            importers.append(path.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and (
                (isinstance(node.func, ast.Name) and node.func.id == "_discover_slots")
                or (isinstance(node.func, ast.Attribute) and node.func.attr == "_discover_slots")
            ):
                callers.append((path.name, node))
    assert importers == ["_registry.py"]
    assert {path for path, _call in callers} == {"_registry.py", "_recess_features.py"}
    registry_call = next(call for path, call in callers if path == "_registry.py")
    writer = {item.arg: item.value for item in registry_call.keywords}["writer"]
    assert isinstance(writer, ast.Attribute) and writer.attr == "writer"
    assert isinstance(writer.value, ast.Name) and writer.value.id == "s"
    assert tuple(inspect.signature(recognise_slots).parameters) == (
        "part",
        "face_edges",
        "ledger",
    )

    watched = {"_slot_proposals_one", "_body_scoped_proposals", "_RecessProposal"}
    sites = {name: [] for name in watched}
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        class Roster(ast.NodeVisitor):
            def __init__(self, source_name):
                self.source_name = source_name
                self.functions = []

            def visit_FunctionDef(self, node):
                self.functions.append(node.name)
                self.generic_visit(node)
                self.functions.pop()

            def visit_Call(self, node):
                leaf = node.func.id if isinstance(node.func, ast.Name) else ""
                if leaf in sites:
                    sites[leaf].append((self.source_name, self.functions[-1]))
                self.generic_visit(node)

        Roster(path.name).visit(tree)
    assert sites["_slot_proposals_one"] == [
        ("_recess_core.py", "_recognise_slots_one"),
    ]
    assert sites["_body_scoped_proposals"] == [
        ("_recess_features.py", "_discover_slots"),
        ("_recess_features.py", "_discover_slots"),
        ("_recess_features.py", "recognise_pockets"),
    ]
    assert {path for path, _function in sites["_RecessProposal"]} == {
        "_recess_core.py",
        "_recess_obround.py",
        "_recess_reduce.py",
    }
    source = (package / "_recess_features.py").read_text(encoding="utf-8")
    assert not any(
        token in source
        for token in (
            "CandidateSet",
            "EvidenceIndex",
            "InventoryProduct",
            "ReconciliationResult",
            "CompletedInputs",
        )
    )
