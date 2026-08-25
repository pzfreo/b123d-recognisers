"""F5: Plates own their complete low-negative/high-positive planar groups."""

from __future__ import annotations

import ast
import copy
import math
from dataclasses import dataclass
from pathlib import Path

import pytest
from build123d import Box, Compound, Plane, Pos, Rot, export_step, import_step
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepGProp import BRepGProp
from OCP.GeomAbs import GeomAbs_Plane
from OCP.GProp import GProp_GProps

from b123d_recognisers import recognise_plates
from b123d_recognisers._adjacency import FaceGraph, FaceNode, SolidRef
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers.plates import Plate, _discover_plates, _PlateAttributionError
from b123d_recognisers.result import _take_inventory
from tests.golden.plates_pads_levels_and_slanted_steps.fixture import build_fixture

ROOT = Path(__file__).parents[1]


@dataclass(frozen=True)
class _Expected:
    record: Plate
    nodes: frozenset[FaceNode]
    solid: SolidRef


def _clusters(values: list[float], tolerance: float) -> list[list[int]]:
    ordered = sorted(range(len(values)), key=values.__getitem__)
    groups: list[list[int]] = []
    for index in ordered:
        if not groups or values[index] - values[groups[-1][0]] > tolerance:
            groups.append([index])
        else:
            groups[-1].append(index)
    return groups


def _fresh_expected(part, graph: FaceGraph, *, min_area=0.4, max_thick=0.5, tol=0.5):
    bb = part.bounding_box()
    ext = (bb.max.X - bb.min.X, bb.max.Y - bb.min.Y, bb.max.Z - bb.min.Z)
    facts = []
    for face in part.faces():
        surface = BRepAdaptor_Surface(face.wrapped)
        if surface.GetType() != GeomAbs_Plane:
            continue
        normal = face.normal_at()
        vector = (normal.X, normal.Y, normal.Z)
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face.wrapped, props)
        centre = props.CentreOfMass()
        point = (centre.X(), centre.Y(), centre.Z())
        plane = surface.Plane().Location()
        location = (plane.X(), plane.Y(), plane.Z())
        facts.append((graph.require_node(face), vector, props.Mass(), point, location))

    proposals = []
    for axis in range(3):
        cross = math.prod(ext[index] for index in range(3) if index != axis)
        if cross <= 0:
            continue
        sides: tuple[list[tuple], list[tuple]] = ([], [])
        for fact in facts:
            component = fact[1][axis]
            if abs(component) < 0.999:
                continue
            sides[component > 0].append(fact)
        groups = []
        for side in sides:
            grouped = {}
            locations = [fact[4][axis] for fact in side]
            for cluster in _clusters(locations, tol):
                members = [side[index] for index in cluster]
                coordinate = min(item[4][axis] for item in members)
                area = sum(item[2] for item in members)
                in_plane = [index for index in range(3) if index != axis]
                grouped[coordinate] = (
                    area,
                    sum(item[3][in_plane[0]] * item[2] for item in members),
                    sum(item[3][in_plane[1]] * item[2] for item in members),
                    frozenset(item[0] for item in members),
                )
            groups.append(grouped)
        events = []
        for sign, grouped in zip((-1, 1), groups, strict=True):
            for coordinate, group in grouped.items():
                if group[0] > min_area * cross:
                    events.append((coordinate, sign, group))
        events.sort(key=lambda event: (event[0], event[1]))
        for low, high in zip(events, events[1:], strict=False):
            if low[1] != -1 or high[1] != 1:
                continue
            thickness = high[0] - low[0]
            if thickness <= tol or thickness >= max_thick * ext[axis]:
                continue
            area = low[2][0] + high[2][0]
            record = Plate(
                "xyz"[axis],
                round(low[0], 3),
                round(high[0], 3),
                (low[2][1] + high[2][1]) / area,
                (low[2][2] + high[2][2]) / area,
            )
            nodes = low[2][3] | high[2][3]
            solid = graph.common_valid_solid(nodes)
            assert solid is not None
            proposals.append(_Expected(record, nodes, solid))
    by_key: dict[tuple[str, float, float], _Expected] = {}
    for proposal in sorted(
        proposals, key=lambda item: (item.record.axis, item.record.lo, item.record.hi)
    ):
        by_key.setdefault((proposal.record.axis, proposal.record.lo, proposal.record.hi), proposal)
    return list(by_key.values())


