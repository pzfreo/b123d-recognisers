# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Issuer-frozen Passage compatibility facts; never public record geometry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, TypeVar

CompatibilitySnapshot = tuple[
    str | None,
    tuple[tuple[float, float], ...] | None,
    int | None,
    float | None,
    tuple[float, float, float] | None,
    int | None,
    bool,
]
PrincipalProjection = tuple[
    str,
    int,
    float,
    tuple[float, float, float],
    tuple[tuple[float, float], ...],
]
PassageT_co = TypeVar("PassageT_co", covariant=True)


class PassageConstructor(Protocol[PassageT_co]):
    def __call__(
        self,
        axis: str,
        sides: int,
        length: float,
        at: tuple[float, float, float],
        section: tuple[tuple[float, float], ...],
    ) -> PassageT_co: ...


@dataclass(frozen=True, slots=True)
class PassageCompatibilityView:
    """Historical eligibility and Slot grouping captured before Candidate issuance."""

    axis: str | None
    section: tuple[tuple[float, float], ...] | None
    sides: int | None
    length: float | None
    at: tuple[float, float, float] | None
    legacy_ordinal: int | None
    eligible: bool

    def __post_init__(self) -> None:
        if self.axis is not None and self.axis not in {"x", "y", "z"}:
            raise ValueError("passage compatibility axis is invalid")
        if (self.axis is None) != (self.section is None):
            raise ValueError("passage grouping axis and section must be present together")
        legacy = (self.length, self.at, self.legacy_ordinal)
        if self.eligible and (
            self.axis is None or self.sides is None or any(value is None for value in legacy)
        ):
            raise ValueError("eligible passage compatibility requires a complete legacy value")
        if not self.eligible and any(value is not None for value in legacy):
            raise ValueError("ineligible passage compatibility cannot carry a legacy value")
        if self.axis is None and self.sides is not None:
            raise ValueError("passage grouping sides require a principal grouping key")

    def issued_snapshot(self) -> CompatibilitySnapshot:
        """Return and revalidate the complete primitive state frozen at issuance."""

        validated = PassageCompatibilityView(
            self.axis,
            self.section,
            self.sides,
            self.length,
            self.at,
            self.legacy_ordinal,
            self.eligible,
        )
        return (
            validated.axis,
            validated.section,
            validated.sides,
            validated.length,
            validated.at,
            validated.legacy_ordinal,
            validated.eligible,
        )


def principal_projection(
    origin: tuple[float, float, float],
    run: tuple[float, float, float],
    u: tuple[float, float, float],
    v: tuple[float, float, float],
    interval: tuple[float, float],
    boundary: tuple[tuple[float, float], ...],
) -> PrincipalProjection | None:
    """Build the sole principal legacy geometry view from occurrence primitives."""

    axes = (
        ((1.0, 0.0, 0.0), "x", 1, 2),
        ((0.0, 1.0, 0.0), "y", 0, 2),
        ((0.0, 0.0, 1.0), "z", 0, 1),
    )
    matched = next(
        (
            (axis, first, second)
            for expected, axis, first, second in axes
            if all(
                abs(value - target) <= 1e-12 for value, target in zip(run, expected, strict=True)
            )
        ),
        None,
    )
    if matched is None:
        return None
    axis, first, second = matched
    lo, hi = interval
    centre = [*origin]
    centre["xyz".index(axis)] = 0.5 * (lo + hi)
    section = tuple(
        (
            round(origin[first] + point[0] * u[first] + point[1] * v[first], 3),
            round(origin[second] + point[0] * u[second] + point[1] * v[second], 3),
        )
        for point in boundary
    )
    canonical = _canonical_section(section)
    if canonical is None:
        return None
    return (
        axis,
        len(canonical),
        round(hi - lo, 3),
        tuple(round(value, 3) for value in centre),  # type: ignore[return-value]
        canonical,
    )


def compatibility_view(
    projection: PrincipalProjection | None,
    *,
    eligible: bool,
    legacy_ordinal: int | None = None,
) -> PassageCompatibilityView:
    """Freeze one eligible legacy value or ineligible grouping fact."""

    if projection is None:
        if eligible:
            raise ValueError("eligible passage has no principal compatibility projection")
        return PassageCompatibilityView(None, None, None, None, None, None, False)
    axis, sides, length, at, section = projection
    return PassageCompatibilityView(
        axis,
        section,
        sides,
        length if eligible else None,
        at if eligible else None,
        legacy_ordinal if eligible else None,
        eligible,
    )


def passage_from_view(
    view: PassageCompatibilityView, passage_type: PassageConstructor[PassageT_co]
) -> PassageT_co:
    """Construct the sole public legacy compatibility value from an eligible fact."""

    snapshot = view.issued_snapshot()
    if not view.eligible:
        raise ValueError("ineligible compatibility fact has no legacy Passage")
    axis, section, sides, length, at, _ordinal, _eligible = snapshot
    assert axis is not None and section is not None and sides is not None
    assert length is not None and at is not None
    return passage_type(axis, sides, length, at, section)


def grouping_from_view(
    view: PassageCompatibilityView,
) -> tuple[str, tuple[tuple[float, float], ...], int] | None:
    """Return the sole Slot-reconciliation grouping interpretation."""

    axis, section, sides, *_ = view.issued_snapshot()
    if axis is None or section is None or sides is None:
        return None
    return axis, section, sides


def _canonical_section(
    section: tuple[tuple[float, float], ...],
) -> tuple[tuple[float, float], ...] | None:
    if len(section) < 3 or len(set(section)) != len(section):
        return None
    area = sum(
        left[0] * right[1] - right[0] * left[1]
        for left, right in zip(section, (*section[1:], section[0]), strict=True)
    )
    if abs(area) <= 1e-12:
        return None
    oriented = section if area > 0 else tuple(reversed(section))
    start = min(range(len(oriented)), key=oriented.__getitem__)
    return (*oriented[start:], *oriented[:start])
