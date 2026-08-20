# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""The executable recognition budget has one policy source of truth."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))

from benchmark_recognition import _load_budget  # noqa: E402


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
