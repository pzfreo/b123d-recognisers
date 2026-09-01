# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Synthetic rectangular blind-slot golden fixture."""

from build123d import Align, Box, Pos

from tests.golden._common import originated_here

PROVENANCE = originated_here("tests/test_rectangular_blind_slots.py")


def build_fixture():
    stock = Box(30, 20, 40, align=(Align.CENTER, Align.CENTER, Align.MIN))
    tool = Pos(0, 5, 0) * Box(
        10,
        5,
        20,
        align=(Align.CENTER, Align.MIN, Align.MIN),
    )
    return stock - tool
