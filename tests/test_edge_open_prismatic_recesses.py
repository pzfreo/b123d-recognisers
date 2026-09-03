import pytest

from b123d_recognisers.edge_open_prismatic_recesses import (
    EdgeOpenPrismaticRecess,
    OpenPolygonalSection,
    OpenSectionOpening,
)


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


def test_open_chain_and_opening_must_bound_a_simple_profile() -> None:
    chain = ((-2.0, 1.0), (2.0, -1.0), (-2.0, -1.0), (2.0, 1.0))

    with pytest.raises(ValueError, match="simple profile"):
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
