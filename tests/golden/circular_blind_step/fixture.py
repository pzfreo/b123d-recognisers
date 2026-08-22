# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Synthetic circular blind-step golden fixture."""

from build123d import Align, Box, Cylinder, Pos

from tests.golden._common import originated_here

PROVENANCE = originated_here("tests/test_circular_blind_steps.py")


def build_fixture():
    stock = Box(40, 30, 20)
    cutter = Pos(20, 15, 0) * Cylinder(
        6, 10, align=(Align.CENTER, Align.CENTER, Align.MIN)
    )
    return stock - cutter
