# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Shared types for the public geometry boundary.

These aliases describe build123d inputs and the one legacy dictionary substrate exported for
Draftwright compatibility. Recognition records themselves continue to contain only serialisable
geometry values.
"""

from __future__ import annotations

from typing import Protocol, TypeAlias, TypedDict

from build123d import BoundBox, Compound, Edge, Face, Solid

Vector3: TypeAlias = tuple[float, float, float]
Span2: TypeAlias = tuple[float, float]
Part: TypeAlias = Solid | Compound
Bounds: TypeAlias = BoundBox
FaceLike: TypeAlias = Face
EdgeLike: TypeAlias = Edge


class _PointMethods(Protocol):
    def X(self) -> float: ...

    def Y(self) -> float: ...

    def Z(self) -> float: ...


class SurfaceAdaptor(Protocol):
    """Structural slice of an OCP surface adaptor used by :func:`fillet_anchor`."""

    def FirstUParameter(self) -> float: ...

    def LastUParameter(self) -> float: ...

    def FirstVParameter(self) -> float: ...

    def LastVParameter(self) -> float: ...

    def Value(self, u: float, v: float) -> _PointMethods: ...


class CylinderEvidence(TypedDict):
    """One public cylinder-analysis item returned by :func:`analyse_cylinders`.

    ``face`` is deliberately a build123d value: cylinder analysis is an explicitly low-level
    substrate helper, not a recognition record. ADR 0002's serialisable-output guarantee applies
    to ``recognise_*`` records, not this compatibility surface.
    """

    diameter: float
    axis: str
    u_extent: float
    axis_xyz: Vector3
    external: bool
    dir_xyz: Vector3
    s_lo: float
    s_hi: float
    solid_idx: int
    face: Face


CylinderInventory: TypeAlias = tuple[list[CylinderEvidence], list[CylinderEvidence]]
FrozenCylinderInventory: TypeAlias = tuple[
    tuple[CylinderEvidence, ...], tuple[CylinderEvidence, ...]
]
