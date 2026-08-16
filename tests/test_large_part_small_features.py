# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""Small features on large parts stay recognised.

Regression corpus for issue #72. 0.2.3 made minimum-evidence gates proportional to the part, so
a feature had to be roughly 0.7-0.9% of the part's largest dimension to be reported at all. On
parts bigger than the fixture corpus's 70 mm median that silently removed real features — six
NIST MBE PMI parts lost records in nineteen places and gained in none.

The distinction 0.2.3 missed, now recorded in ADR 0008:

*A tolerance* asks "are these two things the same?" and scales with the geometry it compares,
because measurement noise does.

*A minimum-evidence threshold* asks "is this big enough to be a feature?" and must not scale with
the **part**, because whether a 1 mm fillet on a 200 mm plate is worth dimensioning is consumer
policy — and ADR 0001 puts policy with the consumer, not here. The package reports the fillet.

Every part below is larger than the golden corpus and carries features smaller than it would
imply. That combination is what the fixtures never covered and what real parts are made of.
"""

from __future__ import annotations

import pytest
from build123d import Box, GeomType, Pos, chamfer, fillet

from b123d_recognisers import (
    recognise_chamfers,
    recognise_fillets,
    recognise_flats,
    recognise_grooves,
    recognise_plates,
    recognise_rectangular_pads,
)

LARGE = 200.0


def _edge_treated(op, size: float):
    block = Box(LARGE, LARGE, 60)
    edges = block.edges().filter_by(GeomType.LINE).group_by()[0]
    return op(edges, size)


def test_a_small_chamfer_on_a_large_part_is_still_a_chamfer():
    """1 mm chamfers on a 200 mm block. 0.2.3 returned none of the four."""

    assert len(recognise_chamfers(_edge_treated(chamfer, 1.0))) == 4


def test_a_small_fillet_on_a_large_part_is_still_a_fillet():
    """1 mm fillets on a 200 mm block. 0.2.3 returned none of the four."""

    assert len(recognise_fillets(_edge_treated(fillet, 1.0))) == 4


def test_a_thin_slab_in_a_large_part_is_still_a_plate():
    """The thickness gate is a minimum, so scaling it to the part erases thin plates."""

    part = Box(LARGE, LARGE, 2) + Pos(0, 0, 21) * Box(40, 40, 40)

    assert [p for p in recognise_plates(part) if p.axis == "z"]


def test_a_small_pad_on_a_large_part_is_still_a_pad():
    """The footprint gate is a minimum on both in-plane axes."""

    part = Box(LARGE, LARGE, 20) + Pos(0, 0, 11) * Box(5, 5, 2)

    assert recognise_rectangular_pads(part)


def test_a_shallow_flat_on_large_stock_is_still_a_flat():
    """``_MIN_FLAT_DEPTH`` scaled to the stock radius, so a shallow flat on big bar vanished.

    This one came from the *feature*-relative pass rather than the part-relative one, which is
    why the rule is about thresholds and not about which reference was used.
    """
    from build123d import Cylinder

    stock = Cylinder(25, 80)
    part = stock - Pos(24, 0, 0) * Box(4, 60, 100)

    assert recognise_flats(part)


@pytest.mark.parametrize("od", [15.0, 100.0, 300.0])
def test_a_shallow_groove_is_a_groove_on_stock_of_any_diameter(od):
    """Found by audit, not by a bug report — the NIST parts are prismatic and have no grooves.

    The step-depth and width margins are minimums, so scaling them to the wall diameter demanded
    a proportionally deeper groove on bigger stock. A 2 mm groove was found on 15 mm bar and lost
    on 100 mm.
    """
    from build123d import Cylinder

    shaft = Cylinder(od / 2, 20)
    shaft += Pos(0, 0, 12.5) * Cylinder(od / 2 - 1.0, 5)
    shaft += Pos(0, 0, 22.5) * Cylinder(od / 2, 20)

    assert len(recognise_grooves(shaft)) == 1


@pytest.mark.parametrize("extent", [80.0, 200.0, 600.0])
def test_the_same_feature_is_recognised_whatever_the_part_around_it(extent):
    """The property the fix restores: a 1 mm chamfer does not stop existing on a bigger plate.

    0.2.3 was scale-*invariant* for the feature and scale-*dependent* on its surroundings, which
    is the opposite of what ADR 0008 set out to achieve.
    """

    block = Box(extent, extent, 60)
    edges = block.edges().filter_by(GeomType.LINE).group_by()[0]

    assert len(recognise_chamfers(chamfer(edges, 1.0))) == 4
