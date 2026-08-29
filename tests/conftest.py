# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""Suite-level test tiers derived from measured module runtimes.

The fast tier is the edit/test loop and draft-PR signal. The slow tier remains part of the
authoritative coverage run before merge; this list changes scheduling, never whether evidence runs.
Keep whole modules together so their module-scoped imported geometry is not rebuilt across tiers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

SLOW_MODULES = frozenset(
    {
        "test_blend_boundary_sweep.py",
        "test_correspondence_match.py",
        "test_correspondence_snapshot.py",
        "test_experimental_frame.py",
        "test_inventory_agreement.py",
        "test_mfcadpp_corpus.py",
        "test_mfcadpp_holdout.py",
        "test_nist_ctc_corpus.py",
        "test_nurbs_conversion_sweep.py",
        "test_package.py",
        "test_rigid_motion_sweep.py",
    }
)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark measured expensive modules without scattering policy through evidence files."""

    for item in items:
        if Path(str(item.path)).name in SLOW_MODULES:
            item.add_marker(pytest.mark.slow)
