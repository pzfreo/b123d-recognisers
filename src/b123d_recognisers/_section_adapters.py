# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Legacy publication-grid projection and private exact section-occurrence adapters."""

from __future__ import annotations

import math
from typing import cast

from b123d_recognisers._section_recess import (
    ClosedSectionProfile,
    SectionEnd,
    SectionRecessEnds,
    SectionRecessGeometry,
)
from b123d_recognisers._sections import (
    _OCCURRENCE_TOL,
    BodyRef,
    BodyRefIssuer,
    LocalFrame,
    PlanarSection,
    SectionEnds,
    SectionOccurrence,
    SectionVertex,
    validate_occurrence,
)
from b123d_recognisers.passages import Passage, PassageFrame, PassageSectionVertex
from b123d_recognisers.prismatic_pockets import PrismaticPocket

_AXES = "xyz"


class LegacySectionProjectionError(ValueError):
    def __init__(self, condition: str) -> None:
        self.condition = condition
        super().__init__(f"legacy section projection refused: {condition}")


def _normalise_published_section(
    section: tuple[tuple[float, float], ...],
) -> PlanarSection:
    if any(
        len(point) != 2 or not all(math.isfinite(value) for value in point) for point in section
    ):
        raise LegacySectionProjectionError("non-finite or malformed vertices")
    vertices = [(round(point[0] * 1000), round(point[1] * 1000)) for point in section]
    changed = True
    while changed and len(vertices) >= 3:
        changed = False
        for index, point in enumerate(vertices):
            previous = vertices[index - 1]
            following = vertices[(index + 1) % len(vertices)]
            incoming = (point[0] - previous[0], point[1] - previous[1])
            outgoing = (following[0] - point[0], following[1] - point[1])
            backtrack = (
                incoming[0] * outgoing[1] == incoming[1] * outgoing[0]
                and incoming[0] * outgoing[0] + incoming[1] * outgoing[1] < 0
            )
            if point in (previous, following) or backtrack:
                del vertices[index]
                changed = True
                break
    if len(set(vertices)) < 3:
        raise LegacySectionProjectionError("collapsed loop")
    if len(set(vertices)) != len(vertices):
        raise LegacySectionProjectionError(
            "non-adjacent repeated vertex creates ambiguous topology"
        )
    try:
        normalized = PlanarSection(
            tuple(SectionVertex((point[0] / 1000, point[1] / 1000)) for point in vertices)
        )
    except ValueError as error:
        raise LegacySectionProjectionError(f"invalid published loop: {error}") from error
    for original in section:
        distances = []
        for index, vertex in enumerate(normalized.boundary):
            start = vertex.point
            end = normalized.boundary[(index + 1) % len(normalized.boundary)].point
            direction = (end[0] - start[0], end[1] - start[1])
            fraction = max(
                0.0,
                min(
                    1.0,
                    (
                        (original[0] - start[0]) * direction[0]
                        + (original[1] - start[1]) * direction[1]
                    )
                    / (direction[0] ** 2 + direction[1] ** 2),
                ),
            )
            distances.append(
                math.dist(
                    original,
                    (start[0] + fraction * direction[0], start[1] + fraction * direction[1]),
                )
            )
        if min(distances) > _OCCURRENCE_TOL:
            raise LegacySectionProjectionError("normalisation exceeds displacement bound")
    return normalized


