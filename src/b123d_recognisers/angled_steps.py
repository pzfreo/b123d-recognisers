# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""Angled blind step recognition for prismatic parts.

An **angled blind step** is a wedge taken out of an edge of the part: one oblique planar
wall, stopping part-way along the edge, with a triangular flat closing the blind end. Milled
as an angled shoulder or a lead-in ramp, it is the feature MFCAD++ calls a *triangular blind
step*.

Geometrically it is the same read as a chamfer — an oblique planar face bridging two
mutually-perpendicular axis-aligned faces at a convex corner — and that is exactly why it
needs recognising. Before this module existed ``recognise_chamfers`` reported these slants
as chamfers, because nothing distinguished them. Measured over 60 MFCAD++ models, **9 of
the 10 models carrying one had their step's slant reported as their only chamfer**, while
the genuine chamfers on the same parts were rejected.

The distinction is **not** size. That was the tempting answer and it does not survive
measurement: the legs of the two populations overlap on every part-relative and
neighbour-relative ratio tried, and a threshold that separated them on one corpus would be
fitted to that corpus. The distinction is topological — **a chamfer runs the full length of
the edge it breaks; an angled step stops, and something has to close the end.** That
something is a triangular flat, and :func:`b123d_recognisers._adjacency.has_triangular_companion`
is the whole discriminator. It says nothing about the part around the face, so a step is a
step at any scale, which a size gate could never promise.

Three gates, all shared with :func:`b123d_recognisers.recognise_chamfers` so the two cannot
disagree about what they are looking at:

- **an oblique bevel** — :func:`b123d_recognisers.classify_bevel`, so the slant is a planar
  face running along exactly one principal axis;
- **convex** — :func:`b123d_recognisers.chamfers.convex_bevel`. Without it a triangular
  *pocket* whose plan is not axis-aligned matches perfectly: its walls are oblique planes
  and its floor is a triangle. Prototyped without this gate, 70% of what the signature
  caught were pockets; with it, precision over 120 models is 100%;
- **a triangular companion** — the blind end.

No size gate, no tolerance, no fraction: every gate here is either a shared geometric
classification or a count of edges.

Depends on ``chamfers`` for the bevel read and the convexity probe rather than copying
either, so a change to what counts as a bevel reaches both recognisers at once.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from b123d_recognisers._adjacency import (
    FaceEdges,
    edge_face_map,
    has_triangular_companion,
    nearest_axis_aligned_planes,
)
from b123d_recognisers._record import Record
from b123d_recognisers._typing import Part
from b123d_recognisers.chamfers import BevelReject, classify_bevel, convex_bevel


@dataclass(frozen=True, order=True)
class AngledStep(Record):
    """A recognised angled blind step. ``axis`` is the direction the slant runs along
    ("x"/"y"/"z"); ``leg1``/``leg2`` are the cut depths into the two adjacent faces
    (``leg1`` the larger); ``angle`` is the slant angle in degrees (45 for equal-leg);
    ``length`` is how far the step runs before its blind end; ``at`` is the slant face
    centre in part space (the callout leader's tip).

    The fields mirror :class:`b123d_recognisers.Chamfer` because the geometry is the same
    read — ``length`` is the addition, and it is the field a chamfer has no use for: a
    chamfer runs the whole edge, so its length is not a chosen dimension.
    """

    axis: str
    leg1: float
    leg2: float
    angle: float
    length: float
    at: tuple[float, float, float]


def recognise_angled_steps(
    part: Part,
    *,
    face_edges: FaceEdges | None = None,
) -> list[AngledStep]:
    """Recognise the angled blind steps of *part* (see module docstring). Returns one
    :class:`AngledStep` per qualifying slant face, sorted deterministically. Empty when the
    part has none. Only single-axis slants (running along one principal axis) are recovered;
    a step whose blind end is closed by anything other than a triangular flat is not one —
    that end is what makes the feature blind, and without it the slant is a chamfer or a
    through step."""

    all_faces = list(part.faces())
    edge_faces = edge_face_map(all_faces, face_edges=face_edges)

    out: list[AngledStep] = []
    for f in all_faces:
        try:
            edge_i, _nv, span, leg_hi, leg_lo = classify_bevel(f)
        except BevelReject:
            continue
        oi = [j for j in (0, 1, 2) if j != edge_i]
        fc = {i: 0.5 * (span[i][0] + span[i][1]) for i in (0, 1, 2)}  # face centre
        neigh_coord = nearest_axis_aligned_planes(
            f, edge_faces, fc, exclude_axis=edge_i, face_edges=face_edges
        )
        if oi[0] not in neigh_coord or oi[1] not in neigh_coord:
            continue
        if not convex_bevel(part, fc, edge_i, neigh_coord):
            continue  # concave — a pocket or passage wall, not a step
        if not has_triangular_companion(f, edge_faces, face_edges=face_edges):
            continue  # runs edge to edge — a chamfer, and `recognise_chamfers` owns it
        fctr = f.center()
        out.append(
            AngledStep(
                axis="xyz"[edge_i],
                leg1=round(leg_hi, 3),
                leg2=round(leg_lo, 3),
                angle=round(math.degrees(math.atan2(leg_lo, leg_hi)), 2),
                length=round(span[edge_i][1] - span[edge_i][0], 3),
                at=(round(fctr.X, 3), round(fctr.Y, 3), round(fctr.Z, 3)),
            )
        )
    return sorted(out, key=lambda s: (s.axis, s.at))
