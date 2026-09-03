import json
from pathlib import Path

import pytest
from build123d import (
    Align,
    Box,
    BuildPart,
    BuildSketch,
    Compound,
    Cylinder,
    Locations,
    Plane,
    Polygon,
    Pos,
    RegularPolygon,
    Rot,
    export_step,
    extrude,
    import_step,
)

from b123d_recognisers._adjacency import FaceGraph, FaceNode
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers.edge_open_prismatic_recesses import (
    EdgeOpenPrismaticRecess,
    OpenPolygonalSection,
    OpenSectionOpening,
    _complete_wall_boundaries,
    recognise_edge_open_prismatic_recesses,
)


def _edge_open_hexagon():
    stock = Box(40, 40, 20, align=(Align.CENTER, Align.CENTER, Align.MIN))
    with BuildPart() as cutter:
        with BuildSketch(Plane.XY.offset(10)), Locations((0, 14)):
            RegularPolygon(8, 7)
        extrude(amount=15)
    return stock - cutter.part


def _section() -> OpenPolygonalSection:
    chain = ((-2.0, 1.0), (-2.0, -1.0), (0.0, -2.0), (2.0, -1.0), (2.0, 1.0))
    return OpenPolygonalSection(chain, OpenSectionOpening(chain[-1], chain[0]))


def test_edge_open_record_serializes_the_opening_separately_from_walls() -> None:
    record = EdgeOpenPrismaticRecess("z", (2.0, 10.0), 1, _section())

    assert record.to_dict() == {
        "axis": "z",
        "run_interval": (2.0, 10.0),
        "open_sign": 1,
        "section": {
            "wall_chain": ((-2.0, 1.0), (-2.0, -1.0), (0.0, -2.0), (2.0, -1.0), (2.0, 1.0)),
            "opening": {"start": (2.0, 1.0), "end": (-2.0, 1.0)},
        },
    }


def test_opening_must_join_the_exact_chain_endpoints() -> None:
    chain = ((-2.0, 1.0), (-2.0, -1.0), (0.0, -2.0), (2.0, -1.0))

    with pytest.raises(ValueError, match="opening must run"):
        OpenPolygonalSection(chain, OpenSectionOpening(chain[0], chain[-1]))


def test_open_chain_direction_is_canonical() -> None:
    section = _section()
    reverse = tuple(reversed(section.wall_chain))

    with pytest.raises(ValueError, match="canonical direction"):
        OpenPolygonalSection(reverse, OpenSectionOpening(reverse[-1], reverse[0]))


def test_open_wall_chain_must_be_simple() -> None:
    chain = ((-2.0, 1.0), (2.0, -1.0), (-2.0, -1.0), (2.0, 1.0))

    with pytest.raises(ValueError, match="wall chain must be simple"):
        OpenPolygonalSection(chain, OpenSectionOpening(chain[-1], chain[0]))


