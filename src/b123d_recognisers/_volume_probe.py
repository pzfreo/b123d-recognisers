# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Policy-neutral volumetric evidence for axis-aligned candidate regions."""

from __future__ import annotations

from build123d import Box, Pos

from b123d_recognisers._typing import Part

#: OCCT cannot construct a volumetric probe at or below this coordinate extent.
PRISM_PROBE_FLOOR = 1e-6


def prism_material_fraction(
    spans: dict[str, tuple[float, float]], part: Part, *, inset: float
) -> float:
    """Return the fraction of an inset axis-aligned prism occupied by ``part``.

    This measures geometry only. Consumers separately own whether they require exact emptiness
    or permit a named material fraction, and they supply their own inset policy.
    """

    size: dict[str, float] = {}
    centre: dict[str, float] = {}
    for axis, (low, high) in spans.items():
        axis_inset = min(inset, (high - low) / 4)
        size[axis] = (high - low) - 2 * axis_inset
        centre[axis] = (low + high) / 2
    if min(size.values()) <= 0:
        raise ValueError("prism spans must have positive extent")
    if min(size.values()) <= PRISM_PROBE_FLOOR:
        # Nominally disjoint face bounds can overlap by a final bit while remaining below the
        # kernel's constructible-solid floor. Such a sliver cannot prove an empty region.
        return 1.0
    probe = Pos(centre["x"], centre["y"], centre["z"]) * Box(
        size["x"], size["y"], size["z"]
    )
    intersection = part.intersect(probe)
    if intersection is None:
        occupied = 0.0
    elif hasattr(intersection, "volume"):
        occupied = intersection.volume
    else:
        occupied = sum(shape.volume for shape in intersection)
    return float(occupied / (size["x"] * size["y"] * size["z"]))


def prism_is_empty(
    spans: dict[str, tuple[float, float]], part: Part, *, inset: float
) -> bool:
    """Whether the inset prism has exactly zero volumetric intersection with ``part``."""

    return prism_material_fraction(spans, part, inset=inset) == 0.0
