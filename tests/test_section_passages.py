# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

from __future__ import annotations

import json
import math
from dataclasses import dataclass

import pytest
from build123d import Box, Face, Rot, export_step, import_step

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
        sum(a * b for a, b in zip(run, item, strict=True)) > 1.0 - 1e-9
        for item in directions
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


@pytest.mark.parametrize(
    "record",
    [
        lambda: PassageFrame(
            (0.0, 0.0, 0.0),
            (0.0, 0.0, -1.0),
            (1.0, 0.0, 0.0),
            (0.0, -1.0, 0.0),
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
