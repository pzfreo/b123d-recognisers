# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""An angled blind step, and the line between it and a chamfer.

Every test here is built around one pair of parts: the same 45° wedge taken out of the same
edge of the same block, once stopping inside the part and once running right through. That
pairing is the point. The two differ in exactly one way — whether a triangular flat closes
the end — and nothing else about them changes, so a test that passes on one and fails on the
other has isolated the discriminator rather than some incidental property of the geometry.

Deliberately *not* a size distinction. The legs, angle, block and orientation are identical
across the pair; only the topology differs. If the recogniser ever started separating these
two on size, the equal-legs assertions here would keep passing and
``test_length_alone_does_not_decide_which_family_claims_a_slant`` would fail.
"""

from __future__ import annotations

from build123d import Axis, Box, Cylinder, Pos, Rot, chamfer

from b123d_recognisers import (
    AngledStep,
    recognise_angled_steps,
    recognise_chamfers,
)
from b123d_recognisers._adjacency import FaceEdges

#: A 45° wedge whose in-plane legs are both 4 mm: rotating a square 45° puts its half-diagonal
#: on each axis, so a side of 4·√2 cuts 4 mm into each of the two faces meeting at the edge.
_WEDGE = 5.657


def _block() -> Box:
    return Box(60, 40, 12)


def _blind(length: float = 30.0, at_x: float = -20.0):
    """The wedge stopped inside the part: open where it runs off the -X end, closed by a
    triangular flat at its +X end."""

    return _block() - Pos(at_x, 20, 6) * Rot(45, 0, 0) * Box(length, _WEDGE, _WEDGE)


def _through():
    """The same wedge run edge to edge, so neither end is closed — a chamfer."""

    return _block() - Pos(0, 20, 6) * Rot(45, 0, 0) * Box(70, _WEDGE, _WEDGE)


def test_a_wedge_stopped_inside_the_part_is_an_angled_step():
    """The blind end is what makes it a step, and the record carries how far it runs.

    ``length`` is the field a chamfer has no use for: a chamfer spans its whole edge, so its
    extent is not a chosen dimension. Here it is, and it is the reason a consumer can call
    the feature out at all.
    """

    steps = recognise_angled_steps(_blind())

    assert len(steps) == 1
    step = steps[0]
    assert step.axis == "x"
    assert (step.leg1, step.leg2) == (4.0, 4.0)
    assert step.angle == 45.0
    # The cutter spans x = -35..-5 and the block stops at -30, so 25 mm of it is inside.
    assert step.length == 25.0


def test_the_same_wedge_run_through_is_a_chamfer_and_not_a_step():
    """The control. Identical legs, identical angle, identical block — only the end differs."""

    assert recognise_angled_steps(_through()) == []

    chamfers = recognise_chamfers(_through())
    assert len(chamfers) == 1
    assert (chamfers[0].leg1, chamfers[0].leg2) == (4.0, 4.0)


def test_the_two_families_never_claim_the_same_face():
    """The reconciliation the shared companion test exists to guarantee.

    ``recognise_chamfers`` declines a bevel with a triangular companion and
    ``recognise_angled_steps`` requires one. If those two ever disagreed the face would be
    reported twice, or — worse and quieter — by neither. Checked in both directions on the
    pair, and on a part carrying one of each so the exclusion is not an artefact of there
    being only one bevel to argue over.
    """

    assert recognise_chamfers(_blind()) == []
    assert recognise_angled_steps(_through()) == []

    both = _blind() - Pos(0, -20, 6) * Rot(45, 0, 0) * Box(70, _WEDGE, _WEDGE)
    steps, chamfers = recognise_angled_steps(both), recognise_chamfers(both)

    assert len(steps) == 1, "the blind wedge must survive alongside a through one"
    assert len(chamfers) == 1, "the through wedge must survive alongside a blind one"
    assert steps[0].at != chamfers[0].at


def test_length_alone_does_not_decide_which_family_claims_a_slant():
    """A long blind step stays a step; a short through bevel stays a chamfer.

    This is the test that fails if the discriminator is ever quietly replaced by a size gate.
    The blind wedge here is *longer* than the part is wide in Y and cuts deeper than the
    chamfer above, and it is still a step; the through wedge is tiny and still a chamfer.
    """

    long_blind = _block() - Pos(-5, 20, 6) * Rot(45, 0, 0) * Box(45, 11.314, 11.314)
    small_through = _block() - Pos(0, -20, 6) * Rot(45, 0, 0) * Box(70, 1.414, 1.414)

    steps = recognise_angled_steps(long_blind)
    assert len(steps) == 1 and steps[0].leg1 == 8.0
    assert recognise_chamfers(long_blind) == []

    assert recognise_angled_steps(small_through) == []
    assert len(recognise_chamfers(small_through)) == 1


def test_a_pocket_wall_is_not_an_angled_step_though_it_has_a_triangular_floor():
    """The gate that a triangular companion alone cannot supply.

    A pocket whose plan is not axis-aligned has oblique planar walls over a triangular floor
    — the angled step's exact signature, minus convexity. Prototyped without the convex
    probe, triangular pockets outnumbered real steps three to one on the MFCAD++ corpus,
    so this is the difference between a 100%-precision recogniser and a 21% one.
    """

    pocket = _block() - Pos(0, 0, 6) * Rot(0, 0, 30) * Box(20, 14, 6)

    assert recognise_angled_steps(pocket) == []


def test_a_step_is_a_step_at_any_scale():
    """No gate here mentions the part, so scaling the whole model changes nothing.

    A size-based discriminator could not promise this — and the rejected alternative to this
    recogniser was exactly that. Built at 1× and 20×, the records must agree once the 20×
    part's lengths are divided back down.
    """

    small = recognise_angled_steps(_blind())
    big = recognise_angled_steps(
        Box(1200, 800, 240) - Pos(-400, 400, 120) * Rot(45, 0, 0) * Box(600, 113.14, 113.14)
    )

    assert len(small) == len(big) == 1
    assert small[0].axis == big[0].axis
    assert small[0].angle == big[0].angle
    assert round(big[0].leg1 / 20, 3) == small[0].leg1
    assert round(big[0].length / 20, 3) == small[0].length


def test_records_are_ordered_deterministically_and_are_plain_data():
    """Two steps on one part come back in a stable order that does not depend on traversal."""

    part = _blind() - Pos(20, -20, 6) * Rot(45, 0, 0) * Box(30, _WEDGE, _WEDGE)
    steps = recognise_angled_steps(part)

    assert len(steps) == 2
    assert steps == sorted(steps, key=lambda s: (s.axis, s.at))
    assert all(isinstance(s, AngledStep) for s in steps)
    assert recognise_angled_steps(part) == steps


def test_a_part_with_no_oblique_face_has_no_angled_steps():
    """The empty case, on geometry that exercises the scan rather than skipping it."""

    assert recognise_angled_steps(_block() - Pos(0, 0, 0) * Cylinder(6, 12)) == []


def test_a_shared_face_edge_memo_does_not_change_the_result():
    """``face_edges=`` is an optimisation, never a behaviour switch — the census shares one
    memo across every recogniser, so a mis-keyed lookup here would show up as a changed
    record count rather than as an exception."""

    part = chamfer(_blind().edges().filter_by(Axis.Z).group_by(Axis.X)[0], 1.5)
    plain = recognise_angled_steps(part)

    assert plain, "the fixture must reach the scan for this comparison to mean anything"
    assert plain == recognise_angled_steps(part, face_edges=FaceEdges())
