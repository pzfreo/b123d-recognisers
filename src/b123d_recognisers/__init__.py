# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""Geometry-only feature recognition for build123d solids.

Recognisers are migrated incrementally from Draftwright. The aggregate public API will land only
with its contract tests; this scaffold intentionally exposes no placeholder recognition result.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("b123d-recognisers")
except PackageNotFoundError:  # source checkout without an installed distribution
    __version__ = "0.1.0.dev0"

__all__ = ["__version__"]
