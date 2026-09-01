"""Authored controls for the label-blind cavity-enclosure audit rule."""

from build123d import Box, Compound, Pos, Rot

from b123d_recognisers._adjacency import FaceGraph
from tools.audit_mfcadpp_cavity_enclosures import _candidate_regions


def _blind_pocket():
    return Box(60, 40, 20) - Pos(0, 0, 8) * Box(24, 12, 8)


def _through_passage():
    return Box(60, 40, 20) - Box(24, 12, 20)


def test_blind_and_through_cavities_form_one_bounded_region() -> None:
    for part in (_blind_pocket(), _through_passage()):
        graph = FaceGraph(part)
        regions = _candidate_regions(graph)
        assert len(regions) == 1
        region, owners = regions[0]
        assert owners
        assert graph.common_valid_solid(region | owners) is not None
        assert region < frozenset(graph.nodes)


def test_multiple_and_separate_body_cavities_remain_distinct() -> None:
    two = Box(80, 50, 20) - Pos(-22, 0, 8) * Box(16, 10, 8)
    two -= Pos(22, 0, 8) * Box(16, 10, 8)
    compound = Compound([_blind_pocket(), Pos(100, 0, 0) * _blind_pocket()])

    assert len(_candidate_regions(FaceGraph(two))) == 2
    graph = FaceGraph(compound)
    regions = _candidate_regions(graph)
    assert len(regions) == 2
    assert all(
        graph.common_valid_solid(region | owners) is not None
        for region, owners in regions
    )
    assert graph.common_valid_solid(regions[0][0] | regions[1][0]) is None


def test_intersecting_cavities_merge_instead_of_inventing_two_owners() -> None:
    crossed = Box(80, 60, 20) - Pos(0, 0, 8) * Box(44, 10, 8)
    crossed -= Pos(0, 0, 8) * Box(10, 44, 8)

    assert len(_candidate_regions(FaceGraph(crossed))) == 1


def test_rigid_transform_preserves_region_structure() -> None:
    part = _blind_pocket()
    transformed = Pos(17, -11, 9) * Rot(31, 17, 23) * part

    base = _candidate_regions(FaceGraph(part))
    moved = _candidate_regions(FaceGraph(transformed))
    assert [len(region) for region, _owners in base] == [
        len(region) for region, _owners in moved
    ]
    assert [len(owners) for _region, owners in base] == [
        len(owners) for _region, owners in moved
    ]
