#!/usr/bin/env python3
"""Produce a canonical Epic 0005 effectiveness report from a labelled STEP corpus."""

from __future__ import annotations

import argparse
import hashlib
import math
import platform
import statistics
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from tools.effectiveness_report import (  # noqa: E402
    REPORT_FORMAT,
    REPORT_FORMAT_VERSION,
    DatasetTruth,
    EffectivenessDataError,
    canonical_json,
    load_mfcadpp_truth,
    load_mfinstseg_truth,
    load_taxonomy,
    score_inventory,
    validate_report,
)


def _git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _selection_hash(ids: list[str]) -> str:
    return hashlib.sha256(("\n".join(ids) + "\n").encode("utf-8")).hexdigest()


def _display_path(path: Path) -> str:
    """Keep repository paths portable and external provenance unambiguous."""

    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def _mfcadpp_selection(
    root: Path,
) -> tuple[list[str], Callable[[str], DatasetTruth], dict[str, Any]]:
    paths = sorted(root.glob("*.st*p"), key=lambda path: path.name)
    if not paths:
        raise EffectivenessDataError(f"no MFCAD++ STEP files under {root}")
    by_id = {path.stem: path for path in paths}
    if len(by_id) != len(paths):
        raise EffectivenessDataError("MFCAD++ model IDs are not unique")
    ids = sorted(by_id)
    return ids, lambda model_id: load_mfcadpp_truth(by_id[model_id]), {"excluded": {}}


def _partition_ids(path: Path) -> list[str]:
    if not path.is_file():
        raise EffectivenessDataError(f"missing MFInstSeg partition: {path}")
    values = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not values:
        raise EffectivenessDataError(f"empty MFInstSeg partition: {path}")
    return values


def _mfinstseg_selection(
    root: Path, partition_root: Path
) -> tuple[list[str], Callable[[str], DatasetTruth], dict[str, Any]]:
    partitions = {
        split: _partition_ids(partition_root / f"{split}.txt")
        for split in ("train", "val", "test")
    }
    duplicates = {
        split: sorted(model_id for model_id, count in Counter(values).items() if count > 1)
        for split, values in partitions.items()
    }
    memberships: dict[str, set[str]] = {}
    for split, values in partitions.items():
        for model_id in values:
            memberships.setdefault(model_id, set()).add(split)
    leaked = sorted(model_id for model_id, splits in memberships.items() if len(splits) > 1)
    excluded = set(duplicates["test"]) | set(leaked)
    ids = sorted(set(partitions["test"]) - excluded)
    if not ids:
        raise EffectivenessDataError("MFInstSeg test partition is empty after exclusions")
    return (
        ids,
        lambda model_id: load_mfinstseg_truth(root, model_id),
        {
            "excluded": {
                "duplicate_test_ids": duplicates["test"],
                "cross_split_ids": leaked,
            },
            "partition_counts": {
                split: {"rows": len(values), "unique": len(set(values))}
                for split, values in partitions.items()
            },
        },
    )


def _ratio(numerator: int, denominator: int) -> dict[str, int | float | None]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": None if denominator == 0 else numerator / denominator,
    }


def _summarize(rows: list[dict[str, Any]], selected: int, invalid: int) -> dict[str, Any]:
    valid = [row for row in rows if row.get("status") == "evaluated"]
    records: Counter[str] = Counter()
    mapped_classes: Counter[str] = Counter()
    drops: Counter[str] = Counter()
    diagnostics: Counter[str] = Counter()
    observations: Counter[str] = Counter()
    per_class: dict[str, Counter[str]] = {}
    mismatches = 0
    for row in valid:
        records.update(row["physical_records"])
        mapped_classes.update(row["mapped_dataset_class_records"])
        drops.update(row["reconciliation_drops"])
        diagnostics.update(row["unsupported_diagnostics"])
        observations.update(row["predicate_observations"])
        mismatches += row["taxonomy_mismatch_defining_faces"]
        for class_id, class_row in row["classes"].items():
            aggregate = per_class.setdefault(class_id, Counter())
            for field in (
                "labelled_faces",
                "matched_defining_faces",
                "mapped_defining_faces",
                "truth_instances",
                "recalled_instances",
            ):
                aggregate[field] += class_row[field]
            aggregate["status"] = class_row["status"]
    classes = {}
    for class_id, aggregate in sorted(per_class.items(), key=lambda item: int(item[0])):
        classes[class_id] = {
            "status": aggregate["status"],
            "defining_face_precision": _ratio(
                aggregate["matched_defining_faces"], aggregate["mapped_defining_faces"]
            ),
            "defining_face_recall": _ratio(
                aggregate["matched_defining_faces"], aggregate["labelled_faces"]
            ),
            "instance_recall": _ratio(
                aggregate["recalled_instances"], aggregate["truth_instances"]
            ),
        }
    return {
        "selected": selected,
        "loaded": selected - invalid,
        "invalid": invalid,
        "evaluated": len(valid),
        "empty": sum(row["no_physical_records"] for row in valid),
        "physical_records": dict(sorted(records.items())),
        "mapped_dataset_class_records": dict(sorted(mapped_classes.items())),
        "taxonomy_mismatch_defining_faces": mismatches,
        "reconciliation_drops": dict(sorted(drops.items())),
        "unsupported_diagnostics": dict(sorted(diagnostics.items())),
        "predicate_observations": dict(sorted(observations.items())),
        "classes": classes,
    }