@pytest.mark.parametrize(
    ("axis", "interval", "open_sign", "message"),
    [
        ("q", (2.0, 10.0), 1, "axis"),
        ("z", (2.0, 2.0), 1, "strictly increasing"),
        ("z", (2.0, 10.0), 0, "open_sign"),
    ],
)
def test_edge_open_record_refuses_invalid_occurrence_values(
    axis: str, interval: tuple[float, float], open_sign: int, message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        EdgeOpenPrismaticRecess(axis, interval, open_sign, _section())


def test_recognises_six_physical_walls_without_inventing_a_closing_wall() -> None:
    (found,) = recognise_edge_open_prismatic_recesses(_edge_open_hexagon())

    assert found.axis == "z"
    assert found.run_interval == (10.0, 20.0)
    assert found.open_sign == 1
    assert len(found.section.wall_chain) == 7
    assert found.section.opening == OpenSectionOpening(
        found.section.wall_chain[-1], found.section.wall_chain[0]
    )
    assert found.section.opening.start[1] == found.section.opening.end[1] == 20.0


def test_edge_open_payload_matches_dedicated_golden() -> None:
    expected = json.loads(
        (Path(__file__).parent / "edge_open_prismatic_recess_expected.json").read_text(
            encoding="utf-8"
        )
    )

    actual = json.loads(
        json.dumps(
            [
                record.to_dict()
                for record in recognise_edge_open_prismatic_recesses(_edge_open_hexagon())
            ]
        )
    )

    assert actual == expected


def test_closed_polygonal_pocket_is_not_edge_open() -> None:
    stock = Box(40, 40, 20, align=(Align.CENTER, Align.CENTER, Align.MIN))
    with BuildPart() as cutter:
        with BuildSketch(Plane.XY.offset(10)):
            RegularPolygon(8, 7)
        extrude(amount=15)

    assert recognise_edge_open_prismatic_recesses(stock - cutter.part) == []


@pytest.mark.parametrize(
    "chain",
    [
        ((-6, 20), (-6, 12), (0, 6), (6, 20)),
        ((-6, 20), (-7, 12), (0, 6), (6, 12), (6, 20)),
        ((-6, 20), (-8, 15), (-4, 8), (4, 8), (8, 15), (6, 20)),
        ((-6, 20), (-8, 15), (-6, 10), (0, 6), (6, 10), (8, 15), (6, 20)),
    ],
)
def test_polygonal_edge_open_profiles_retain_every_physical_wall(
    chain: tuple[tuple[int, int], ...],
) -> None:
    stock = Box(40, 40, 20, align=(Align.CENTER, Align.CENTER, Align.MIN))
    with BuildPart() as cutter:
        with BuildSketch(Plane.XY.offset(10)):
            Polygon(*chain)
        extrude(amount=15)

    (found,) = recognise_edge_open_prismatic_recesses(stock - cutter.part)

    assert len(found.section.wall_chain) == len(chain)


def test_floorless_edge_open_passage_is_refused() -> None:
    stock = Box(40, 40, 20, align=(Align.CENTER, Align.CENTER, Align.MIN))
    with BuildPart() as cutter:
        with BuildSketch(Plane.XY.offset(-5)), Locations((0, 14)):
            RegularPolygon(8, 7)
        extrude(amount=30)

    assert recognise_edge_open_prismatic_recesses(stock - cutter.part) == []


def test_a_cross_bore_interrupting_a_wall_is_refused() -> None:
    bore = Plane(origin=(-4.49, 8.36, 15), z_dir=(-0.625, -0.78, 0)) * Cylinder(
        1, 10, align=(Align.CENTER, Align.CENTER, Align.CENTER)
    )
    perforated = _edge_open_hexagon() - bore

    assert recognise_edge_open_prismatic_recesses(perforated) == []


def test_repeated_exterior_contact_on_an_endpoint_wall_is_refused() -> None:
    floor, *walls, mouth, exterior = (FaceNode(index) for index in range(9))
    wall_tuple = tuple(walls)

    class OneWire:
        @staticmethod
        def wires():
            return (object(),)

    class RepeatedBoundaryGraph:
        @staticmethod
        def face(_node):
            return OneWire()

        @staticmethod
        def neighbours(node):
            if node not in wall_tuple:
                return ()
            index = wall_tuple.index(node)
            adjacent = [floor, mouth]
            if index:
                adjacent.append(wall_tuple[index - 1])
            if index + 1 < len(wall_tuple):
                adjacent.append(wall_tuple[index + 1])
            if index in (0, len(wall_tuple) - 1):
                adjacent.append(exterior)
            return tuple(adjacent)

        @staticmethod
        def shared_edges(left, right):
            repeated = left is wall_tuple[0] and right is exterior
            return (object(), object()) if repeated else (object(),)

        @staticmethod
        def arc(_left, _right):
            return "convex"

    assert not _complete_wall_boundaries(
        RepeatedBoundaryGraph(), floor, wall_tuple, mouth, (exterior,)
    )


def test_parallel_endpoint_wall_supports_are_refused() -> None:
    stock = Box(40, 40, 20, align=(Align.CENTER, Align.CENTER, Align.MIN))
    with BuildPart() as cutter:
        with BuildSketch(Plane.XY.offset(10)):
            Polygon((-6, 20), (-6, 15), (-8, 12), (0, 6), (8, 12), (6, 15), (6, 20))
        extrude(amount=15)

    assert recognise_edge_open_prismatic_recesses(stock - cutter.part) == []


def test_shallow_nonparallel_endpoint_wall_supports_are_retained() -> None:
    stock = Box(40, 40, 20, align=(Align.CENTER, Align.CENTER, Align.MIN))
    with BuildPart() as cutter:
        with BuildSketch(Plane.XY.offset(10)):
            Polygon(
                (-6, 20), (-5.56, 15), (-8, 12), (0, 6), (8, 12), (6, 15), (6, 20)
            )
        extrude(amount=15)

    assert len(recognise_edge_open_prismatic_recesses(stock - cutter.part)) == 1


def test_edge_open_recognition_is_axis_covariant_and_body_local() -> None:
    first = _edge_open_hexagon()
    rotated = Rot(90, 0, 0) * first
    compound = Compound(children=[first, Pos(80, 0, 0) * first])

    (baseline,) = recognise_edge_open_prismatic_recesses(first)
    (covariant,) = recognise_edge_open_prismatic_recesses(rotated)
    separate = recognise_edge_open_prismatic_recesses(compound)

    assert baseline.axis != covariant.axis
    assert baseline.run_interval[1] - baseline.run_interval[0] == (
        covariant.run_interval[1] - covariant.run_interval[0]
    )
    assert len(separate) == 2


def test_edge_open_recess_survives_step_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "edge-open-prismatic-recess.step"
    assert export_step(_edge_open_hexagon(), path)

    (record,) = recognise_edge_open_prismatic_recesses(import_step(path))

    assert (
        record.to_dict()
        == recognise_edge_open_prismatic_recesses(_edge_open_hexagon())[0].to_dict()
    )


def test_edge_open_recess_publishes_exact_body_local_evidence() -> None:
    part = _edge_open_hexagon()
    ledger = ClaimLedger(FaceGraph(part))

    (record,) = recognise_edge_open_prismatic_recesses(part, ledger=ledger)
    (candidate,) = ledger.candidate_set(FamilyId.EDGE_OPEN_PRISMATIC_RECESSES).candidates
    evidence = ledger.snapshot_index()

    assert candidate.record == record
    assert len(evidence.defining_of(candidate)) == 6
    assert len(evidence.constituent_of(candidate)) == 7
    assert ledger.graph.common_valid_solid(evidence.constituent_of(candidate)) is not None
