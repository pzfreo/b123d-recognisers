#!/usr/bin/env python3
"""Measure the section-recess prototype as an aggregate-only overlay on a labelled corpus.

The output deliberately contains no model rows or model identifiers.  This lets a human run the
MFInstSeg test partition once and return only high-level transfer evidence to the development team.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_TARGET_SHAPES = {13: "triangular", 14: "rectangular", 15: "hexagonal", 16: "obround"}

from tools.effectiveness_report import (  # noqa: E402
    DatasetTruth,
    EffectivenessDataError,
    load_taxonomy,
)
from tools.run_effectiveness_baseline import _mfcadpp_selection, _mfinstseg_selection  # noqa: E402


@dataclass(frozen=True, slots=True)
class _Task:
    truth: DatasetTruth
    target_class: int
    relevant_families: frozenset[str]


@dataclass(frozen=True, slots=True)
class _Counts:
    models: int = 0
    target_faces: int = 0
    baseline_defining: int = 0
    combined_defining: int = 0
    baseline_covered: int = 0
    combined_covered: int = 0
    target_instances: int = 0
    baseline_instances: int = 0
    combined_instances: int = 0
    prototype_occurrences: int = 0
    prototype_defining: int = 0
    prototype_target_defining: int = 0
    prototype_constituent: int = 0
    prototype_target_constituent: int = 0

    def __add__(self, other: _Counts) -> _Counts:
        return _Counts(
            **{
                field: getattr(self, field) + getattr(other, field)
                for field in self.__dataclass_fields__
            }
        )


def _evaluate(task: _Task) -> _Counts:
    from b123d_recognisers import import_step_geometry
    from b123d_recognisers._dispositions import Outcome
    from b123d_recognisers._section_recess_prototype import build_section_recess_prototype
    from b123d_recognisers.result import _take_inventory
    from tools.effectiveness_report import _public_family_id

    part = import_step_geometry(task.truth.step_path)
    faces = tuple(part.faces())
    if len(faces) != len(task.truth.semantic):
        raise EffectivenessDataError(
            f"{len(faces)} imported faces != {len(task.truth.semantic)} labels"
        )
    product = _take_inventory(part)
    graph = product.context.graph
    face_index = {face: index for index, face in enumerate(faces)}
    baseline_claims: list[frozenset[int]] = []
    baseline_constituents: list[frozenset[int]] = []
    for disposition in product.reconciliation.dispositions:
        if disposition.outcome is not Outcome.ACCEPTED:
            continue
        candidate = disposition.candidate
        if _public_family_id(candidate.family.value) in task.relevant_families:
            baseline_claims.append(
                frozenset(
                    face_index[graph.face(node)] for node in product.evidence.defining_of(candidate)
                )
            )
        baseline_constituents.append(
            frozenset(
                face_index[graph.face(node)] for node in product.evidence.constituent_of(candidate)
            )
        )

    document = build_section_recess_prototype(part)
    expected_shape = _TARGET_SHAPES.get(task.target_class)
    occurrences = tuple(
        item
        for item in document.occurrences
        if expected_shape is None or item.classification.section_shape == expected_shape
    )
    prototype_claims = [frozenset(item.evidence.defining_faces) for item in occurrences]
    prototype_constituents = [frozenset(item.evidence.constituent_faces) for item in occurrences]
    target = frozenset(
        index for index, value in enumerate(task.truth.semantic) if value == task.target_class
    )
    truth_instances = tuple(
        instance
        for instance in task.truth.instances
        if instance and task.truth.semantic[min(instance)] == task.target_class
    )
    baseline_covered = (
        frozenset().union(*baseline_constituents) if baseline_constituents else frozenset()
    )
    prototype_covered = (
        frozenset().union(*prototype_constituents) if prototype_constituents else frozenset()
    )
    baseline_defining = frozenset().union(*baseline_claims) if baseline_claims else frozenset()
    prototype_defining = frozenset().union(*prototype_claims) if prototype_claims else frozenset()

    def recalled(instances: tuple[frozenset[int], ...], claims: list[frozenset[int]]) -> int:
        return sum(any(instance & claim for claim in claims) for instance in instances)

    return _Counts(
        models=1,
        target_faces=len(target),
        baseline_defining=len(target & baseline_defining),
        combined_defining=len(target & (baseline_defining | prototype_defining)),
        baseline_covered=len(target & baseline_covered),
        combined_covered=len(target & (baseline_covered | prototype_covered)),
        target_instances=len(truth_instances),
        baseline_instances=recalled(truth_instances, baseline_claims),
        combined_instances=recalled(truth_instances, [*baseline_claims, *prototype_claims]),
        prototype_occurrences=len(occurrences),
        prototype_defining=sum(map(len, prototype_claims)),
        prototype_target_defining=sum(len(target & claim) for claim in prototype_claims),
        prototype_constituent=sum(map(len, prototype_constituents)),
        prototype_target_constituent=sum(len(target & claim) for claim in prototype_constituents),
    )


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def _source() -> dict[str, str]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    diff = subprocess.run(
        ["git", "diff", "--binary", "HEAD", "--"], cwd=ROOT, check=True, capture_output=True
    ).stdout
    return {"commit": commit, "tracked_diff_sha256": hashlib.sha256(diff).hexdigest()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", choices=("mfcadpp", "mfinstseg"))
    parser.add_argument("root", type=Path)
    parser.add_argument("--partition-root", type=Path)
    parser.add_argument("--target-class", type=int, default=16)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=min(4, os.cpu_count() or 1))
    parser.add_argument("--output", "-o", type=Path)
    parser.add_argument(
        "--taxonomy",
        type=Path,
        default=ROOT / "docs" / "benchmarks" / "effectiveness-taxonomy-v1.json",
    )
    args = parser.parse_args()
    try:
        if args.workers <= 0:
            raise EffectivenessDataError("--workers must be positive")
        if args.dataset == "mfcadpp":
            ids, loader, _ = _mfcadpp_selection(args.root)
        else:
            if args.partition_root is None:
                raise EffectivenessDataError("--partition-root is required for MFInstSeg")
            ids, loader, _ = _mfinstseg_selection(args.root, args.partition_root)
        if args.limit is not None:
            if args.limit <= 0:
                raise EffectivenessDataError("--limit must be positive")
            ids = ids[: args.limit]
        taxonomy = load_taxonomy(args.taxonomy, args.dataset)
        mapping = taxonomy.get(args.target_class)
        if mapping is None or not mapping["families"]:
            raise EffectivenessDataError("target class is not mapped by the selected taxonomy")
        tasks = [
            _Task(loader(model_id), args.target_class, frozenset(mapping["families"]))
            for model_id in ids
        ]
    except (EffectivenessDataError, OSError, ValueError) as error:
        parser.error(str(error))

    total = _Counts()
    invalid: Counter[str] = Counter()
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(_evaluate, task): task for task in tasks}
        for future in concurrent.futures.as_completed(futures):
            try:
                total += future.result()
            except (EffectivenessDataError, OSError, RuntimeError, ValueError) as error:
                invalid[type(error).__name__] += 1

    payload: dict[str, Any] = {
        "format": "section-recess-prototype-transfer",
        "format_version": 1,
        "dataset": args.dataset,
        "target_class": args.target_class,
        "target_name": mapping["name"],
        "selected_models": len(tasks),
        "evaluated_models": total.models,
        "invalid_models": sum(invalid.values()),
        "invalid_kinds": dict(sorted(invalid.items())),
        "source": _source(),
        "counts": asdict(total),
        "metrics": {
            "baseline_defining_recall": _ratio(total.baseline_defining, total.target_faces),
            "combined_defining_recall": _ratio(total.combined_defining, total.target_faces),
            "baseline_face_coverage": _ratio(total.baseline_covered, total.target_faces),
            "combined_face_coverage": _ratio(total.combined_covered, total.target_faces),
            "baseline_instance_recall": _ratio(total.baseline_instances, total.target_instances),
            "combined_instance_recall": _ratio(total.combined_instances, total.target_instances),
            "prototype_defining_precision": _ratio(
                total.prototype_target_defining, total.prototype_defining
            ),
            "prototype_constituent_precision": _ratio(
                total.prototype_target_constituent, total.prototype_constituent
            ),
        },
    }
    encoded = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is None:
        sys.stdout.write(encoded)
    else:
        args.output.write_text(encoded, encoding="utf-8")
    return 0 if not invalid else 2


if __name__ == "__main__":
    raise SystemExit(main())
