# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Private exact adapters between principal-axis records and section occurrences."""

from __future__ import annotations

import math

from b123d_recognisers._sections import (
    BodyRef,
    BodyRefIssuer,
    LocalFrame,
    PlanarSection,
    SectionEnds,
    SectionOccurrence,
    SectionVertex,
    validate_occurrence,
)
from b123d_recognisers.passages import Passage
from b123d_recognisers.prismatic_pockets import PrismaticPocket

_AXES = "xyz"


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
    if any(round(left, 3) != right for left, right in zip(centroid, expected, strict=True)):
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
