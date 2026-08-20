# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""A complete recess boundary beats fragments assembled from selected wall pairs."""

from __future__ import annotations

from build123d import Box, BuildPart, BuildSketch, Plane, Polygon, Pos, extrude

import b123d_recognisers as r


def _u_void(*, blind: bool):
    """An eight-wall concave section with several opposed, axis-aligned wall pairs."""

    with BuildPart() as tool:
        with BuildSketch(Plane.XY):
            Polygon(
                (-15, -15),
                (15, -15),
                (15, 15),
                (9, 15),
                (9, -9),
                (-9, -9),
                (-9, 15),
                (-15, 15),
            )
        extrude(amount=14 if blind else 40, both=not blind)
    return Box(60, 60, 20) - (Pos(0, 0, -4) * tool.part if blind else tool.part)


def test_a_non_rectangular_passage_beats_slots_assembled_from_its_wall_pairs():
    """Three plausible pairs are still one eight-wall through void, not three slots."""

    part = _u_void(blind=False)
    assert len(r.recognise_slots(part)) == 3, "candidate discovery remains independent"
    assert [passage.sides for passage in r.recognise_passages(part)] == [8]

    result = r.build_recognition_result(part)
    assert result.slots == ()
    assert [passage.sides for passage in result.passages] == [8]


def test_a_non_rectangular_prismatic_pocket_beats_paired_wall_fragments():
    """The floor and complete ring describe one U pocket; three rectangles do not."""

    part = _u_void(blind=True)
    assert len(r.recognise_pockets(part)) == 3, "the pair recogniser proposes fragments"
    assert [pocket.sides for pocket in r.recognise_prismatic_pockets(part)] == [8]

    result = r.build_recognition_result(part)
    assert result.pockets == ()
    assert [pocket.sides for pocket in result.prismatic_pockets] == [8]
