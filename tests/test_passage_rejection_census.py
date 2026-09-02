# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Geometry-only controls for the two-ended Passage rejection census."""

from __future__ import annotations

from build123d import Box, BuildPart, BuildSketch, Cylinder, Plane, Pos, RegularPolygon, extrude

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._section_passages import (
    _BodyAdapter,
    _enclosure_proposals,
    _mouth_regions,
    section_ring_proposals,
)
from tools.audit_mfcadpp_cavity_enclosures import _two_ended_regions
from tools.audit_mfcadpp_passage_rejections import _classify_region


def _tool(sides: int):
    with BuildPart() as tool:
        with BuildSketch(Plane.XY):
            RegularPolygon(7, sides)
        extrude(amount=60, both=True)
    return tool.part


def _passage(*, interrupted: bool):
    result = Box(60, 50, 20) - _tool(6)
    return result - Pos(15, -8, 0) * Box(30, 6, 6) if interrupted else result


def _gates(part) -> list[str]:
    graph = FaceGraph(part)
    mouths = dict(_mouth_regions(graph))
    fallback = _enclosure_proposals(graph, _BodyAdapter())
    fallback_by_region = {proposal.constituent: proposal for proposal in fallback}
    final = section_ring_proposals(part, graph)
    existing_regions = frozenset(
        frozenset(proposal.nodes) for proposal in final if not proposal.constituent
    )
    final_regions = frozenset(
        proposal.constituent
        for proposal in final
        if proposal.constituent
    )
    return [
        _classify_region(
            graph,
            region,
            mouths.get(region),
            fallback_by_region,
            existing_regions,
            final_regions,
        )
        for region, _openings in _two_ended_regions(graph)
    ]


def test_census_distinguishes_new_fallback_from_existing_cycle() -> None:
    assert _gates(_passage(interrupted=True)) == ["accepted_fallback"]
    assert _gates(_passage(interrupted=False)) == ["duplicate_or_existing_cycle"]


def test_census_places_circular_bore_at_planar_seed_gate() -> None:
    assert _gates(Box(60, 50, 20) - Cylinder(7, 60)) == ["planar_mouth_seed"]