def legacy_section_geometry(record: Passage | PrismaticPocket) -> SectionRecessGeometry:
    """Project published-grid geometry without forcing an exact-centroid intermediate value."""

    axis = record.axis
    span = record.depth if isinstance(record, PrismaticPocket) else record.length
    if axis not in _AXES or not math.isfinite(span) or span <= 0:
        raise LegacySectionProjectionError("invalid axis or span")
    if len(record.at) != 3 or not all(math.isfinite(value) for value in record.at):
        raise LegacySectionProjectionError("invalid centre")
    if record.sides != len(record.section) or record.sides < 3:
        raise LegacySectionProjectionError("side count does not match published vertices")
    if isinstance(record, PrismaticPocket) and record.open_sign not in (-1, 1):
        raise LegacySectionProjectionError("invalid opening direction")
    raw = _normalise_published_section(record.section)
    transverse = tuple(index for index in range(3) if index != _AXES.index(axis))
    centroid = raw.centroid
    if any(
        abs(centroid[index] - record.at[coordinate]) > 0.0008
        for index, coordinate in enumerate(transverse)
    ):
        raise LegacySectionProjectionError("centre disagrees with published loop")
    origin_grid = tuple(round(value * 1000) for value in centroid)
    origin = [0.0, 0.0, 0.0]
    for index, coordinate in enumerate(transverse):
        origin[coordinate] = origin_grid[index] / 1000
    frame = LocalFrame.principal(axis, cast(tuple[float, float, float], tuple(origin)))
    coordinate_order = (1, 0) if axis == "y" else (0, 1)
    try:
        local = PlanarSection(
            tuple(
                SectionVertex(
                    cast(
                        tuple[float, float],
                        tuple(
                            (round(vertex.point[index] * 1000) - origin_grid[index]) / 1000
                            for index in coordinate_order
                        ),
                    )
                )
                for vertex in raw.boundary
            )
        )
        interval = tuple(
            round(record.at[_AXES.index(axis)] + sign * span / 2, 3) for sign in (-1, 1)
        )
        return SectionRecessGeometry(
            "section_recess",
            PassageFrame(frame.origin, frame.run, frame.u, frame.v),
            cast(tuple[float, float], interval),
            ClosedSectionProfile(
                "closed",
                tuple(PassageSectionVertex(vertex.point, 0.0) for vertex in local.boundary),
            ),
            SectionRecessEnds(
                SectionEnd(
                    "capped"
                    if isinstance(record, PrismaticPocket) and record.open_sign == 1
                    else "open"
                ),
                SectionEnd(
                    "capped"
                    if isinstance(record, PrismaticPocket) and record.open_sign == -1
                    else "open"
                ),
            ),
        )
    except ValueError as error:
        raise LegacySectionProjectionError(
            f"invalid projected loop or interval: {error}"
        ) from error


def _validate_record(
    *,
    axis: str,
    span: float,
    at: tuple[float, float, float],
    section: tuple[tuple[float, float], ...],
    sides: int,
) -> tuple[LocalFrame, PlanarSection, tuple[float, float]]:
    if axis not in _AXES:
        raise ValueError("legacy section axis must be x, y, or z")
    if not math.isfinite(span) or span <= 0:
        raise ValueError("legacy section span must be positive")
    if len(at) != 3 or not all(math.isfinite(value) for value in at):
        raise ValueError("legacy section centre must be finite")
    if sides != len(section) or sides < 3:
        raise ValueError("legacy side count must match a polygonal section")
    if any(
        len(point) != 2 or not all(math.isfinite(value) for value in point) for point in section
    ):
        raise ValueError("legacy section points must be finite pairs")

    transverse = [index for index in range(3) if index != _AXES.index(axis)]
    # Legacy vertices are rounded world-plane coordinates.  Centre them before canonicalisation;
    # the record's rounded `at` remains authoritative only within the same positional contract.
    raw = PlanarSection(tuple(SectionVertex((point[0], point[1])) for point in section))
    centroid = raw.centroid
    expected = (at[transverse[0]], at[transverse[1]])
    # Both values are independently serialized at three decimal places.  The neutral section
    # contract already publishes 0.0008 mm as the analytic-centroid displacement allowance for
    # that double rounding; use the same bound rather than requiring identical rounded values.
    if any(abs(left - right) > 0.0008 for left, right in zip(centroid, expected, strict=True)):
        raise ValueError("legacy centre disagrees with the section's analytic centroid")
    local = PlanarSection(
        tuple(
            SectionVertex((vertex.point[0] - centroid[0], vertex.point[1] - centroid[1]))
            for vertex in raw.boundary
        )
    )
    centre_values = [float(value) for value in at]
    centre_values[transverse[0]], centre_values[transverse[1]] = centroid
    centre3 = (centre_values[0], centre_values[1], centre_values[2])
    frame = LocalFrame.principal(axis, centre3)
    axis_index = _AXES.index(axis)
    interval = (at[axis_index] - span / 2.0, at[axis_index] + span / 2.0)
    return frame, local, interval


