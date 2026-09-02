#!/usr/bin/env python3
"""Paired Z-only/principal-axis Polygonal Boss aggregate benchmark."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))


def _commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _summary(values: list[float]) -> dict[str, float]:
    return {
        "total_seconds": sum(values),
        "median_seconds": statistics.median(values),
        "maximum_seconds": max(values),
    }


def _run_case(part: Any, enabled: bool) -> tuple[Any, float]:
    import b123d_recognisers.polygonal_bosses as polygonal
    from b123d_recognisers.result import _take_inventory

    original = polygonal._recognise_one

    def z_only(*args: Any, **kwargs: Any) -> Any:
        boss_on_other_axis = not kwargs.get("whole_stock", False) and kwargs.get("axis", "z") != "z"
        return [] if boss_on_other_axis else original(*args, **kwargs)

    if not enabled:
        polygonal._recognise_one = z_only
    try:
        started = time.perf_counter()
        product = _take_inventory(part)
        return product.result, time.perf_counter() - started
    finally:
        polygonal._recognise_one = original


def _measure(parts: list[tuple[str, Any]]) -> dict[str, Any]:
    rows = []
    for index, (model_id, part) in enumerate(parts):
        order = (False, True) if index % 2 == 0 else (True, False)
        measured = {enabled: _run_case(part, enabled) for enabled in order}
        disabled, disabled_seconds = measured[False]
        enabled, enabled_seconds = measured[True]
        legacy = disabled.polygonal_bosses
        principal = enabled.polygonal_bosses
        rows.append(
            {
                "id": model_id,
                "other_outputs_equal": replace(enabled, polygonal_bosses=legacy) == disabled,
                "legacy_z_bosses": len(legacy),
                "principal_axis_bosses": len(principal),
                "legacy_records_retained": all(record in principal for record in legacy),
                "introduced": [record.to_dict() for record in principal if record not in legacy],
                "disabled_seconds": disabled_seconds,
                "enabled_seconds": enabled_seconds,
                "enabled_first": order[0],
            }
        )
    disabled_times = [row["disabled_seconds"] for row in rows]
    enabled_times = [row["enabled_seconds"] for row in rows]
    return {
        "all_other_outputs_equal": all(row["other_outputs_equal"] for row in rows),
        "all_legacy_records_retained": all(row["legacy_records_retained"] for row in rows),
        "legacy_z_bosses": sum(row["legacy_z_bosses"] for row in rows),
        "principal_axis_bosses": sum(row["principal_axis_bosses"] for row in rows),
        "introduced_bosses": sum(len(row["introduced"]) for row in rows),
        "disabled": _summary(disabled_times),
        "enabled": _summary(enabled_times),
        "enabled_to_disabled_total_ratio": sum(enabled_times) / sum(disabled_times),
        "paired_median_delta_seconds": statistics.median(
            right - left for left, right in zip(disabled_times, enabled_times, strict=True)
        ),
        "models": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workload", choices=("mfcadpp", "census"))
    parser.add_argument("--root", type=Path)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    from b123d_recognisers import import_step_geometry as import_step

    if args.workload == "mfcadpp":
        if args.root is None:
            parser.error("mfcadpp requires --root")
        paths = sorted(args.root.glob("*.st*p"))[: args.limit]
    else:
        paths = sorted(
            path
            for corpus in ("nist", "gramel")
            for path in (ROOT / "tests" / "corpus" / corpus).glob("*.st*p")
        )
    if not paths:
        parser.error("the selected workload contains no STEP files")
    report = {
        "format": "b123d-recognisers-polygonal-boss-axis-paired-benchmark",
        "format_version": 1,
        "implementation_commit": _commit(),
        "workload": args.workload,
        "selection": [path.name for path in paths],
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        **_measure([(path.name, import_step(path)) for path in paths]),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "models"}, indent=2))
    return 0 if report["all_other_outputs_equal"] and report["all_legacy_records_retained"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
