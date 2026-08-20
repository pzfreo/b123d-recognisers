# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""The executable recognition budget has one policy source of truth."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))

from benchmark_recognition import _load_budget, _peak_rss_kb  # noqa: E402

BUDGET_FILE = Path(__file__).parents[1] / "docs" / "benchmarks" / "recognition-budget.json"


def test_the_recorded_budget_is_used_unless_the_cli_explicitly_overrides_it(tmp_path):
    budget = tmp_path / "budget.json"
    budget.write_text(
        json.dumps(
            {
                "budget": 1.05,
                "workloads": {"census": {"min_seconds": 10.0}},
            }
        ),
        encoding="utf-8",
    )

    recorded, multiplier = _load_budget(budget, "census", None)
    assert recorded == {"min_seconds": 10.0}
    assert multiplier == 1.05

    _recorded, overridden = _load_budget(budget, "census", 1.20)
    assert overridden == 1.20


def test_the_checked_in_budget_can_actually_be_checked():
    """The tmp-file test above proves the loader; this proves the file it is pointed at.

    A workload recorded without a minimum cannot be measured against, and would fail obscurely
    at the point someone is trying to find out whether they made things slower.
    """

    payload = json.loads(BUDGET_FILE.read_text(encoding="utf-8"))

    assert payload["budget"] > 1.0, "a budget at or below 1.0 forbids all measurement noise"
    for workload in ("composite", "census"):
        recorded, multiplier = _load_budget(BUDGET_FILE, workload, None)
        assert recorded["min_seconds"] > 0
        assert multiplier == recorded.get("budget", payload["budget"])
        assert multiplier > 1.0


def test_peak_memory_is_a_number_or_absent_but_never_a_wrong_unit():
    """`ru_maxrss` is kibibytes on Linux and bytes on macOS; Windows has no ``resource``.

    The field is called ``peak_rss_kb``, so macOS has to be converted and Windows has to say
    nothing rather than say something untrue. The bound is loose on purpose: this asserts a
    unit, not a memory budget.
    """

    peak = _peak_rss_kb()

    if peak is None:
        assert sys.platform.startswith("win")
    else:
        assert 1_000 < peak < 100_000_000, "a bytes-on-macOS reading lands far outside this"


def test_a_workload_may_carry_its_own_budget(tmp_path):
    """A short arm tolerates more noise than a long one, so the multiplier can be per workload.

    The fallback matters as much as the override: a workload that records no budget of its own
    must follow the file's, not silently get a different one.
    """

    budget = tmp_path / "budget.json"
    budget.write_text(
        json.dumps(
            {
                "budget": 1.05,
                "workloads": {
                    "composite": {"min_seconds": 2.0, "budget": 1.30},
                    "census": {"min_seconds": 100.0},
                },
            }
        ),
        encoding="utf-8",
    )

    assert _load_budget(budget, "composite", None)[1] == 1.30
    assert _load_budget(budget, "census", None)[1] == 1.05
    assert _load_budget(budget, "composite", 1.02)[1] == 1.02
