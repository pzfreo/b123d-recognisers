# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Topology-free canonical native analytic surface values.

This leaf is the one authority shared by F1 effective-surface recovery and F2 smooth-side
continuation.  It owns no graph, node, orientation, recovery, evidence, or cache.
"""

from __future__ import annotations

import math
from enum import Enum
from typing import Any

from OCP.BRepAdaptor import BRepAdaptor_Surface

from quiddity._geometry import COORD_FLOOR

_EQUIVALENCE_REL = 1e-9
_AXIS_GAP = 1e-9
_ANGLE_GAP = 1e-9


class SurfaceKind(Enum):
    PLANE = "plane"
    CYLINDER = "cylinder"
    CONE = "cone"
    SPHERE = "sphere"


def _canonical_direction_and_sign(
    direction: Any,
) -> tuple[tuple[float, float, float], float]:
    values = (float(direction.X()), float(direction.Y()), float(direction.Z()))
    dominant = max(range(3), key=lambda axis: (abs(values[axis]), axis))
    sign = 1.0 if values[dominant] >= 0.0 else -1.0
    return (sign * values[0], sign * values[1], sign * values[2]), sign


def _closest_axis_point(
    location: Any, direction: tuple[float, float, float]
) -> tuple[float, float, float]:
    point = (float(location.X()), float(location.Y()), float(location.Z()))
    along = sum(value * axis for value, axis in zip(point, direction, strict=True))
    return (
        point[0] - along * direction[0],
        point[1] - along * direction[1],
        point[2] - along * direction[2],
    )


def native_primitive(adaptor: BRepAdaptor_Surface, kind: SurfaceKind) -> Any:
    if kind is SurfaceKind.PLANE:
        return adaptor.Plane()
    if kind is SurfaceKind.CYLINDER:
        return adaptor.Cylinder()
    if kind is SurfaceKind.CONE:
        return adaptor.Cone()
    return adaptor.Sphere()


def _primitive_parameters(kind: SurfaceKind, primitive: Any) -> tuple[float, ...]:
    if kind is SurfaceKind.PLANE:
        direction, _ = _canonical_direction_and_sign(primitive.Axis().Direction())
        location = primitive.Location()
        offset = sum(
            value * axis
            for value, axis in zip(
                (float(location.X()), float(location.Y()), float(location.Z())),
                direction,
                strict=True,
            )
        )
        return (*direction, offset)
    if kind in (SurfaceKind.CYLINDER, SurfaceKind.CONE):
        direction, sign = _canonical_direction_and_sign(primitive.Axis().Direction())
        if kind is SurfaceKind.CYLINDER:
            point = _closest_axis_point(primitive.Axis().Location(), direction)
            return (*point, *direction, float(primitive.Radius()))
        apex = primitive.Apex()
        return (
            float(apex.X()),
            float(apex.Y()),
            float(apex.Z()),
            *direction,
            sign * float(primitive.SemiAngle()),
        )
    centre = primitive.Location()
    return (float(centre.X()), float(centre.Y()), float(centre.Z()), float(primitive.Radius()))


def validated_parameters(kind: SurfaceKind, primitive: Any) -> tuple[float, ...]:
    parameters = _primitive_parameters(kind, primitive)
    if not parameters or not all(math.isfinite(value) for value in parameters):
        raise ValueError("analytic primitive parameters must be finite")
    direction = parameters[3:6] if kind in (SurfaceKind.CYLINDER, SurfaceKind.CONE) else None
    if kind is SurfaceKind.PLANE:
        direction = parameters[:3]
    if direction is not None and not math.isclose(
        math.sqrt(sum(value * value for value in direction)), 1.0, rel_tol=0.0, abs_tol=1e-9
    ):
        raise ValueError("analytic primitive axis must be unit length")
    if kind in (SurfaceKind.CYLINDER, SurfaceKind.SPHERE) and parameters[-1] <= 0.0:
        raise ValueError("analytic primitive radius must be positive")
    if kind is SurfaceKind.CONE and not 0.0 < abs(parameters[-1]) < math.pi / 2.0:
        raise ValueError("analytic cone angle must be strictly between zero and pi/2")
    return tuple(0.0 if value == 0.0 else value for value in parameters)


def _distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right, strict=True)))


def _axis_equal(left: tuple[float, ...], right: tuple[float, ...]) -> bool:
    return 1.0 - abs(sum(a * b for a, b in zip(left, right, strict=True))) <= _AXIS_GAP


def equivalent_parameters(
    kind: SurfaceKind,
    left: tuple[float, ...],
    right: tuple[float, ...],
    *,
    local: float,
) -> bool:
    """Whether two validated native facts prove one placed analytic continuation."""

    if not math.isfinite(local) or local <= 0.0:
        raise ValueError("analytic equivalence requires a finite positive local length")
    tolerance = _EQUIVALENCE_REL * local + COORD_FLOOR
    if kind is SurfaceKind.PLANE:
        return _axis_equal(left[:3], right[:3]) and abs(left[3] - right[3]) <= tolerance
    if kind is SurfaceKind.CYLINDER:
        return (
            _distance(left[:3], right[:3]) <= tolerance
            and _axis_equal(left[3:6], right[3:6])
            and abs(left[6] - right[6]) <= tolerance
        )
    if kind is SurfaceKind.CONE:
        return (
            _distance(left[:3], right[:3]) <= tolerance
            and _axis_equal(left[3:6], right[3:6])
            and abs(left[6] - right[6]) <= _ANGLE_GAP
        )
    return _distance(left[:3], right[:3]) <= tolerance and abs(left[3] - right[3]) <= tolerance
