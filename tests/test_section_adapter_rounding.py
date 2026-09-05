import pytest

from quiddity._section_adapters import (
    LegacySectionProjectionError,
    _normalise_published_section,
    legacy_section_geometry,
)
from quiddity._sections import PlanarSection, SectionVertex
from quiddity.passages import Passage
from quiddity.prismatic_pockets import PrismaticPocket


@pytest.mark.parametrize("axis", ["x", "y", "z"])
@pytest.mark.parametrize("offset", [0.0, 1.0, 10.0, 100.0])
@pytest.mark.parametrize("kind", ["passage", "pocket"])
def test_one_grid_cell_survives_translation_and_recentering(axis, offset, kind):
    section = ((offset, 0), (offset + 0.001, 0), (offset + 0.001, 2), (offset, 2))
    transverse = tuple(index for index in range(3) if index != "xyz".index(axis))
    centre = [0.0, 0.0, 0.0]
    centre[transverse[0]] = round(offset + 0.0005, 3)
    centre[transverse[1]] = 1.0
    record = (
        Passage(axis, 4, 1.0, tuple(centre), section)
        if kind == "passage"
        else PrismaticPocket(axis, 4, 1.0, 1, tuple(centre), section)
    )
    geometry = legacy_section_geometry(record)
    frame = geometry.frame
    rebuilt = tuple(
        tuple(
            frame.origin[index]
            + frame.u[index] * vertex.point[0]
            + frame.v[index] * vertex.point[1]
            for index in transverse
        )
        for vertex in geometry.profile.boundary
    )
    assert len(rebuilt) == 4
    for expected in section:
        assert any(point == pytest.approx(expected, abs=1e-12) for point in rebuilt)
    assert geometry.ends.low.condition == ("open" if kind == "passage" else "capped")
    assert geometry.ends.high.condition == "open"


@pytest.mark.parametrize(
    "points",
    [
        ((0, 0), (2, 0), (2, 2), (2, 2), (0, 2)),
        ((0, 0), (2, 0), (2, 1.9996), (1.9996, 2), (0, 2)),
        ((0, 0), (0.0004, 0), (2, 0), (2, 2), (0, 2)),
        ((0, 0), (2, 0), (2, 1), (2.001, 1), (2, 1), (2, 2), (0, 2)),
    ],
)
def test_grid_normalisation_removes_collapsed_edges_and_bounded_backtracking(points):
    expected = _normalise_published_section(points)
    assert expected.area == pytest.approx(4.0)
    assert len({vertex.point for vertex in expected.boundary}) == len(expected.boundary)
    for start in range(len(points)):
        rotated = points[start:] + points[:start]
        assert _normalise_published_section(rotated) == expected
        assert _normalise_published_section(tuple(reversed(rotated))) == expected


@pytest.mark.parametrize(
    ("points", "condition"),
    [
        (((0, 0), (0.0001, 0), (0, 0.0001)), "collapsed loop"),
        (((0, 0), (2, 2), (0, 2), (2, 0)), "invalid published loop"),
        (((0, 0), (2, 0), (1, 1), (2, 2), (0, 2), (1, 1)), "ambiguous topology"),
        (((0, 0), (2, 0), (2, 1), (3, 1), (2, 1), (2, 2), (0, 2)), "displacement bound"),
    ],
)
def test_unrepresentable_sections_have_bounded_adapter_refusals(points, condition):
    with pytest.raises(LegacySectionProjectionError, match=condition) as failure:
        _normalise_published_section(points)
    assert condition in failure.value.condition


def test_direct_section_producers_keep_strict_distinctness():
    with pytest.raises(ValueError, match="adjacent section vertices must be distinct"):
        PlanarSection(tuple(SectionVertex(point) for point in ((0, 0), (1, 0), (1, 0), (0, 1))))
