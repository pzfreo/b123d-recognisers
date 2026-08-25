# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

from __future__ import annotations

import json
import math
from dataclasses import dataclass

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


def _square():
    return Box(60, 40, 20) - Box(10, 10, 60)


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
