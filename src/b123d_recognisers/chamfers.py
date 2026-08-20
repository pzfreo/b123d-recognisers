# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Chamfer (bevelled-edge) recognition for prismatic parts.

``recognise_chamfers`` recovers the manufacturing size of each chamfer so it can be called
out (``C12`` / ``12 × 45°``) rather than left as a rendered-but-undimensioned bevel. A
chamfer is a small **oblique** planar face whose normal is not aligned
with any principal axis (a 45° equal-leg chamfer on a Z edge has normal ≈ (0.707, 0.707,
0)) — that breaks a **convex** edge where two mutually-perpendicular axis-aligned faces
meet. Four gates keep it to genuine chamfers and recover the right size:

- **oblique** — the face's steepest normal component is below ``AXIS_ALIGNED_COS``, excluding real
  axis-aligned faces and shallow draft angles; a turned part's conical chamfer is not
  planar (none found);
- **bridges two axis-aligned faces** — the face is edge-adjacent to axis-aligned faces on
  two distinct in-plane axes, excluding a hex/polygon prism's real oblique sides (whose
  neighbours are themselves oblique);
- **convex** — the virtual sharp corner the bevel replaces (where the two neighbour planes
  cross, at the chamfer's own edge position) lies *outside* the solid. A gusset / rib /
  web fills a **concave** re-entrant corner, so that corner point is buried *inside* the
  material — the discriminator that face-normal + adjacency alone cannot make (a gusset's
  hypotenuse is also edge-adjacent to two perpendicular walls); and
- **not a spanning wedge** — a chamfer's cut is small relative to the part's *overall*
  size, so its larger leg stays under ``max_leg_frac`` of the part's largest dimension; a
  structural ramp/wedge/oversized bevel spans a large fraction and is excluded. Gating
  against the whole-part size (not each leg's own axis extent) keeps a legitimate plate
  edge-break — small in absolute terms — whose cut into a thin thickness axis would trip a
  per-axis fraction of that small extent, while still rejecting a long shallow ramp.

The two legs are the chamfer face's in-plane bbox extents, so an equal-leg and an
asymmetric chamfer are distinguished from the geometry, not estimated from the rendered
view. Depends on :mod:`._bevel` for the single-face read and the convex-corner probe, which
``recognise_angled_steps`` and ``recognise_fillets`` share -- they lived here until three
recognisers wanted them, which is one more than a recogniser should be a substrate for.

**A fifth gate used to live here, and it was not a chamfer test.** A bevel edge-adjacent to a
triangular flat is the slant of an angled blind step, and this recogniser declined it — by
consulting the *other* family's signature through a helper the two shared, so that neither
would report the face and both would agree about which. That is the hand-rolled ownership
device the run-local face graph and its claim ledger were built to remove. Nothing on the face
itself says a chamfer is not a step: the question is which of two families owns it, and ADR 0003
puts that question after discovery, not inside it. So this recogniser proposes every bevel that
clears its own four gates, and
:func:`b123d_recognisers._reconcile.chamfers_that_are_not_angled_steps` drops the ones
``recognise_angled_steps`` claimed.

**What that means for a caller.** Run through :func:`b123d_recognisers.build_recognition_result`
or :func:`b123d_recognisers.feature_census` and the answer is what it always was — the
reconciliation is inside both. Call this function *directly* and a blind step's slant now comes
back as a chamfer, as it did before ``recognise_angled_steps`` existed. That is the same
posture ``recognise_passages`` takes towards a slot's void and ``recognise_turned_steps``
towards a groove's rung: a recogniser reports what its own evidence supports, and a rule that
can see both families decides.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from b123d_recognisers._adjacency import (
    FaceEdges,
    edge_face_map,
    nearest_axis_aligned_planes,
)
from b123d_recognisers._bevel import BevelReject, classify_bevel, convex_bevel
from b123d_recognisers._claims import ClaimLedger
from b123d_recognisers._record import Record
from b123d_recognisers._typing import FaceLike, Part

#: **A minimum-evidence threshold, not a tolerance — deliberately absolute (ADR 0008).**
#: Scaling it to the part makes a feature's existence depend on what surrounds it, so a small
#: feature on a large part disappears. Whether such a feature is worth dimensioning is consumer
#: policy, and ADR 0001 puts policy with the consumer; recognition reports it either way.
_MIN_LEG = 0.5

#: A chamfer runs *along* one principal axis, so its normal has essentially no component on
#: that axis. Looser than the package's AXIS_ZERO_COS because a chamfer face carries more
#: angular noise than a plane that is nominally perpendicular to an axis.
_RUN_AXIS_COS = 0.05


@dataclass(frozen=True)
class Chamfer(Record):
    """A recognised chamfer. ``axis`` is the chamfered edge's direction ("x"/"y"/"z");
    ``leg1``/``leg2`` are the cut depths into the two adjacent faces (equal for a 45°
    chamfer, ``leg1`` the larger); ``angle`` is the chamfer angle in degrees (45 for
    equal-leg); ``at`` is the chamfer face centre in part space (the callout leader's
    tip)."""

    axis: str
    leg1: float
    leg2: float
    angle: float
    at: tuple[float, float, float]


def recognise_chamfers(
    part: Part,
    *,
    tol: float | None = None,
    max_leg_frac: float = 0.45,
    face_edges: FaceEdges | None = None,
    ledger: ClaimLedger | None = None,
) -> list[Chamfer]:
    """Recognise the chamfers of *part* (see module docstring). Returns one
    :class:`Chamfer` per qualifying oblique face, sorted deterministically. Empty when the
    part has no chamfer. Only single-axis chamfers (running along one principal axis) are
    recovered; a compound corner bevel (oblique on all three axes) is skipped.

    *ledger* records the face a chamfer was **established by**: the bevel, and only that. The
    two axis-aligned planes it bridges are *consulted* — they locate the virtual sharp corner
    the convexity probe tests — and each belongs to whatever feature owns it, which is exactly
    the fillet case :mod:`b123d_recognisers._claims` draws the line on.

    A blind step's slant clears every gate here, because on the face alone it is a bevel; pass
    the ledger ``recognise_angled_steps`` wrote into and
    :func:`b123d_recognisers._reconcile.chamfers_that_are_not_angled_steps` removes it."""
    bb = part.bounding_box()
    tol = _MIN_LEG if tol is None else tol
    ext = {0: bb.max.X - bb.min.X, 1: bb.max.Y - bb.min.Y, 2: bb.max.Z - bb.min.Z}
    all_faces = list(part.faces())
    edge_faces = edge_face_map(all_faces, face_edges=face_edges)

    out: list[tuple[Chamfer, FaceLike]] = []
    for f in all_faces:
        # The shared single-face read (classification thresholds + legs = the face's OWN
        # in-plane bbox extents, not measured against a possibly distant outermost wall).
        # (The old extra skew gate on the in-plane normal components was unreachable — a
        # unit normal with two components < 0.05 forces the third > 0.99, which "aligned"
        # already rejects, so the redundant gate was removed when thresholds moved.)
        try:
            edge_i, _nv, span, leg_hi, leg_lo = classify_bevel(f)
        except BevelReject:
            continue
        oi = [j for j in (0, 1, 2) if j != edge_i]
        fc = {i: 0.5 * (span[i][0] + span[i][1]) for i in (0, 1, 2)}  # face centre
        if leg_lo < tol:
            continue
        if leg_hi > max_leg_frac * max(ext.values()):
            continue  # a ramp/wedge spanning a large fraction of the part — not an edge break
        # Must bridge two axis-aligned faces on distinct in-plane axes (a chamfer replaces
        # a sharp 90° edge). A hex side abuts oblique faces. Each neighbour plane's
        # coordinate lets the convex-corner test below reconstruct the virtual corner.
        neigh_coord = nearest_axis_aligned_planes(
            f, edge_faces, fc, exclude_axis=edge_i, face_edges=face_edges
        )
        if oi[0] not in neigh_coord or oi[1] not in neigh_coord:
            continue
        if not convex_bevel(part, fc, edge_i, neigh_coord):
            continue  # concave corner — a gusset / rib / web, not a chamfer
        # Anchor the leader on the bevel FACE (its centroid), not the supporting plane's
        # parametric origin: that origin is arbitrary (OCC parameterisation) and can project to
        # a chamfer endpoint/corner rather than the middle of the diagonal. The centroid
        # of the convex planar bevel lies on the face; this also matches declare's
        # _read_chamfer_face, so detected and declared chamfers anchor identically.
        fctr = f.center()
        angle = math.degrees(math.atan2(leg_lo, leg_hi))
        out.append(
            (
                Chamfer(
                    axis="xyz"[edge_i],
                    leg1=round(leg_hi, 3),
                    leg2=round(leg_lo, 3),
                    angle=round(angle, 2),
                    at=(round(fctr.X, 3), round(fctr.Y, 3), round(fctr.Z, 3)),
                ),
                f,
            )
        )
    out.sort(key=lambda pair: (pair[0].axis, pair[0].at))
    if ledger is not None:
        for chamfer, face in out:
            ledger.add_defining(chamfer, [ledger.graph.require_node(face)])
    return [chamfer for chamfer, _ in out]
