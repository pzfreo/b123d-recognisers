#!/usr/bin/env python3
"""Paired whole-compound/body-local Plate aggregate benchmark."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
from collections import Counter
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
    import b123d_recognisers.plates as plates
    from b123d_recognisers.result import _take_inventory

    original = plates._plate_scopes
    if not enabled:
        plates._plate_scopes = lambda value: [value]
    try:
        started = time.perf_counter()
        product = _take_inventory(part)
        return product.result, time.perf_counter() - started
    finally:
        plates._plate_scopes = original


def _introduced(legacy: tuple[Any, ...], body_local: tuple[Any, ...]) -> list[dict[str, Any]]:
    remaining = Counter(legacy)
    introduced = []
    for record in body_local:
        if remaining[record]:
            remaining[record] -= 1
        else:
            introduced.append(record.to_dict())
    return introduced


def _measure(parts: list[tuple[str, Any]]) -> dict[str, Any]:
    rows = []
    for index, (model_id, part) in enumerate(parts):
        order = (False, True) if index % 2 == 0 else (True, False)
        measured = {enabled: _run_case(part, enabled) for enabled in order}
        legacy, legacy_seconds = measured[False]
        body_local, body_local_seconds = measured[True]
        old_plates = legacy.plates
        new_plates = body_local.plates
        old_counts = Counter(old_plates)
        new_counts = Counter(new_plates)
        rows.append(
            {
                "id": model_id,
                "other_outputs_equal": replace(body_local, plates=old_plates) == legacy,
                "legacy_plates": len(old_plates),
                "body_local_plates": len(new_plates),
                "legacy_records_retained": all(
                    new_counts[record] >= count for record, count in old_counts.items()
                ),
                "introduced": _introduced(old_plates, new_plates),
                "legacy_seconds": legacy_seconds,
                "body_local_seconds": body_local_seconds,
                "body_local_first": order[0],
            }
        )
    legacy_times = [row["legacy_seconds"] for row in rows]
    body_local_times = [row["body_local_seconds"] for row in rows]
    return {
        "all_other_outputs_equal": all(row["other_outputs_equal"] for row in rows),
        "all_legacy_records_retained": all(row["legacy_records_retained"] for row in rows),
        "legacy_plates": sum(row["legacy_plates"] for row in rows),
        "body_local_plates": sum(row["body_local_plates"] for row in rows),
        "introduced_plates": sum(len(row["introduced"]) for row in rows),
        "legacy": _summary(legacy_times),
        "body_local": _summary(body_local_times),
        "body_local_to_legacy_total_ratio": sum(body_local_times) / sum(legacy_times),
        "paired_median_delta_seconds": statistics.median(
            right - left for left, right in zip(legacy_times, body_local_times, strict=True)
        ),
        "models": rows,
    }


def _acceptable(report: dict[str, Any]) -> bool:
    return bool(
        report["all_other_outputs_equal"]
        and report["all_legacy_records_retained"]
        and report["body_local_to_legacy_total_ratio"] <= 1.10
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workload", choices=("mfcadpp", "census"))
    parser.add_argument("--root", type=Path)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    from build123d import import_step

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
        "format": "b123d-recognisers-plate-body-locality-paired-benchmark",
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
    return 0 if _acceptable(report) else 1


if __name__ == "__main__":
    raise SystemExit(main())
