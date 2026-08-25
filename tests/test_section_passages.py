# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace

import pytest
from build123d import (
    Box,
    BuildPart,
    BuildSketch,
    Compound,
    Cone,
    Face,
    Plane,
    Polygon,
    Pos,
    RegularPolygon,
    Rot,
    Shell,
    export_step,
    extrude,
    import_step,
)

from b123d_recognisers import (
    PassageCompatibilityError,
    PassageEnds,
    PassageFrame,
    PassageSection,
    PassageSectionVertex,
    SectionPassage,
    build_recognition_result,
    recognise_passages,
    recognise_section_passages,
)
from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._registry import PHYSICAL_DEFINITIONS
from b123d_recognisers._run import start
from b123d_recognisers._section_passages import _INTERVAL_TOL, _pair_line
from b123d_recognisers._sections import LocalFrame
from b123d_recognisers.result import _discover_all


def _square():
    return Box(60, 40, 20) - Box(10, 10, 60)


class _LineVector:
    def __init__(self, xyz: tuple[float, float, float]) -> None:
        self.X, self.Y, self.Z = xyz

    def normalized(self) -> _LineVector:
        return self


class _LineEdge:
    geom_type = type("GeometryType", (), {"name": "LINE"})()

    def __init__(self, low: float, high: float) -> None:
        self._ends = (_LineVector((0.0, 0.0, low)), _LineVector((0.0, 0.0, high)))

    def tangent_at(self) -> _LineVector:
        return _LineVector((0.0, 0.0, 1.0))

    def position_at(self, at: float) -> _LineVector:
        return self._ends[0 if at == 0.0 else 1]


class _SharedEdges:
    def __init__(self, intervals: tuple[tuple[float, float], ...]) -> None:
        self._edges = tuple(_LineEdge(*interval) for interval in intervals)

    def shared_edges(self, left: object, right: object) -> tuple[_LineEdge, ...]:
        del left, right
        return self._edges


