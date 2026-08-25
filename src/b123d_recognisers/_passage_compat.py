# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Issuer-frozen Passage compatibility facts; never public record geometry."""

from __future__ import annotations

from dataclasses import dataclass


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