def _claimed(part, **kwargs):
    ledger = ClaimLedger(FaceGraph(part))
    expected = _fresh_expected(
        part,
        ledger.graph,
        min_area=kwargs.get("min_area_frac", 0.4),
        max_thick=kwargs.get("max_thick_frac", 0.5),
        tol=0.5 if kwargs.get("tol") is None else kwargs["tol"],
    )
    public = recognise_plates(part, **kwargs)
    records = _discover_plates(part, writer=ledger.writer, **kwargs)
    assert [item.record.to_dict() for item in expected] == [record.to_dict() for record in records]
    assert [record.to_dict() for record in records] == [record.to_dict() for record in public]
    candidates = ledger.candidate_set(FamilyId.PLATES).candidates
    for item, record, candidate in zip(expected, records, candidates, strict=True):
        assert candidate.record is record
        assert ledger.defining_of(candidate) == item.nodes
        assert ledger.graph.common_valid_solid(item.nodes) == item.solid
    return records, candidates, ledger


@pytest.mark.parametrize(
    "part",
    [
        build_fixture(),
        Rot(90, 0, 0) * build_fixture(),
        Rot(0, 90, 0) * build_fixture(),
        build_fixture().mirror(Plane.YZ),
        build_fixture().scale(0.2),
        build_fixture().scale(5),
    ],
)
def test_plate_groups_survive_axes_mirror_and_scale(part) -> None:
    assert _claimed(part)[0]


def test_fragmented_groups_keep_every_original_patch() -> None:
    part = build_fixture() - Pos(-50, 0, 20) * Box(20, 4, 6)
    records, candidates, ledger = _claimed(part)
    assert records
    assert any(len(ledger.defining_of(candidate)) > 2 for candidate in candidates)


def test_step_traversal_custom_thresholds_and_shared_graph(monkeypatch, tmp_path: Path) -> None:
    target = tmp_path / "plates.step"
    assert export_step(build_fixture(), target)
    _claimed(import_step(target), min_area_frac=0.3, max_thick_frac=0.7, tol=0.25)

    part = build_fixture()
    kind = type(part)
    original = kind.faces
    monkeypatch.setattr(kind, "faces", lambda self: type(original(self))(reversed(original(self))))
    _claimed(part)


def test_compound_mixed_provenance_refuses_without_prefix() -> None:
    part = Compound([build_fixture(), copy.deepcopy(build_fixture())])
    assert recognise_plates(part)
    ledger = ClaimLedger(FaceGraph(part))
    with pytest.raises(_PlateAttributionError):
        _discover_plates(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.PLATES).candidates == ()
    with pytest.raises(_PlateAttributionError):
        _take_inventory(part)


def test_foreign_and_late_body_failure_are_atomic(monkeypatch) -> None:
    part = build_fixture()
    foreign = ClaimLedger(FaceGraph(Pos(200, 0, 0) * build_fixture()))
    with pytest.raises(_PlateAttributionError):
        _discover_plates(part, writer=foreign.writer)
    assert foreign.candidate_set(FamilyId.PLATES).candidates == ()

    ledger = ClaimLedger(FaceGraph(part))
    monkeypatch.setattr(ledger.graph, "common_valid_solid", lambda _nodes: None)
    with pytest.raises(_PlateAttributionError):
        _discover_plates(part, writer=ledger.writer)
    assert ledger.candidate_set(FamilyId.PLATES).candidates == ()


def test_terminal_plate_identity_and_evidence() -> None:
    product = _take_inventory(build_fixture())
    candidates = product.physical.candidate_set(FamilyId.PLATES).candidates
    assert candidates
    assert tuple(candidate.record for candidate in candidates) == product.result.plates
    assert all(product.evidence.defining_of(candidate) for candidate in candidates)


def test_completed_turned_profile_remains_record_only_global_veto(monkeypatch) -> None:
    from b123d_recognisers.turned import TurnedProfile

    calls = 0

    def veto(_steps):
        nonlocal calls
        calls += 1
        return object()

    monkeypatch.setattr(TurnedProfile, "from_steps", staticmethod(veto))
    product = _take_inventory(build_fixture())
    assert calls == 1
    assert product.physical.candidate_set(FamilyId.PLATES).candidates == ()
    assert product.result.plates == ()


def test_plate_private_core_and_registry_route_are_closed() -> None:
    registry = (ROOT / "src/b123d_recognisers/_registry.py").read_text(encoding="utf-8")
    tree = ast.parse(registry)
    plates = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_plates"
    )
    calls = [node for node in ast.walk(plates) if isinstance(node, ast.Call)]
    discover = next(
        call
        for call in calls
        if isinstance(call.func, ast.Name) and call.func.id == "_discover_plates"
    )
    writer = {keyword.arg: keyword.value for keyword in discover.keywords}["writer"]
    assert isinstance(writer, ast.Attribute) and writer.attr == "writer"
    assert (
        sum(
            isinstance(call.func, ast.Attribute) and call.func.attr == "from_steps"
            for call in calls
        )
        == 1
    )