@pytest.mark.parametrize(
    ("intervals", "accepted"),
    (
        (((-10.0, 0.0), (0.0, 10.0)), True),
        (((-10.0, 0.0), (_INTERVAL_TOL, 10.0)), True),
        (((-10.0, 0.0), (math.nextafter(_INTERVAL_TOL, math.inf), 10.0)), False),
        (((-10.0, 0.0), (-_INTERVAL_TOL, 10.0)), True),
        (((-10.0, 0.0), (math.nextafter(-_INTERVAL_TOL, -math.inf), 10.0)), False),
        (((-10.0, 10.0), (-10.0, 10.0)), False),
    ),
)
def test_segmented_junction_union_has_closed_gap_and_overlap_boundaries(
    intervals: tuple[tuple[float, float], ...], accepted: bool
) -> None:
    frame = LocalFrame.canonical((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    result = _pair_line(_SharedEdges(intervals), object(), object(), frame)  # type: ignore[arg-type]
    assert (result is not None) is accepted
    if result is not None:
        assert result[2:] == (-10.0, 10.0)


def _polygonal_tool(sides_or_points):
    with BuildPart() as tool:
        with BuildSketch(Plane.XY):
            if isinstance(sides_or_points, int):
                RegularPolygon(7, sides_or_points)
            else:
                Polygon(*sides_or_points)
        extrude(amount=60, both=True)
    return tool.part


@dataclass(frozen=True)
class _RawPassageOracle:
    walls: tuple[Face, ...]
    run: tuple[float, float, float]
    interval: tuple[float, float]


def _xyz(value) -> tuple[float, float, float]:
    return (float(value.X), float(value.Y), float(value.Z))


def _canonical_direction(value) -> tuple[float, float, float]:
    direction = _xyz(value.normalized())
    dominant = max(range(3), key=lambda index: (round(abs(direction[index]), 6), -index))
    if direction[dominant] < 0.0:
        direction = tuple(-coordinate for coordinate in direction)
    return direction


def _same_shape(left, right) -> bool:
    return bool(left.wrapped.IsSame(right.wrapped))


def _raw_square_oracle(part) -> _RawPassageOracle:
    """Reconstruct the fixture occurrence without production graph/section helpers."""

    walls = tuple(face for face in part.faces() if math.isclose(face.area, 200.0, abs_tol=1e-6))
    assert len(walls) == 4
    long_edges = tuple(
        edge
        for face in walls
        for edge in face.edges()
        if edge.geom_type.name == "LINE" and math.isclose(edge.length, 20.0, abs_tol=1e-6)
    )
    assert len(long_edges) == 8
    directions = tuple(_canonical_direction(edge.tangent_at()) for edge in long_edges)
    run = directions[0]
    assert all(
        sum(a * b for a, b in zip(run, item, strict=True)) > 1.0 - 1e-9 for item in directions
    )
    adjacency = {
        at: {
            other
            for other in range(len(walls))
            if at != other
            and any(
                _same_shape(left, right)
                for left in walls[at].edges()
                for right in walls[other].edges()
            )
        }
        for at in range(len(walls))
    }
    assert all(len(neighbours) == 2 for neighbours in adjacency.values())
    coordinates = tuple(
        sum(a * b for a, b in zip(_xyz(vertex), run, strict=True))
        for face in walls
        for vertex in face.vertices()
    )
    return _RawPassageOracle(walls, run, (min(coordinates), max(coordinates)))


def test_public_nested_schema_and_json_shape() -> None:
    (record,) = recognise_section_passages(_square())
    assert record == SectionPassage(
        PassageFrame(
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
        ),
        (-10.0, 10.0),
        PassageSection(
            (
                PassageSectionVertex((-5.0, -5.0), 0.0),
                PassageSectionVertex((5.0, -5.0), 0.0),
                PassageSectionVertex((5.0, 5.0), 0.0),
                PassageSectionVertex((-5.0, 5.0), 0.0),
            )
        ),
        PassageEnds(False, False),
    )
    payload = json.loads(json.dumps(record.to_dict()))
    assert list(payload) == ["frame", "run_interval", "section", "ends"]
    assert payload["ends"] == {"low_capped": False, "high_capped": False}


def test_rich_api_is_the_exact_passages_candidate_authority() -> None:
    part = _square()
    ledger = ClaimLedger(FaceGraph(part))
    records = recognise_section_passages(part, ledger=ledger)
    (candidate,) = ledger.candidate_set(FamilyId.PASSAGES).candidates
    assert candidate.record is records[0]
    assert len(ledger.defining_of(candidate)) == len(records[0].section.boundary) == 4
    compatibility = ledger.snapshot_index().passage_compatibility(candidate)
    assert compatibility.eligible is True
    assert compatibility.axis == "z"
    assert compatibility.legacy_ordinal == 0
    assert compatibility.at == (0.0, 0.0, 0.0)


def test_legacy_ledger_refuses_before_any_geometry_work(monkeypatch) -> None:
    import b123d_recognisers.passages as module

    ledger = ClaimLedger(FaceGraph(_square()))
    monkeypatch.setattr(module, "FaceGraph", lambda *args, **kwargs: pytest.fail("geometry ran"))
    with pytest.raises(
        PassageCompatibilityError,
        match=r"recognise_passages\(\.\.\., ledger=\.\.\.\) is unavailable from 0\.4\.0",
    ):
        recognise_passages(object(), ledger=ledger)  # type: ignore[arg-type]
    assert ledger.candidate_set(FamilyId.PASSAGES).candidates == ()


def test_aggregate_has_one_rich_authority_and_legacy_projection() -> None:
    result = build_recognition_result(_square())
    assert len(result.section_passages) == len(result.passages) == 1
    assert result.passages == tuple(recognise_passages(_square()))


def test_oblique_passage_is_rich_only_and_keeps_exact_wall_ownership() -> None:
    part = Rot(17, 23, 31) * _square()
    oracle = _raw_square_oracle(part)
    assert recognise_passages(part) == []
    graph = FaceGraph(part)
    ledger = ClaimLedger(graph)
    (record,) = recognise_section_passages(part, ledger=ledger)
    assert record.frame.run == pytest.approx(oracle.run, abs=5e-7)
    assert record.run_interval == pytest.approx(oracle.interval, abs=5e-4)
    assert record.frame.run == (0.390731, -0.26913, 0.880283)
    assert len(record.section.boundary) == 4
    (candidate,) = ledger.candidate_set(FamilyId.PASSAGES).candidates
    assert candidate.record is record
    compatibility = ledger.snapshot_index().passage_compatibility(candidate)
    assert compatibility.eligible is False
    assert compatibility.axis is None
    defining = ledger.defining_of(candidate)
    assert len(defining) == 4
    assert all(
        any(_same_shape(graph.face(node), wall) for wall in oracle.walls) for node in defining
    )
    assert all(
        any(_same_shape(graph.face(node), wall) for node in defining) for wall in oracle.walls
    )
    result = build_recognition_result(part)
    assert result.section_passages == (record,)
    assert result.passages == ()


@pytest.mark.parametrize(
    ("section", "wall_count"),
    [
        (3, 3),
        (6, 6),
        (((-8, -8), (8, -8), (8, 8), (3, 8), (3, -3), (-3, -3), (-3, 8), (-8, 8)), 8),
    ],
    ids=("triangle", "hexagon", "concave-u"),
)
def test_free_axis_line_sections_preserve_complete_wall_cycles(section, wall_count) -> None:
    part = Rot(17, 23, 31) * (Box(60, 40, 20) - _polygonal_tool(section))
    ledger = ClaimLedger(FaceGraph(part))
    (record,) = recognise_section_passages(part, ledger=ledger)
    assert len(record.section.boundary) == wall_count
    (candidate,) = ledger.candidate_set(FamilyId.PASSAGES).candidates
    assert candidate.record is record
    assert len(ledger.defining_of(candidate)) == wall_count
    assert recognise_passages(part) == []


def test_multiple_unequal_free_axis_occurrences_on_one_solid_are_distinct() -> None:
    part = Box(80, 40, 20)
    part = part - Pos(-20, 0, 0) * Box(8, 8, 60) - Pos(20, 0, 0) * Box(12, 6, 60)
    part = Rot(17, 23, 31) * part
    ledger = ClaimLedger(FaceGraph(part))
    records = recognise_section_passages(part, ledger=ledger)
    candidates = ledger.candidate_set(FamilyId.PASSAGES).candidates
    assert len(records) == len(candidates) == 2
    assert all(
        candidate.record is record for candidate, record in zip(candidates, records, strict=True)
    )
    assert records[0] != records[1]


def test_equal_coincident_solids_keep_two_occurrence_identities() -> None:
    first = Rot(17, 23, 31) * _square()
    second = Rot(17, 23, 31) * _square()
    part = Compound([first, second])
    ledger = ClaimLedger(FaceGraph(part))
    records = recognise_section_passages(part, ledger=ledger)  # type: ignore[arg-type]
    candidates = ledger.candidate_set(FamilyId.PASSAGES).candidates
    assert len(records) == len(candidates) == 2
    assert records[0] == records[1]
    assert records[0] is not records[1]
    assert candidates[0] is not candidates[1]


@pytest.mark.parametrize(
    "part",
    (
        Pos(17, -9, 4) * Rot(17, 23, 31) * _square(),
        (Rot(17, 23, 31) * _square()).mirror(Plane.YZ),
        (Rot(17, 23, 31) * _square()).scale(2.5),
    ),
)
def test_free_axis_passage_survives_translation_mirror_and_uniform_scale(part) -> None:
    graph = FaceGraph(part)
    ledger = ClaimLedger(graph)
    records = recognise_section_passages(part, ledger=ledger)  # type: ignore[arg-type]
    assert len(records) == 1
    (candidate,) = ledger.candidate_set(FamilyId.PASSAGES).candidates
    assert candidate.record is records[0]
    assert len(ledger.defining_of(candidate)) == 4


def test_late_foreign_occurrence_refuses_before_any_candidate_prefix(monkeypatch) -> None:
    import b123d_recognisers.passages as passages_module
    from b123d_recognisers._section_passages import section_ring_proposals

    part = Rot(17, 23, 31) * _square()
    graph = FaceGraph(part)
    valid = section_ring_proposals(part, graph)
    foreign_part = Pos(100, 0, 0) * part
    foreign = section_ring_proposals(foreign_part, FaceGraph(foreign_part))
    assert len(valid) == len(foreign) == 1
    monkeypatch.setattr(
        passages_module,
        "section_ring_proposals",
        lambda supplied_part, supplied_graph: [valid[0], foreign[0]],
    )
    ledger = ClaimLedger(graph)
    with pytest.raises(ValueError, match="not issued by this graph|body authority changed"):
        passages_module._discover_section_passages(part, graph, ledger.writer)
    assert ledger.candidate_set(FamilyId.PASSAGES).candidates == ()


def test_aggregate_late_passage_failure_has_no_completion_or_occurrence_capability(
    monkeypatch,
) -> None:
    import b123d_recognisers.passages as passages_module
    from b123d_recognisers._section_passages import section_ring_proposals

    first = Rot(17, 23, 31) * _square()
    part = Compound([first, Pos(150, 0, 0) * first])
    context = start(part)
    proposals = section_ring_proposals(part, context.graph)
    assert len(proposals) == 2
    foreign_part = Pos(400, 0, 0) * first
    (foreign,) = section_ring_proposals(foreign_part, FaceGraph(foreign_part))
    malformed = replace(proposals[1], solid=foreign.solid)
    monkeypatch.setattr(
        passages_module,
        "section_ring_proposals",
        lambda supplied_part, supplied_graph: [proposals[0], malformed],
    )
    ledger = ClaimLedger(context.graph, definitions=PHYSICAL_DEFINITIONS)
    with pytest.raises(ValueError, match="body authority changed"):
        _discover_all(context, ledger)
    assert ledger.candidate_set(FamilyId.PASSAGES).candidates == ()
    assert FamilyId.PASSAGES not in ledger._issuer._completed
    assert FamilyId.PASSAGES not in ledger._issuer._completed_occurrences
    assert all(
        FamilyId.PASSAGES not in snapshot.occurrences
        for snapshot in ledger._issuer._restricted_snapshots.values()
    )


@pytest.mark.parametrize(
    ("fractions", "accepted"),
    (
        ((1e-9, 1e-9, 1e-9), True),
        ((math.nextafter(1e-9, math.inf), 0.0, 0.0), False),
        ((0.0, math.nextafter(1e-9, math.inf), 0.0), False),
        ((0.0, 0.0, math.nextafter(1e-9, math.inf)), False),
    ),
)
def test_full_prism_and_both_end_slabs_share_the_closed_material_boundary(
    monkeypatch, fractions: tuple[float, float, float], accepted: bool
) -> None:
    import b123d_recognisers._section_passages as module

    part = Rot(17, 23, 31) * _square()
    (proposal,) = module.section_ring_proposals(part, FaceGraph(part))
    pending = iter(fractions)
    monkeypatch.setattr(module, "_material_fraction", lambda part, probe: next(pending))
    assert (
        module._void_and_open(part, proposal.frame, proposal.run_interval, proposal.section)
        is accepted
    )


def test_full_prism_coordinate_floor_is_fail_closed_at_equality(monkeypatch) -> None:
    import b123d_recognisers._section_passages as module

    part = Rot(17, 23, 31) * _square()
    (proposal,) = module.section_ring_proposals(part, FaceGraph(part))
    with pytest.raises(ValueError, match="too short"):
        module._probe_prism(
            proposal.frame,
            (0.0, 2 * module._COORD_FLOOR),
            proposal.section,
        )
    sentinel = object()
    captured = []
    monkeypatch.setattr(
        module.Solid,
        "extrude",
        lambda face, vector: captured.append(vector.length) or sentinel,
    )
    assert (
        module._probe_prism(
            proposal.frame,
            (0.0, math.nextafter(2 * module._COORD_FLOOR, math.inf)),
            proposal.section,
        )
        is sentinel
    )
    assert captured[0] > 0.0


def test_candidate_compatibility_fact_is_issuer_revalidated() -> None:
    part = _square()
    ledger = ClaimLedger(FaceGraph(part))
    recognise_section_passages(part, ledger=ledger)
    (candidate,) = ledger.candidate_set(FamilyId.PASSAGES).candidates
    index = ledger.snapshot_index()
    original = candidate.compatibility
    object.__setattr__(candidate, "compatibility", None)
    with pytest.raises(ValueError, match="issued state"):
        index.passage_compatibility(candidate)
    object.__setattr__(candidate, "compatibility", original)
    assert original is not None
    object.__setattr__(original, "axis", "bad")
    with pytest.raises(ValueError, match="compatibility axis is invalid"):
        index.passage_compatibility(candidate)
    object.__setattr__(original, "axis", "z")
    assert index.passage_compatibility(candidate) is original


def test_oblique_passage_step_round_trip_preserves_schema_and_wall_count(tmp_path) -> None:
    source = Rot(17, 23, 31) * _square()
    source_oracle = _raw_square_oracle(source)
    path = tmp_path / "oblique-section-passage.step"
    assert export_step(source, path)
    imported = import_step(path)
    imported_oracle = _raw_square_oracle(imported)
    assert imported_oracle.run == pytest.approx(source_oracle.run, abs=1e-9)
    assert imported_oracle.interval == pytest.approx(source_oracle.interval, abs=1e-8)
    assert recognise_section_passages(imported) == recognise_section_passages(source)
    assert recognise_passages(imported) == []


def test_whole_occurrence_serialization_displacement_refuses_before_evidence() -> None:
    accepted = Rot(17, 23, 31) * (Box(60, 40, 5000) - Box(10, 10, 15000))
    assert len(recognise_section_passages(accepted)) == 1

    refused = Rot(17, 23, 31) * (Box(60, 40, 10000) - Box(10, 10, 30000))
    ledger = ClaimLedger(FaceGraph(refused))
    with pytest.raises(ValueError, match="serialization exceeds the displacement bound"):
        recognise_section_passages(refused, ledger=ledger)
    assert ledger.candidate_set(FamilyId.PASSAGES).candidates == ()


@pytest.mark.parametrize(
    "part",
    [
        Box(60, 40, 20) - Pos(0, 0, 5) * Box(10, 10, 20),
        (Box(60, 40, 20) - Box(10, 10, 60)) + Box(10, 10, 2),
        (Box(60, 40, 20) - Box(10, 10, 60)) + Pos(0, 4, 0) * Box(10, 0.1, 5),
        Box(60, 40, 20) - Cone(5, 7, 60),
    ],
    ids=("one-cap", "membrane", "partial-rib", "taper"),
)
def test_caps_obstructions_and_taper_refuse_without_evidence(part) -> None:
    part = Rot(17, 23, 31) * part
    ledger = ClaimLedger(FaceGraph(part))
    assert recognise_section_passages(part, ledger=ledger) == []
    assert ledger.candidate_set(FamilyId.PASSAGES).candidates == ()


def test_open_shell_cannot_supply_body_authority() -> None:
    solid = Rot(17, 23, 31) * _square()
    shell = Shell(solid.faces())
    ledger = ClaimLedger(FaceGraph(shell))
    assert recognise_section_passages(shell, ledger=ledger) == []  # type: ignore[arg-type]
    assert ledger.candidate_set(FamilyId.PASSAGES).candidates == ()


@pytest.mark.parametrize(
    "record",
    [
        lambda: PassageFrame(
            (0.0, 0.0, 0.0),
            (0.0, 0.0, -1.0),
            (1.0, 0.0, 0.0),
            (0.0, -1.0, 0.0),
        ),
        lambda: PassageFrame(
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            (0.707107, 0.707107, 0.0),
            (-0.707107, 0.707107, 0.0),
        ),
        lambda: PassageFrame(
            (0.0, 0.0, 0.0),
            (0.1234567, 0.0, 0.992349952),
            (0.0, 1.0, 0.0),
            (-0.992349952, 0.0, 0.1234567),
        ),
        lambda: PassageEnds(0, False),
        lambda: SectionPassage(
            PassageFrame(
                (0.0, 0.0, 0.0),
                (0.0, 0.0, 1.0),
                (1.0, 0.0, 0.0),
                (0.0, 1.0, 0.0),
            ),
            (1.0, 1.0),
            PassageSection(
                (
                    PassageSectionVertex((-1.0, -1.0), 0.0),
                    PassageSectionVertex((1.0, -1.0), 0.0),
                    PassageSectionVertex((0.0, 2.0), 0.0),
                )
            ),
            PassageEnds(False, False),
        ),
    ],
)
def test_public_schema_refuses_noncanonical_values(record) -> None:
    with pytest.raises(ValueError):
        record()
