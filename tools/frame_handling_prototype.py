"""Prototype part-relative frame normalization for rigid-motion-invariant recognition.

This is deliberately outside the public package.  It asks one architectural question: can an
orthonormal frame inferred only from a part's analytic faces normalize independently presented
copies closely enough that the existing recognisers and reconciliation recover the same feature
occurrences?  Records remain expressed in the normalized frame; mapping them back to caller space
is a separate contract problem and is intentionally not hidden by this experiment.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from build123d import Axis, Pos  # noqa: E402

from b123d_recognisers.frames import (  # noqa: E402
    PartFrame,
    RefusedPartFrame,
    _normalize_part,
    infer_part_frame,
)
from tests.golden._common import load_fixture  # noqa: E402
from tools.rigid_motion_sweep import ROTATIONS, _match, _occurrences  # noqa: E402

GOLDEN_ROOT = ROOT / "tests" / "golden"


def normalize_part(part):
    """Compatibility adapter from the evidence harness to the production-shaped spike."""

    frame = infer_part_frame(part)
    if isinstance(frame, RefusedPartFrame):
        raise ValueError(frame.reason.value)
    assert isinstance(frame, PartFrame)
    return _normalize_part(part, frame), frame


def evaluate_goldens() -> dict[str, object]:
    """Compare independently normalized original/rotated copies occurrence by occurrence."""

    totals = {
        rotation.name: {
            "baseline_records": 0,
            "same_family": 0,
            "reclassified": 0,
            "absent": 0,
            "introduced": 0,
        }
        for rotation in ROTATIONS
    }
    fixtures: dict[str, object] = {}
    refused: dict[str, str] = {}
    for fixture_path in sorted(GOLDEN_ROOT.glob("*/fixture.py")):
        fixture = fixture_path.parent.name
        part = load_fixture(fixture_path).build_fixture()
        try:
            normalized, _frame = normalize_part(part)
            baseline = _occurrences(normalized)
        except ValueError as exc:
            refused[fixture] = str(exc)
            continue
        rows = {}
        for rotation in ROTATIONS:
            rotated = part.rotate(rotation.axis, rotation.degrees)
            normalized_rotated, _rotated_frame = normalize_part(rotated)
            occurrences = _occurrences(normalized_rotated)
            pairs, absent, introduced = _match(baseline, occurrences)
            same = sum(baseline[left].family == occurrences[right].family for left, right in pairs)
            row = {
                "baseline_records": len(baseline),
                "same_family": same,
                "reclassified": len(pairs) - same,
                "absent": len(absent),
                "introduced": len(introduced),
            }
            rows[rotation.name] = row
            for key, value in row.items():
                totals[rotation.name][key] += value
        fixtures[fixture] = rows
    return {"schema": 1, "totals": totals, "refused": refused, "fixtures": fixtures}


def evaluate_translated_goldens() -> dict[str, object]:
    """Exercise full rigid placement: translation alone and combined with rotation."""

    presentations = {
        "T": lambda part: Pos(173, -91, 42) * part,
        "X30+T": lambda part: Pos(173, -91, 42) * part.rotate(Axis.X, 30),
    }
    totals = {
        name: {
            "baseline_records": 0,
            "same_family": 0,
            "reclassified": 0,
            "absent": 0,
            "introduced": 0,
        }
        for name in presentations
    }
    refused: dict[str, str] = {}
    for fixture_path in sorted(GOLDEN_ROOT.glob("*/fixture.py")):
        fixture = fixture_path.parent.name
        part = load_fixture(fixture_path).build_fixture()
        try:
            baseline = _occurrences(normalize_part(part)[0])
            for name, place in presentations.items():
                occurrences = _occurrences(normalize_part(place(part))[0])
                pairs, absent, introduced = _match(baseline, occurrences)
                same = sum(
                    baseline[left].family == occurrences[right].family for left, right in pairs
                )
                row = totals[name]
                row["baseline_records"] += len(baseline)
                row["same_family"] += same
                row["reclassified"] += len(pairs) - same
                row["absent"] += len(absent)
                row["introduced"] += len(introduced)
        except ValueError as exc:
            refused[fixture] = str(exc)
    return {"schema": 1, "totals": totals, "refused": refused}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the complete machine report")
    args = parser.parse_args()
    report = evaluate_goldens()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    for name, row in report["totals"].items():
        print(name, row)
    print("refused", report["refused"])


if __name__ == "__main__":
    main()