def _runtime(rows: list[dict[str, Any]]) -> dict[str, int | float | None]:
    values = sorted(row["seconds"] for row in rows if row.get("status") == "evaluated")
    if not values:
        return {
            "count": 0,
            "total_seconds": 0.0,
            "min_seconds": None,
            "median_seconds": None,
            "p95_seconds": None,
            "max_seconds": None,
        }
    return {
        "count": len(values),
        "total_seconds": sum(values),
        "min_seconds": values[0],
        "median_seconds": statistics.median(values),
        "p95_seconds": values[math.ceil(0.95 * len(values)) - 1],
        "max_seconds": values[-1],
    }


def _environment() -> dict[str, str]:
    import build123d
    import OCP

    return {
        "python": platform.python_version(),
        "build123d": getattr(build123d, "__version__", "unknown"),
        "ocp": getattr(OCP, "__version__", "unknown"),
        "os": platform.platform(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", choices=("mfcadpp", "mfinstseg"))
    parser.add_argument("root", type=Path)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--taxonomy",
        type=Path,
        default=ROOT / "docs" / "benchmarks" / "effectiveness-taxonomy-v1.json",
    )
    parser.add_argument("--partition-root", type=Path)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--allow-invalid", action="store_true")
    args = parser.parse_args()
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    try:
        if args.dataset == "mfcadpp":
            ids, loader, selection_extra = _mfcadpp_selection(args.root)
        else:
            if args.partition_root is None:
                raise EffectivenessDataError("--partition-root is required for MFInstSeg")
            ids, loader, selection_extra = _mfinstseg_selection(args.root, args.partition_root)
        if args.limit is not None:
            ids = ids[: args.limit]
        taxonomy = load_taxonomy(args.taxonomy, args.dataset)
    except EffectivenessDataError as error:
        parser.error(str(error))

    from build123d import import_step

    from b123d_recognisers import __version__
    from b123d_recognisers.result import _take_inventory

    rows: list[dict[str, Any]] = []
    invalid = 0
    for model_id in ids:
        try:
            truth = loader(model_id)
            part = import_step(truth.step_path)
            started = time.perf_counter()
            product = _take_inventory(part)
            seconds = time.perf_counter() - started
            row = score_inventory(truth, part, product, taxonomy, seconds)
            row["status"] = "evaluated"
        except (EffectivenessDataError, OSError, RuntimeError, ValueError) as error:
            invalid += 1
            row = {"model_id": model_id, "status": "invalid", "reason": str(error)}
        rows.append(row)
    summary = _summarize(rows, len(ids), invalid)
    report = {
        "format": REPORT_FORMAT,
        "format_version": REPORT_FORMAT_VERSION,
        "dataset": {"name": args.dataset, "version": args.dataset_version},
        "package": {"name": "b123d-recognisers", "version": __version__, "commit": _git_commit()},
        "environment": _environment(),
        "selection": {
            "rule": "unique model ID, lexical ascending",
            "limit": args.limit,
            "selected_ids_sha256": _selection_hash(ids),
            **selection_extra,
        },
        "mapping": {
            "format_version": 1,
            "sha256": hashlib.sha256(args.taxonomy.read_bytes()).hexdigest(),
            "path": _display_path(args.taxonomy),
        },
        "models": rows,
        "summary": summary,
        "runtime": _runtime(rows),
    }
    validate_report(report)
    if invalid and not args.allow_invalid:
        print(
            f"refusing partial report: {invalid}/{len(ids)} selected models invalid; "
            "use --allow-invalid only with an explicit recorded policy",
            file=sys.stderr,
        )
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(canonical_json(report), encoding="utf-8")
    print(canonical_json(summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
