# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""Prismatic passage recognition: a polygonal void running through the material.

A **passage** is a closed ring of planar walls with nothing capping either end. MFCAD++ splits
them by cross-section -- triangular, rectangular, six-sided -- but the geometry does not: they
are one shape with a side count, and measured over 120 of its models the count is exactly the
polygon's, 3 in 74 of 91 triangular instances, 4 in 40 of 64 rectangular, 6 in 46 of 60
six-sided.

What separates a passage from its neighbours is what is *not* there:

- **from a pocket, the floor.** A pocket's ring is capped at one end by a face perpendicular to
  the run axis and filling the ring's cross-section. A passage's is capped at neither end.
  Distinguishing that cap from the part's own end face matters and is easy to get wrong: at a
  passage mouth the outer face is perpendicular and edge-adjacent too, so the test is whether
  it *fills* the ring or the ring is a hole punched through it.
- **from a polygonal boss, the material.** The same ring bounds a prism when the material is
  inside it and a void when the material is outside, which one solid-classifier probe answers.

Over 120 MFCAD++ models: 100% precision, 51% instance recall (65 of 128) and 49% of
labelled faces. What is missed is one thing rather than many -- walls whose spans differ,
because a passage running through a stepped region has one wall shorter than the rest, so the
ring never forms.

Every gate is topological or a direction comparison. There is no size gate and no tolerance on
a length, so a passage is a passage at any scale -- ``tests/test_scale_invariance.py`` carries
the family with no exclusion.

