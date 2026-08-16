# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Compatibility facade for the historical cylinder-feature implementation module."""

from b123d_recognisers._cylinder_substrate import (
    _FULL_CYL_MIN_EXTENT as _FULL_CYL_MIN_EXTENT,
)
from b123d_recognisers._cylinder_substrate import (
    analyse_cylinders,
    full_cylinders,
)
from b123d_recognisers._hole_features import (
    BossRecord,
    CounterBore,
    HoleRecord,
    feature_diameters,
    recognise_bosses,
    recognise_holes,
)
from b123d_recognisers._hole_features import (
    _edge_face_map as _edge_face_map,
)
from b123d_recognisers._hole_patterns import (
    BoltCircle,
    HoleSpec,
    LinearArray,
    RectGrid,
    recognise_hole_patterns,
)
from b123d_recognisers._hole_patterns import (
    _bolt_circle_candidates as _bolt_circle_candidates,
)
from b123d_recognisers._pattern_geometry import (
    _linear_array_candidates as _linear_array_candidates,
    _plane_uv as _plane_uv,
    _rect_grid as _rect_grid,
)

__all__ = [
    "BoltCircle",
    "BossRecord",
    "CounterBore",
    "HoleRecord",
    "HoleSpec",
    "LinearArray",
    "RectGrid",
    "analyse_cylinders",
    "feature_diameters",
    "full_cylinders",
    "recognise_bosses",
    "recognise_hole_patterns",
    "recognise_holes",
]
