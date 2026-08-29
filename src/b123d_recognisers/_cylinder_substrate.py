# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Shared single-pass cylindrical-face substrate."""

import math
from typing import TypeVar

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_BezierSurface, GeomAbs_BSplineSurface, GeomAbs_Cylinder

from b123d_recognisers._adjacency import FaceGraph, frame_points_outward
from b123d_recognisers._analytic_surfaces import SurfaceKind
from b123d_recognisers._effective_surfaces import (
    AnalyticSurfaceFact,
    EffectiveFaceSurfaceQuery,
    SurfaceUse,
    effective_faces_for_graph,
)
from b123d_recognisers._geometry import COORD_FLOOR, _axis_letter_of, length_tol, quantise
from b123d_recognisers._typing import CylinderEvidence, CylinderInventory, Part

#: Whatever record type the caller groups. _merge_runs cares only about ``s_lo``/``s_hi`` and the
#: caller's key, so it preserves the element type instead of flattening a widened record -- a
#: hole segment carries more than a raw cylinder patch and must come back out still carrying it.
_E = TypeVar("_E", bound=CylinderEvidence)

_FULL_CYL_MIN_EXTENT = math.pi * 1.05

# Coaxial segments whose axial ranges meet within this gap belong to the same stack (a
# counterbore shoulder is an exact-touch); larger gaps are distinct features unless bridged by a
# shoulder chamfer/fillet or a crossing void (see _merge_stacks). Expressed as a fraction of the
# band's own diameter per ADR 0008: the gap a sliver face or a tangent seam leaves scales with
# the cylinder, so a fixed millimetre gap splits a small bore's stack and welds a large one's.
_STACK_GAP_FRAC = 0.0125


def analyse_cylinders(
    part: Part, *, face_surfaces: EffectiveFaceSurfaceQuery | None = None
) -> CylinderInventory:
    """Return ``(z_cyls, cross_cyls)`` from native or certified effective cylinders.

    Native cylinders retain the historical adaptor path. Non-native faces are admitted only when
    the run-owned effective query recovers a cylinder and independently certifies its radial
    material side. When *face_surfaces* is omitted that query is created lazily, so native-only
    callers pay no extra graph/recovery cost.

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
    effective = face_surfaces
    for solid_idx, face in faces_by_solid:
        surf = BRepAdaptor_Surface(face.wrapped)
        native = surf.GetType() == GeomAbs_Cylinder
        material_use: SurfaceUse | None = None
        if native:
            cyl = surf.Cylinder()
            r = cyl.Radius()
            d_xyz = (
                cyl.Axis().Direction().X(),
                cyl.Axis().Direction().Y(),
                cyl.Axis().Direction().Z(),
            )
            ap_xyz = (
                cyl.Axis().Location().X(),
                cyl.Axis().Location().Y(),
                cyl.Axis().Location().Z(),
            )
        else:
            if surf.GetType() not in (GeomAbs_BSplineSurface, GeomAbs_BezierSurface):
                continue
            if effective is None:
                effective = effective_faces_for_graph(FaceGraph(part))
            fact = effective.fact(face)
            if not isinstance(fact, AnalyticSurfaceFact) or fact.kind is not SurfaceKind.CYLINDER:
                continue
            issued = effective.use(face, material_side=True)
            if (
                not isinstance(issued, SurfaceUse)
                or issued.surface.kind is not SurfaceKind.CYLINDER
            ):
                continue
            material_use = issued
            ap_xyz = (
                0.0
                if abs(issued.surface.parameters[0]) <= COORD_FLOOR
                else quantise(issued.surface.parameters[0]),
                0.0
                if abs(issued.surface.parameters[1]) <= COORD_FLOOR
                else quantise(issued.surface.parameters[1]),
                0.0
                if abs(issued.surface.parameters[2]) <= COORD_FLOOR
                else quantise(issued.surface.parameters[2]),
            )
            d_xyz = (
                quantise(issued.surface.parameters[3]),
                quantise(issued.surface.parameters[4]),
                quantise(issued.surface.parameters[5]),
            )
            r = issued.surface.parameters[6]
        ax = _axis_letter_of(d_xyz)
        # Canonical direction (dominant component positive) so coaxial faces
        # report comparable axial coordinates whichever way their frame points
        sign = 1.0 if {"x": d_xyz[0], "y": d_xyz[1], "z": d_xyz[2]}[ax] > 0 else -1.0
        dir_xyz = tuple(sign * value for value in d_xyz)
        if native:
            s_ap = math.fsum(
                coordinate * direction
                for coordinate, direction in zip(ap_xyz, dir_xyz, strict=True)
            )
            axial = (
                s_ap + sign * surf.FirstVParameter(),
                s_ap + sign * surf.LastVParameter(),
            )
        else:
            axial = tuple(
                vertex.X * dir_xyz[0] + vertex.Y * dir_xyz[1] + vertex.Z * dir_xyz[2]
                for vertex in face.vertices()
            )
        rec: CylinderEvidence = dict(
            diameter=quantise(r * 2),
            axis=ax,
            solid_idx=solid_idx,
            u_extent=surf.LastUParameter() - surf.FirstUParameter(),
            axis_xyz=ap_xyz,
            dir_xyz=dir_xyz,
            s_lo=min(axial),
            s_hi=max(axial),
            face=face,
            # Outward material (boss/OD) vs bore: a right-handed cylinder's natural normal
            # points away from the axis, so a frame pointing outward is an external surface.
            external=(
                bool(frame_points_outward(face))
                if material_use is None
                else material_use.material_side is not None
                and material_use.material_side.candidate_outward_sign > 0
            ),
        )
        (z_cyls if ax == "z" else cross_cyls).append(rec)
    return z_cyls, cross_cyls


def _line_key(c) -> tuple:
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


def _cyl_group_key(c) -> tuple:
    """Cylinder patches of one hole/boss share an axis line and a diameter."""
    return (*_line_key(c), quantise(c["diameter"], figures=4))


def _merge_runs(items: list[_E], key_fn) -> list[list[_E]]:
    """Group *items* by *key_fn*, then split each group into runs of
    contiguous axial ranges (a gap wider than the band's own ``_STACK_GAP_FRAC`` starts a new
    run)."""
    by_key: dict[object, list[_E]] = {}
    for item in items:
        by_key.setdefault(key_fn(item), []).append(item)
    runs: list[list[_E]] = []
    for group in by_key.values():
        group.sort(key=lambda c: c["s_lo"])
        run: list[_E] = [group[0]]
        hi = group[0]["s_hi"]
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
