# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""Pockets of any prismatic cross-section, found by walking a ring rather than pairing walls.

A **prismatic pocket** is a closed ring of planar walls with a floor filling one end and the
other end open: the capped sibling of :class:`b123d_recognisers.Passage`, and the same feature
MFCAD++ labels *Triangular pocket*, *6-sided pocket* and *Rectangular pocket*.

**Why a second pocket family rather than an extension of the first.**
:func:`b123d_recognisers.recognise_pockets` finds a recess by sorting walls into buckets by the
axis their normal aligns with and pairing walls within a bucket. A triangular recess has no two
walls sharing an axis, so no pair forms and no gate ever runs -- measured over 600 MFCAD++
models, **94% of triangular-pocket faces never reach a test**, which is why that family scores 0%
on them and 4% on hexagonal ones. Nothing about the geometry is hard; the search cannot see it.

Ring-walking has no such blind spot, and this is not a hope: `recognise_passages` already walks
these exact rings and scores 59% on triangular passages, on the same solids where pairing scores
0% on triangular pockets. It also already *finds* these pockets and discards them -- the line
that did so read ``continue  # a floor fills the ring: this is a pocket``.

**What each family is for.** They are not redundant, and neither is going away:

- this one reaches any planar cross-section, and is the only path to a non-rectangular recess;
- :func:`b123d_recognisers.recognise_pockets` reaches recesses this cannot -- an obround pocket's
  ends are cylindrical, so its walls form no closed *planar* ring at all. Measured: **zero** rings
  on the *Circular end pocket* class, which the pairing family recognises.

Where both see the same rectangular recess, both report it. That overlap is a reconciliation
question and is answered by
:func:`b123d_recognisers._reconcile.prismatic_pockets_that_are_not_pockets`, from the faces
each family claimed -- not by either recogniser declining a face because the other might want
it, which ADR 0003 forbids.

Ring-finding, the cross-section walk and the cap test are
:mod:`b123d_recognisers._rings`, shared with ``passages``.
"""

from __future__ import annotations

from dataclasses import dataclass

from b123d_recognisers._adjacency import FaceEdges, FaceGraph
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._record import Record
from b123d_recognisers._rings import _centroid, rings
from b123d_recognisers._typing import Part


@dataclass(frozen=True, order=True)
class PrismaticPocket(Record):
    """A floored recess of constant planar cross-section, open at one end.

    ``axis`` is the direction the walls run ("x"/"y"/"z"); ``sides`` is the number of walls, so
    a triangular pocket reports 3 and a hexagonal one 6; ``depth`` is how far it runs from the
    open end down to the floor; ``at`` is the centre of the void in part space; ``open_sign`` is
    ``+1`` when the opening is at the high end of ``axis`` and ``-1`` at the low end.

    ``section`` is the cross-section: its corners in part coordinates, in the two axes other
    than ``axis`` and in that axis order, walked around the ring. It is carried for the reason
    :class:`b123d_recognisers.Passage` carries one -- without it a triangular pocket and a
    hexagonal one of the same depth differ only in ``sides``, and the shape a machinist needs to
    see is gone.

    **Not a :class:`b123d_recognisers.Pocket`, deliberately.** That record measures ``width`` and
    ``length`` on two named axes, which is a true statement about a rectangular recess and a
    meaningless one about a triangle. Folding these in would have made ``Pocket.width`` sometimes
    a wall-to-wall measurement and sometimes a bounding-box extent, with no way for a caller
    reading it to tell -- a change of meaning for every existing consumer, including those that
    only ever see rectangular pockets. Two sibling records under one field cost a consumer
    nothing it is not already paying.

    The corner walk is canonical rather than the kernel's, as ``Passage``'s is: equivalent
    geometry gives an equal record however the part was traversed.
    """

    axis: str
    sides: int
    depth: float
    open_sign: int
    at: tuple[float, float, float]
    section: tuple[tuple[float, float], ...]


def recognise_prismatic_pockets(
    part: Part,
    *,
    face_edges: FaceEdges | None = None,
    ledger: ClaimLedger | None = None,
) -> list[PrismaticPocket]:
    """Recognise the prismatic pockets of *part* (see module docstring).

    Returns one :class:`PrismaticPocket` per ring capped at exactly one end, sorted
    deterministically. A ring capped at *both* ends is an enclosed cavity and is not reported by
    any family here: it is not reachable by a tool, so it is not a machined recess, and reporting
    one would be asserting a feature that cannot have been cut.

    **A rectangular recess is reported here as well as by**
    :func:`b123d_recognisers.recognise_pockets`, because on the ring alone it is one. Which
    survives is
    :func:`b123d_recognisers._reconcile.prismatic_pockets_that_are_not_pockets`, decided from
    the claims rather than by either family second-guessing the other.

    *ledger* records the faces the pocket was **established by**: its ring walls. The floor is
    *consulted* -- it is what makes the recess blind, and `depth` is the walls' own span rather
    than a measurement off it -- so it is not claimed, the same line
    :func:`b123d_recognisers.recognise_pockets` draws for the recess it finds by pairing.
    """

    graph = FaceGraph(part, face_edges=face_edges) if ledger is None else ledger.graph
    found: list[tuple[PrismaticPocket, tuple]] = []
    for ring in rings(part, graph):
        low_capped, high_capped = ring.caps
        if low_capped == high_capped:
            continue  # neither: a passage. Both: an enclosed cavity, which no tool reaches.
        axis, section = ring.axis, ring.section
        others = [a for a in (0, 1, 2) if a != axis]
        middle = _centroid(section)
        at = [0.0, 0.0, 0.0]
        at[axis] = 0.5 * (ring.low + ring.high)
        at[others[0]], at[others[1]] = middle
        found.append(
            (
                PrismaticPocket(
                    axis="xyz"[axis],
                    sides=len(ring.nodes),
                    depth=round(ring.high - ring.low, 3),
                    # The floor caps one end, so the opening is the other.
                    open_sign=1 if low_capped else -1,
                    at=(round(at[0], 3), round(at[1], 3), round(at[2], 3)),
                    section=tuple((round(u, 3), round(v, 3)) for u, v in section),
                ),
                tuple(ring.nodes),
            )
        )

    found.sort(key=lambda pair: (pair[0].axis, pair[0].at))
    if ledger is not None:
        for pocket, nodes in found:
            ledger.add_defining(pocket, nodes)
    return [pocket for pocket, _ in found]
