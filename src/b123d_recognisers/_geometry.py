# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Internal shared axis and length conventions used by recognition records and patterns.

Two things live here because every recogniser needs them and none owns them: the stable
dominant-axis convention, and the length-tolerance form of ADR 0008.
"""

from __future__ import annotations

import math

_PLANE_AXES = {
    "x": ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    "y": ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0)),
    "z": ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
}

_DOMINANT_TIE_TOL = 1e-12


def _unit(v):
    """Normalise negative zeros out of a direction tuple."""
    return tuple(0.0 if c == 0 else c for c in v)


def _axis_letter_of(axis) -> str:
    """Return a platform-stable dominant axis, preferring Z then Y for numerical ties."""

    components = tuple(abs(float(component)) for component in axis)
    if len(components) != 3:
        raise ValueError("axis must be a 3-vector")
    peak = max(components)
    # OCCT can perturb an exact diagonal by a final bit in opposite directions on Windows and
    # Unix. The routing letter is discrete, so resolve numerical ties explicitly instead of
    # allowing that insignificant noise to select a different feature universe.
    return next(
        letter
        for letter, component in reversed(tuple(zip("xyz", components, strict=True)))
        if peak - component <= _DOMINANT_TIE_TOL
    )


def plane_axes(axis) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Return the stable right-handed in-plane basis for an axis letter or vector."""

    letter = axis if isinstance(axis, str) else _axis_letter_of(axis)
    return _PLANE_AXES[letter]


def _axis_direction_components(axis: str, direction=None):
    if axis not in "xyz" or len(axis) != 1:
        raise ValueError("axis must be 'x', 'y', or 'z'")
    if direction is None:
        direction = tuple(1.0 if letter == axis else 0.0 for letter in "xyz")
    try:
        raw = tuple(float(component) for component in direction)
    except (TypeError, ValueError) as exc:
        raise ValueError("axis_direction must be a 3-vector") from exc
    if len(raw) != 3:
        raise ValueError("axis_direction must be a 3-vector")
    if not all(math.isfinite(component) for component in raw):
        raise ValueError("axis_direction must contain only finite values")
    norm = math.hypot(*raw)
    if norm <= 1e-12:
        raise ValueError("axis_direction must be non-zero")
    index = "xyz".index(axis)
    if abs(raw[index]) + norm * 1e-9 < max(abs(component) for component in raw):
        raise ValueError(f"axis_direction's dominant component must match axis={axis!r}")
    return raw, norm, index


def _normalised_axis_direction(axis: str, direction=None) -> tuple[float, float, float]:
    raw, norm, index = _axis_direction_components(axis, direction)
    sign = -1.0 if raw[index] < 0 else 1.0
    return (sign * raw[0] / norm, sign * raw[1] / norm, sign * raw[2] / norm)


def _canonical_axis_direction(axis: str, direction=None) -> tuple[float, float, float]:
    raw, norm, index = _axis_direction_components(axis, direction)
    sign = -1.0 if raw[index] < 0 else 1.0
    unit = (
        tuple(sign * component for component in raw)
        if abs(norm - 1.0) <= 2e-6
        else _normalised_axis_direction(axis, raw)
    )
    rounded = tuple(
        0.0 if abs(component) < 0.5e-6 else round(component, 6) for component in unit
    )
    return (rounded[0], rounded[1], rounded[2])


def _canonical_axis_span(axis: str, direction, span) -> tuple[float, float]:
    raw, _norm, index = _axis_direction_components(axis, direction)
    lo, hi = (float(value) for value in span)
    if raw[index] < 0:
        lo, hi = -hi, -lo
    return (round(lo, 3), round(hi, 3))


def _axis_line_coordinates(axis: str, point, direction=None) -> tuple[float, float]:
    px, py, pz = (float(component) for component in point)
    vector = _normalised_axis_direction(axis, direction)
    along = px * vector[0] + py * vector[1] + pz * vector[2]
    foot = tuple(
        component - along * delta for component, delta in zip((px, py, pz), vector, strict=True)
    )
    keep = [index for index, letter in enumerate("xyz") if letter != axis]
    coordinates = tuple(round(foot[index], 3) for index in keep)
    return (
        0.0 if coordinates[0] == 0 else coordinates[0],
        0.0 if coordinates[1] == 0 else coordinates[1],
    )


def _axis_direction_is_aligned(axis: str, direction, *, tol: float = 1e-3) -> bool:
    vector = _canonical_axis_direction(axis, direction)
    index = "xyz".index(axis)
    return abs(vector[index] - 1.0) <= tol and all(
        abs(vector[other]) <= tol for other in range(3) if other != index
    )


def part_scale(bbox) -> float:
    """Return a solid's characteristic length: the largest extent of its bounding box.

    The reference length for tolerances that compare two coordinates with no smaller feature
    to measure against — a level bucket, a floor-plane coincidence, a merge radius. Takes the
    bounding box rather than the part because every caller already holds one, and asking for a
    second is both a wasted traversal and a chance for the two to disagree.
    """

    return max(float(bbox.size.X), float(bbox.size.Y), float(bbox.size.Z))


def length_tol(nominal: float, *, rel: float, floor: float) -> float:
    """Return a length tolerance proportional to *nominal* but never below *floor*.

    The package's one tolerance form, per ADR 0008. *rel* carries the part of the allowance
    that grows with the thing being measured — machining and modelling error both scale with
    size — and *floor* carries the part that does not: the absolute noise band below which two
    coordinates are the same coordinate.

    The terms add rather than taking a maximum. A maximum discards one term below
    ``floor / rel``, so every feature smaller than that gets exactly the floor and its own size
    stops mattering — the same scale-blindness, moved to the small end.

    *nominal* is a diameter, radius, width or envelope extent, and is therefore non-negative.
    A negative value would silently *tighten* the gate below its floor, which no caller can
    mean, so it is a programming error and raises.

    A NaN nominal is deliberately not rejected. It means the geometry that produced it is
    malformed, and this package fails closed on malformed evidence rather than raising: the NaN
    propagates, every comparison against it is false, and the candidate is refused.
    """

    if nominal < 0.0:
        raise ValueError("nominal must be a non-negative length")
    return rel * nominal + floor