def _occurrence(
    *,
    axis: str,
    span: float,
    at: tuple[float, float, float],
    section: tuple[tuple[float, float], ...],
    sides: int,
    ends: SectionEnds,
    body_ref: BodyRef,
    body_refs: BodyRefIssuer,
) -> SectionOccurrence:
    body_refs.validate(body_ref)
    frame, planar, interval = _validate_record(
        axis=axis, span=span, at=at, section=section, sides=sides
    )
    return SectionOccurrence(body_ref, frame, interval, planar, ends)


def passage_to_occurrence(
    record: Passage, *, body_ref: BodyRef, body_refs: BodyRefIssuer
) -> SectionOccurrence:
    return _occurrence(
        axis=record.axis,
        span=record.length,
        at=record.at,
        section=record.section,
        sides=record.sides,
        ends=SectionEnds(False, False),
        body_ref=body_ref,
        body_refs=body_refs,
    )


def prismatic_pocket_to_occurrence(
    record: PrismaticPocket, *, body_ref: BodyRef, body_refs: BodyRefIssuer
) -> SectionOccurrence:
    if record.open_sign not in (-1, 1):
        raise ValueError("legacy pocket open_sign must be -1 or +1")
    return _occurrence(
        axis=record.axis,
        span=record.depth,
        at=record.at,
        section=record.section,
        sides=record.sides,
        ends=SectionEnds(record.open_sign == 1, record.open_sign == -1),
        body_ref=body_ref,
        body_refs=body_refs,
    )


def _legacy_values(
    occurrence: SectionOccurrence, *, body_refs: BodyRefIssuer
) -> tuple[str, int, float, tuple[float, float, float], tuple[tuple[float, float], ...]]:
    validate_occurrence(occurrence, body_refs=body_refs)
    if any(vertex.bulge != 0.0 for vertex in occurrence.section.boundary):
        raise ValueError("polygonal legacy records cannot represent arc sections")
    principal = {
        ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)): "x",
        ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)): "y",
        ((0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)): "z",
    }
    try:
        axis = principal[(occurrence.frame.run, occurrence.frame.u, occurrence.frame.v)]
    except KeyError as exc:
        raise ValueError("legacy records require an exact principal-axis frame") from exc
    lo, hi = occurrence.run_interval
    axis_index = _AXES.index(axis)
    centre = [float(value) for value in occurrence.frame.origin]
    centre[axis_index] = 0.5 * (lo + hi)
    transverse = [index for index in range(3) if index != axis_index]
    section = tuple(
        (
            round(occurrence.frame.origin[transverse[0]] + vertex.point[0], 3),
            round(occurrence.frame.origin[transverse[1]] + vertex.point[1], 3),
        )
        for vertex in occurrence.section.boundary
    )
    return (
        axis,
        len(section),
        round(hi - lo, 3),
        tuple(round(value, 3) for value in centre),  # type: ignore[return-value]
        section,
    )


def occurrence_to_passage(occurrence: SectionOccurrence, *, body_refs: BodyRefIssuer) -> Passage:
    if occurrence.ends != SectionEnds(False, False):
        raise ValueError("Passage requires two open ends")
    axis, sides, length, at, section = _legacy_values(occurrence, body_refs=body_refs)
    return Passage(axis=axis, sides=sides, length=length, at=at, section=section)


def occurrence_to_prismatic_pocket(
    occurrence: SectionOccurrence, *, body_refs: BodyRefIssuer
) -> PrismaticPocket:
    if occurrence.ends == SectionEnds(True, False):
        open_sign = 1
    elif occurrence.ends == SectionEnds(False, True):
        open_sign = -1
    else:
        raise ValueError("PrismaticPocket requires exactly one capped end")
    axis, sides, depth, at, section = _legacy_values(occurrence, body_refs=body_refs)
    return PrismaticPocket(
        axis=axis,
        sides=sides,
        depth=depth,
        open_sign=open_sign,
        at=at,
        section=section,
    )
