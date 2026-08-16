# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Shared single-pass cylindrical-face substrate."""

import math

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder
from OCP.TopAbs import TopAbs_Orientation

from b123d_recognisers._geometry import _axis_letter_of, length_tol
from b123d_recognisers._typing import CylinderEvidence, CylinderInventory, Part

_FULL_CYL_MIN_EXTENT = math.pi * 1.05

# Coaxial segments whose axial ranges meet within this gap belong to the same stack (a
# counterbore shoulder is an exact-touch); larger gaps are distinct features unless bridged by a
# shoulder chamfer/fillet or a crossing void (see _merge_stacks). Expressed as a fraction of the
# band's own diameter per ADR 0008: the gap a sliver face or a tangent seam leaves scales with
# the cylinder, so a fixed millimetre gap splits a small bore's stack and welds a large one's.
_STACK_GAP_FRAC = 0.0125


def analyse_cylinders(part: Part) -> CylinderInventory:
    """Return (z_cyls, cross_cyls) from OCP cylindrical face analysis.

    Each entry is a dict with keys: diameter, axis (dominant axis letter),
    u_extent (the face's angular span in radians — partial spans are fillets),
    axis_xyz (a point on the cylinder axis), external (True when the face
    is outward-facing — a boss/OD; False for a bore), dir_xyz (unit axis
    direction with its dominant component positive), s_lo/s_hi (the patch's
    axial extent as coordinates along dir_xyz), solid_idx (index of the owning
    solid, keeping coaxial bores in different bodies distinct), and
    face (the source face).
    z_cyls: cylinders whose axis is approximately Z.
    cross_cyls: cylinders whose axis is approximately X or Y.
    """
    z_cyls: list[CylinderEvidence] = []
    cross_cyls: list[CylinderEvidence] = []
    # Attribute each face to its owning solid so coaxial bores in *different*
    # bodies of a multi-solid assembly are not grouped into one hole — which
    # would measure a depth across the gap between the bodies. A single
    # solid yields one group, i.e. the historical single-body behaviour.
    solids = part.solids()
    faces_by_solid = (
        [(i, f) for i, s in enumerate(solids) for f in s.faces()]
        if solids
        else [(0, f) for f in part.faces()]
    )
    for solid_idx, face in faces_by_solid:
        surf = BRepAdaptor_Surface(face.wrapped)
        if surf.GetType() != GeomAbs_Cylinder:
            continue
        cyl = surf.Cylinder()
        r = cyl.Radius()
        d = cyl.Axis().Direction()
        ap = cyl.Axis().Location()
        ax = _axis_letter_of((d.X(), d.Y(), d.Z()))
        # Canonical direction (dominant component positive) so coaxial faces
        # report comparable axial coordinates whichever way their frame points
        sign = 1.0 if {"x": d.X(), "y": d.Y(), "z": d.Z()}[ax] > 0 else -1.0
        dir_xyz = (sign * d.X(), sign * d.Y(), sign * d.Z())
        v0, v1 = surf.FirstVParameter(), surf.LastVParameter()
        # s(P) = P·dir for P = ap + v*d  →  s = ap·dir + sign*v
        s_ap = ap.X() * dir_xyz[0] + ap.Y() * dir_xyz[1] + ap.Z() * dir_xyz[2]
        s0, s1 = s_ap + sign * v0, s_ap + sign * v1
        rec: CylinderEvidence = dict(
            diameter=round(r * 2, 2),
            axis=ax,
            solid_idx=solid_idx,
            u_extent=surf.LastUParameter() - surf.FirstUParameter(),
            axis_xyz=(ap.X(), ap.Y(), ap.Z()),
            dir_xyz=dir_xyz,
            s_lo=min(s0, s1),
            s_hi=max(s0, s1),
            face=face,
            # Outward material (boss/OD) vs bore: a right-handed cylinder's
            # natural normal points away from the axis, so FORWARD means
            # external — but mirroring makes the frame left-handed and flips
            # both, so compare against the frame handedness
            external=(face.wrapped.Orientation() == TopAbs_Orientation.TopAbs_FORWARD)
            == cyl.Position().Direct(),
        )
        (z_cyls if ax == "z" else cross_cyls).append(rec)
    return z_cyls, cross_cyls


def _line_key(c):
    """Coaxial-stack key: the owning solid plus the axis letter and the axis
    point projected onto the plane perpendicular to the axis direction (so it is
    position-independent along the axis, and exact for slanted axes too). The
    solid component keeps coaxial bores in different bodies of an assembly from
    grouping into one hole."""
    px, py, pz = c["axis_xyz"]
    dx, dy, dz = c["dir_xyz"]
    t = px * dx + py * dy + pz * dz
    return (
        c.get("solid_idx", 0),
        c["axis"],
        round(px - t * dx, 3),
        round(py - t * dy, 3),
        round(pz - t * dz, 3),
    )


def _cyl_group_key(c):
    """Cylinder patches of one hole/boss share an axis line and a diameter."""
    return (*_line_key(c), round(c["diameter"], 2))


def _merge_runs(items, key_fn):
    """Group *items* by *key_fn*, then split each group into runs of
    contiguous axial ranges (a gap wider than the band's own ``_STACK_GAP_FRAC`` starts a new
    run)."""
    by_key: dict = {}
    for item in items:
        by_key.setdefault(key_fn(item), []).append(item)
    runs = []
    for group in by_key.values():
        group.sort(key=lambda c: c["s_lo"])
        run, hi = [group[0]], group[0]["s_hi"]
        for c in group[1:]:
            if c["s_lo"] <= hi + length_tol(c["diameter"], rel=_STACK_GAP_FRAC):
                run.append(c)
                hi = max(hi, c["s_hi"])
            else:
                runs.append(run)
                run, hi = [c], c["s_hi"]
        runs.append(run)
    return runs


def full_cylinders(cyls: list[CylinderEvidence]) -> list[CylinderEvidence]:
    """The feature-relevant ("full") cylinder records within *cyls*.

    *cyls* is one of the two record lists returned by :func:`analyse_cylinders`
    (the z-axis list or the cross-axis list); the records are the dicts that
    function produces. The result keeps only the records that belong to a hole
    or boss: patches around one axis must total more than half a turn within
    one contiguous axial range, so fillet faces and slot end caps are excluded
    (even coaxial caps at different heights) but a bore split by a slot or
    keyway still counts.

    This is the patch-level filter shared with ``make_drawing``. For the
    higher-level inventory of dimensionable diameters use
    :func:`feature_diameters`, which is built from the recognised
    :func:`recognise_holes` / :func:`recognise_bosses` features instead. Public and
    stable for downstream consumers.
    """
    keep = []
    for run in _merge_runs(cyls, _cyl_group_key):
        if sum(c["u_extent"] for c in run) >= _FULL_CYL_MIN_EXTENT:
            keep.extend(run)
    return keep




# ---------------------------------------------------------------------------
# Hole / boss recognition
# ---------------------------------------------------------------------------
