# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""The fast/slow scheduling policy must name real evidence modules."""

from pathlib import Path

from tests.conftest import SLOW_MODULES


def test_every_slow_tier_module_exists_and_is_a_test_module() -> None:
    tests = Path(__file__).parent

    assert SLOW_MODULES
    assert all(name.startswith("test_") and name.endswith(".py") for name in SLOW_MODULES)
    assert {name for name in SLOW_MODULES if not (tests / name).is_file()} == set()
