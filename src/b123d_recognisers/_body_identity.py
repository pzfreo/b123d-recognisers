# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Serializable, geometry-derived source-body correlation.

The value is deliberately useful only for equality.  It is not a persistent topology handle:
separate solids with the same signature are ambiguous and callers must publish ``None`` rather
than assigning either occurrence by traversal order.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence

from b123d_recognisers._typing import Part

BodyKey = tuple[float, ...]


def body_signature(solid: Part) -> BodyKey:
    """Return the coordinate-frame-local geometric signature of one physical solid."""

    bb = solid.bounding_box()
    return (
        float(bb.min.X),
        float(bb.min.Y),
        float(bb.min.Z),
        float(bb.max.X),
        float(bb.max.Y),
        float(bb.max.Z),
        float(solid.volume),
        float(solid.area),
    )


def unambiguous_body_keys(
    sources: Sequence[Part], *, require_valid_solid: bool = False
) -> tuple[BodyKey | None, ...]:
    """Return occurrence-aligned keys, refusing duplicate geometric signatures.

    Existing recess projections also operate on record-only open-shell compatibility inputs.
    New physical-ownership fields opt into ``require_valid_solid`` so those inputs publish no
    misleading body identity without changing the older recess value contract.
    """

    signatures = tuple(
        (
            body_signature(source)
            if not require_valid_solid or (source.solids() and source.is_valid)
            else None
        )
        for source in sources
    )
    counts = Counter(signature for signature in signatures if signature is not None)
    return tuple(
        signature if signature is not None and counts[signature] == 1 else None
        for signature in signatures
    )
