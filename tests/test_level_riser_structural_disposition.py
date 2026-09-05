"""Bounded proofs for the Step Level and Riser structural attribution exclusions."""

from __future__ import annotations

from copy import deepcopy

from build123d import Box, Compound, Pos

from quiddity import recognise_risers
from quiddity._adjacency import FaceGraph
from quiddity._candidates import FamilyId
from quiddity._registry import (
    PHYSICAL_DEFINITIONS,
    FullyAttributed,
    NotCounted,
)
from quiddity.levels import step_level_records
from quiddity.result import _take_inventory


def _step():
    return Box(60, 40, 10) + Pos(-15, 0, 10) * Box(30, 40, 10)


def _equal_same_solid_ramps():
    return Box(60, 40, 20) - Pos(0, 0, 5) * Box(0.0008, 40, 10)


def test_step_level_compound_occurrences_each_have_one_solid_owner() -> None:
    part = Compound([_step(), Pos(100, 0, 0) * _step()])
    product = _take_inventory(part)
    candidates = product.physical.candidate_set(FamilyId.STEP_LEVELS).candidates

    assert len(candidates) == 2
    owners = {
        product.context.graph.common_valid_solid(product.evidence.defining_of(candidate))
        for candidate in candidates
    }
    assert None not in owners
    assert len(owners) == 2


def test_riser_equal_value_can_mean_two_faces_on_one_solid_without_a_winner() -> None:
    part = _equal_same_solid_ramps()
    (record,) = recognise_risers(part, min_area_frac=0.0)
    original = type(part).faces
    type(part).faces = lambda self: list(reversed(original(self)))
    try:
        assert recognise_risers(part, min_area_frac=0.0) == [record]
    finally:
        type(part).faces = original
    graph = FaceGraph(_equal_same_solid_ramps())
    matching = frozenset(
        node
        for node in graph.nodes
        if graph.is_planar(node)
        and round(sum(graph.bounds(node)[0]) / 2, 3) == record.positions[0]
        and graph.bounds(node)[0][0] == graph.bounds(node)[0][1]
        and graph.bounds(node)[2][0] == record.z_lo
        and graph.bounds(node)[2][1] == record.z_hi
    )
    assert len(matching) == 2
    assert graph.common_valid_solid(matching) is not None
    product = _take_inventory(_equal_same_solid_ramps())
    (candidate,) = product.physical.candidate_set(FamilyId.RISERS).candidates
    assert len(product.evidence.defining_of(candidate)) == 2


def test_riser_equal_value_across_solids_has_no_common_owner() -> None:
    first = _step()
    part = Compound([first, deepcopy(first)])
    product = _take_inventory(part)
    candidates = product.physical.candidate_set(FamilyId.RISERS).candidates

    assert len(recognise_risers(part)) == len(candidates) == 2
    owners = {
        product.context.graph.common_valid_solid(product.evidence.defining_of(candidate))
        for candidate in candidates
    }
    assert None not in owners
    assert len(owners) == 2


def test_aggregate_remains_writer_free_complete_and_result_exact() -> None:
    part = _step()
    public_risers = tuple(recognise_risers(part))
    public_levels = tuple(step_level_records(part))
    product = _take_inventory(part)
    assert product.result.risers == public_risers
    assert product.result.step_levels == public_levels
    level_candidates = product.physical.candidate_set(FamilyId.STEP_LEVELS).candidates
    assert level_candidates
    assert all(product.evidence.defining_of(candidate) for candidate in level_candidates)
    riser_candidates = product.physical.candidate_set(FamilyId.RISERS).candidates
    assert riser_candidates
    assert all(product.evidence.defining_of(candidate) for candidate in riser_candidates)
    assert product.diagnostics == ()


def test_dispositions_and_census_reasons_are_exact() -> None:
    definitions = {item.family: item for item in PHYSICAL_DEFINITIONS}
    assert isinstance(definitions[FamilyId.STEP_LEVELS].attribution, FullyAttributed)
    assert isinstance(definitions[FamilyId.RISERS].attribution, FullyAttributed)
    for family in (FamilyId.STEP_LEVELS, FamilyId.RISERS):
        assert isinstance(definitions[family].census, NotCounted)
    assert "body-local" in definitions[FamilyId.STEP_LEVELS].attribution.proof_contract
    assert "producing faces" in definitions[FamilyId.RISERS].attribution.proof_contract
