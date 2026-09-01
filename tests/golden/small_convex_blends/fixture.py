# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Synthetic small convex blend-chain golden fixture."""

from build123d import Axis, Box, fillet

from tests.golden._common import originated_here

PROVENANCE = originated_here("tests/test_blends.py")


def build_fixture():
    stock = Box(40, 30, 20)
    return fillet(list(stock.edges().filter_by(Axis.Z)), 0.2)
