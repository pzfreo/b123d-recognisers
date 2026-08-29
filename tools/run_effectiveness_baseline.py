#!/usr/bin/env python3
"""Produce a canonical Epic 0005 effectiveness report from a labelled STEP corpus."""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import subprocess
import sys
import tempfile
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
    summarize_rows,
    summarize_runtime,
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


def _write_new_report(path: Path, contents: str) -> None:
    """Atomically create a report, refusing to replace historical evidence."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent, delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    except FileExistsError as error:
        raise EffectivenessDataError(f"refusing to overwrite existing report: {path}") from error
    except OSError as error:
        raise EffectivenessDataError(f"could not create report {path}: {error}") from error
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


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
    parser.add_argument(
        "--recognition-frame",
        choices=("raw", "framed"),
        default="raw",
        help="score caller-space recognition or the inferred local framed route",
    )
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
    from b123d_recognisers.frames import RefusedPartFrame, _normalize_part, infer_part_frame
    from b123d_recognisers.result import _take_inventory

    rows: list[dict[str, Any]] = []
    invalid = 0
    for model_id in ids:
        try:
            truth = loader(model_id)
            part = import_step(truth.step_path)
            started = time.perf_counter()
            working_part = part
            if args.recognition_frame == "framed":
                frame = infer_part_frame(part)
                if isinstance(frame, RefusedPartFrame):
                    raise EffectivenessDataError(f"frame refused: {frame.reason.value}")
                working_part = _normalize_part(part, frame)
            product = _take_inventory(working_part)
            seconds = time.perf_counter() - started
            row = score_inventory(truth, working_part, product, taxonomy, seconds)
            row["status"] = "evaluated"
        except (EffectivenessDataError, OSError, RuntimeError, ValueError) as error:
            invalid += 1
            row = {"model_id": model_id, "status": "invalid", "reason": str(error)}
        rows.append(row)
    summary = summarize_rows(rows, len(ids), invalid)
    report = {
        "format": REPORT_FORMAT,
        "format_version": REPORT_FORMAT_VERSION,
        "dataset": {"name": args.dataset, "version": args.dataset_version},
        "package": {"name": "b123d-recognisers", "version": __version__, "commit": _git_commit()},
        "environment": _environment(),
        "selection": {
            "rule": "unique model ID, lexical ascending",
            "limit": args.limit,
            "recognition_frame": args.recognition_frame,
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
        "runtime": summarize_runtime(rows),
    }
    validate_report(report)
    if invalid and not args.allow_invalid:
        print(
            f"refusing partial report: {invalid}/{len(ids)} selected models invalid; "
            "use --allow-invalid only with an explicit recorded policy",
            file=sys.stderr,
        )
        return 2
    try:
        _write_new_report(args.output, canonical_json(report))
    except EffectivenessDataError as error:
        parser.error(str(error))
    print(canonical_json(summary), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