Ring-finding is :func:`b123d_recognisers._adjacency.connected_components`, shared with
``polygonal_bosses``, which finds the same ring from outside. Two implementations of one walk
is the defect the adjacency work exists to remove.
"""

from __future__ import annotations

from dataclasses import dataclass

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepClass3d import BRepClass3d_SolidClassifier
from OCP.GeomAbs import GeomAbs_Plane
from OCP.gp import gp_Pnt
from OCP.TopAbs import TopAbs_IN

from b123d_recognisers._adjacency import (
    FaceEdges,
    connected_components,
    edge_face_map,
    neighbours,
)
from b123d_recognisers._geometry import AXIS_ZERO_COS
from b123d_recognisers._record import Record
from b123d_recognisers._typing import Part

#: Two walls belong to one ring when their spans along the run axis agree. A coordinate
#: comparison between two faces of one feature, so ADR 0008 makes it a tolerance rather than a
#: minimum-evidence threshold -- but it compares two derivations of the *same* extrusion, which
#: differ only by kernel noise, so it is a float epsilon and not a length at all.
_SPAN_EPS = 1e-6

#: How close a ring centre must sit to a slot's centre to be the same feature. A comparison
#: between two derivations of one void, so it is a tolerance rather than a minimum-evidence
#: threshold under ADR 0008 -- and both come from the same bounding boxes, so it is a float
#: epsilon rather than a length.
_SAME_FEATURE_EPS = 1e-6


@dataclass(frozen=True, order=True)
class Passage(Record):
    """A recognised passage. ``axis`` is the direction it runs ("x"/"y"/"z"); ``sides`` is the
    number of walls, so a triangular passage reports 3 and a hexagonal one 6; ``length`` is how
    far it runs; ``at`` is the centre of the void in part space."""

    axis: str
    sides: int
    length: float
    at: tuple[float, float, float]


def recognise_passages(
    part: Part,
    *,
    slots: list | None = None,
    face_edges: FaceEdges | None = None,
) -> list[Passage]:
    """Recognise the prismatic passages of *part* (see module docstring). Returns one
    :class:`Passage` per closed uncapped ring, sorted deterministically. Empty when the part has
    none. Only passages whose walls all run parallel to one principal axis and share one span
    are recovered; a passage whose walls step or taper along its length is not one."""

    claimed = _slot_centres(part if slots is None else None, slots)
    faces = list(part.faces())
    edge_faces = edge_face_map(faces, face_edges=face_edges)
    index = {face: i for i, face in enumerate(faces)}
    adjacent = {
        i: {index[other] for other in neighbours(face, edge_faces, face_edges=face_edges)
            if other in index}
        for i, face in enumerate(faces)
    }

    normal: dict[int, tuple[float, float, float]] = {}
    box: dict[int, tuple] = {}
    for i, face in enumerate(faces):
        if BRepAdaptor_Surface(face.wrapped).GetType() != GeomAbs_Plane:
            continue
        try:
            unit = face.normal_at()
        except Exception:  # noqa: BLE001 - a degenerate face has no normal to read
            continue
        normal[i] = (unit.X, unit.Y, unit.Z)
        bb = face.bounding_box()
        box[i] = ((bb.min.X, bb.max.X), (bb.min.Y, bb.max.Y), (bb.min.Z, bb.max.Z))

    out: list[Passage] = []
    for axis in (0, 1, 2):
        walls = [i for i in normal if abs(normal[i][axis]) <= AXIS_ZERO_COS]

        def shares_a_span(a: int, b: int, axis: int = axis) -> bool:
            return (
                b in adjacent[a]
                and abs(box[a][axis][0] - box[b][axis][0]) <= _SPAN_EPS
                and abs(box[a][axis][1] - box[b][axis][1]) <= _SPAN_EPS
            )

        for ring in connected_components(walls, shares_a_span):
            members = set(ring)
            if len(ring) < 3 or any(len(adjacent[i] & members) != 2 for i in ring):
                continue  # a ring closes; a chain of walls does not
            spans = [box[i][axis] for i in ring]
            low, high = min(a for a, _ in spans), max(b for _, b in spans)
            if _capped(ring, members, axis, low, high, adjacent, normal, box, faces):
                continue  # a floor fills the ring: this is a pocket
            middles = [
                sum(getattr(faces[i].center(), "XYZ"[k]) for i in ring) / len(ring)
                for k in (0, 1, 2)
            ]
            centre = (middles[0], middles[1], middles[2])
            if any(
                abs(centre[0] - c[0]) <= _SAME_FEATURE_EPS
                and abs(centre[1] - c[1]) <= _SAME_FEATURE_EPS
                for c in claimed
            ):
                continue  # `recognise_slots` already reports this void, and says more
            probe = BRepClass3d_SolidClassifier(part.wrapped)
            probe.Perform(gp_Pnt(*centre), 1e-6)
            if probe.State() == TopAbs_IN:
                continue  # material inside the ring: a prism, not a void
            out.append(
                Passage(
                    axis="xyz"[axis],
                    sides=len(ring),
                    length=round(high - low, 3),
                    at=(round(centre[0], 3), round(centre[1], 3), round(centre[2], 3)),
                )
            )
    return sorted(out, key=lambda p: (p.axis, p.at))


def _slot_centres(part, slots) -> list[tuple[float, float]]:
    """Where `recognise_slots` has already reported a void, in the two in-plane axes.

    A through slot *is* a closed uncapped ring, so this family sees it too. Reporting both is a
    double count, and two pinned goldens caught it: `straight_and_obround_slots` produced four
    slots and four passages at the same places, `traversal_order` three of each.

    An earlier attempt declined every four-walled ring instead, on the reasoning that a
    rectangular through void is simply what this package calls a slot. Measured, that is false:
    of fifteen such rings across 120 MFCAD++ models, seven are in models where
    `recognise_slots` reports nothing at all. It was not a reconciliation, it was a silent
    coverage drop. Asking the slot recogniser what it actually claimed is the reconciliation.

    *slots* is injected the way `cyls=` is elsewhere, so the census pays for one slot scan
    rather than two.
    """

    if slots is None:
        if part is None:
            return []
        from b123d_recognisers.slots import recognise_slots

        slots = recognise_slots(part)
    centres = []
    for slot in slots:
        long_mid = 0.5 * (slot.lo + slot.hi)
        if slot.long_axis == "x":
            centres.append((long_mid, slot.w_center))
        else:
            centres.append((slot.w_center, long_mid))
    return centres


def _capped(ring, members, axis, low, high, adjacent, normal, box, faces) -> bool:
    """Does a face perpendicular to the run axis close either end of *ring*?

    Not merely "is there a perpendicular neighbour at the end" -- at a passage mouth the part's
    own outer face is perpendicular and edge-adjacent, and testing only for its presence
    rejects every passage there is. A floor *fills* the ring's cross-section; an end face
    extends past it, because the ring is a hole punched through that face.
    """

    others = [a for a in (0, 1, 2) if a != axis]
    ring_low = [min(box[i][a][0] for i in ring) for a in others]
    ring_high = [max(box[i][a][1] for i in ring) for a in others]
    for i in ring:
        for j in adjacent[i]:
            if j in members:
                continue
            # Any neighbour, not only a planar axis-aligned one. Requiring that let an
            # ordinary filleted or chamfered pocket floor read as a passage: breaking the
            # bottom edge replaces the flat floor's contact with a blend face, and the only
            # cap candidate disappeared. A blend at the bottom of a blind void still closes
            # it, so what matters is whether something sits across the end of the span
            # inside the ring, not what surface type it happens to be.
            end = box.get(j)
            if end is None:
                end = _extent(faces[j])
            if end[axis][1] < low - _SPAN_EPS or end[axis][0] > high + _SPAN_EPS:
                continue
            near_low = abs(end[axis][0] - low) <= _SPAN_EPS or abs(end[axis][1] - low) <= _SPAN_EPS
            near_high = (
                abs(end[axis][0] - high) <= _SPAN_EPS or abs(end[axis][1] - high) <= _SPAN_EPS
            )
            if not (near_low or near_high):
                continue
            if all(
                end[a][0] >= ring_low[k] - _SPAN_EPS and end[a][1] <= ring_high[k] + _SPAN_EPS
                for k, a in enumerate(others)
            ):
                return True
    return False


def _extent(face) -> tuple:
    bb = face.bounding_box()
    return ((bb.min.X, bb.max.X), (bb.min.Y, bb.max.Y), (bb.min.Z, bb.max.Z))
