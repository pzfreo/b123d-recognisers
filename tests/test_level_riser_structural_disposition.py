"""Bounded proofs for the Step Level and Riser structural attribution exclusions."""

from __future__ import annotations

from copy import deepcopy

from build123d import Box, Compound, Pos

from b123d_recognisers import recognise_risers
from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._registry import PHYSICAL_DEFINITIONS, IncompleteAttribution, NotCounted
from b123d_recognisers.levels import step_level_records
from b123d_recognisers.result import _take_inventory


def _step():
    return Box(60, 40, 10) + Pos(-15, 0, 10) * Box(30, 40, 10)


def _equal_same_solid_ramps():
    return Box(60, 40, 20) - Pos(0, 0, 5) * Box(0.0008, 40, 10)


def test_step_level_whole_part_cluster_has_no_single_solid_owner() -> None:
    part = Compound([_step(), Pos(100, 0, 0) * _step()])
    records = step_level_records(part)
    assert records
    graph = FaceGraph(part)
    record = records[0]
    nodes = frozenset(
        node
        for node in graph.nodes
        if graph.is_planar(node) and abs(sum(graph.bounds(node)[2]) / 2 - record.z) <= 0.5
    )
    owners = {graph.common_valid_solid((node,)) for node in nodes}
    assert len(owners - {None}) == 2
    assert graph.common_valid_solid(nodes) is None


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


def test_riser_equal_value_across_solids_has_no_common_owner() -> None:
    first = _step()
    part = Compound([first, deepcopy(first)])
    assert len(recognise_risers(part)) == 1
    graph = FaceGraph(part)
    nodes = frozenset(
        node
        for node in graph.nodes
        if graph.is_planar(node) and graph.bounds(node)[0][0] == graph.bounds(node)[0][1] == 0.0
    )
    assert len(nodes) == 2
    assert all(graph.common_valid_solid((node,)) is not None for node in nodes)
    assert graph.common_valid_solid(nodes) is None


def test_aggregate_remains_writer_free_complete_and_result_exact() -> None:
    part = _step()
    public_risers = tuple(recognise_risers(part))
    public_levels = tuple(step_level_records(part))
    product = _take_inventory(part)
    assert product.result.risers == public_risers
    assert product.result.step_levels == public_levels
    for family in (FamilyId.STEP_LEVELS, FamilyId.RISERS):
        candidates = product.physical.candidate_set(family).candidates
        assert candidates
        assert all(
            product.evidence.defining_of(candidate) == frozenset() for candidate in candidates
        )
    assert product.diagnostics == ()


def test_dispositions_and_census_reasons_are_exact() -> None:
    definitions = {item.family: item for item in PHYSICAL_DEFINITIONS}
    for family in (FamilyId.STEP_LEVELS, FamilyId.RISERS):
        assert isinstance(definitions[family].attribution, IncompleteAttribution)
        assert isinstance(definitions[family].census, NotCounted)
    assert "multiple SolidRefs" in definitions[FamilyId.STEP_LEVELS].attribution.reason
    assert "deduplication" in definitions[FamilyId.RISERS].attribution.reason
