"""Deterministic golden-corpus rigid-motion evidence for issue #272.

This is a measurement tool, not a recogniser.  It matches accepted census occurrences by the
original defining face indices that survive a rigid transform.  A baseline occurrence may match
a rotated occurrence when either defining set contains the other: some families name only the
walls while another family names the same walls plus its terminal faces.  Matching therefore
proves a shared geometric occurrence rather than inferring reclassification from equal counts.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from collections import Counter
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from build123d import Axis, Vector  # noqa: E402

from quiddity.census import _LEGACY_CENSUS_BINDINGS  # noqa: E402
from quiddity.result import PHYSICAL_FAMILIES, _take_inventory  # noqa: E402
from tests.golden._common import load_fixture  # noqa: E402

GOLDEN_ROOT = ROOT / "tests" / "golden"
JSON_REPORT = ROOT / "docs" / "benchmarks" / "rigid-motion-sweep.json"
MARKDOWN_REPORT = ROOT / "docs" / "benchmarks" / "rigid-motion-sweep.md"
BASELINE_COMMIT = "b03ba00ccc1970181580a55a6331332166ccb49c"


@dataclass(frozen=True)
class Rotation:
    name: str
    axis: Axis
    degrees: float


@dataclass(frozen=True)
class Occurrence:
    family: str
    defining_faces: frozenset[int]
    record: object | None = None


ROTATIONS = (
    Rotation("Z30", Axis.Z, 30.0),
    Rotation("X30", Axis.X, 30.0),
    Rotation("X90", Axis.X, 90.0),
)


def _record_evidence(record: object, by_record: dict[int, frozenset[int]]) -> frozenset[int]:
    """Return direct evidence, or the union carried by a derived pattern's members."""

    seen: set[int] = set()

    def visit(value: object) -> frozenset[int]:
        identity = id(value)
        if identity in seen:
            return frozenset()
        seen.add(identity)
        direct = by_record.get(identity)
        if direct is not None:
            return direct
        if dataclasses.is_dataclass(value) and not isinstance(value, type):
            return frozenset().union(
                *(visit(getattr(value, field.name)) for field in dataclasses.fields(value))
            )
        if isinstance(value, (list, tuple)):
            return frozenset().union(*(visit(item) for item in value))
        return frozenset()

    return visit(record)


def _occurrences(part) -> tuple[Occurrence, ...]:
    product = _take_inventory(part)
    by_record: dict[int, frozenset[int]] = {}
    for family in PHYSICAL_FAMILIES:
        candidates = (
            product.distinct_steps.candidates
            if family.value == "turned_steps"
            else product.accepted.candidate_set(family).candidates
        )
        for candidate in candidates:
            by_record[id(candidate.record)] = frozenset(
                node.index for node in product.evidence.defining_of(candidate)
            )

    occurrences: list[Occurrence] = []
    # Keep the pinned detector-baseline identities paired with the private detector result.
    for census_family, result_field in _LEGACY_CENSUS_BINDINGS:
        records = (
            tuple(candidate.record for candidate in product.distinct_steps.candidates)
            if census_family == "step"
            else getattr(product._legacy_result, result_field)
        )
        for record in records:
            evidence = _record_evidence(record, by_record)
            if not evidence:
                raise RuntimeError(
                    f"{census_family} occurrence has no defining evidence; cannot match it"
                )
            occurrences.append(Occurrence(census_family, evidence, record))
    return tuple(occurrences)


def _validate_face_correspondence(baseline, rotated, rotation: Rotation) -> None:
    """Prove face index means the same geometric face after this fixture rotation."""

    before, after = baseline.faces(), rotated.faces()
    if len(before) != len(after):
        raise RuntimeError(f"{rotation.name}: rigid motion changed the face count")
    for index, (left, right) in enumerate(zip(before, after, strict=True)):
        restored = Vector(*tuple(right.center())).rotate(rotation.axis, -rotation.degrees)
        if (
            left.geom_type != right.geom_type
            or len(left.edges()) != len(right.edges())
            or abs(left.area - right.area) > 1e-5
            or (left.center() - restored).length > 1e-5
        ):
            raise RuntimeError(
                f"{rotation.name}: face index {index} does not preserve rigid correspondence"
            )


def _match(
    baseline: tuple[Occurrence, ...], rotated: tuple[Occurrence, ...]
) -> tuple[tuple[tuple[int, int], ...], tuple[int, ...], tuple[int, ...]]:
    """Maximum-cardinality one-to-one evidence containment matching.

    For equal cardinality, retain the most same-family occurrences, then the greatest evidence
    overlap. The corpus has at most ten occurrences per fixture, so an exact bitmask dynamic
    programme is simpler and more auditable than a heuristic greedy assignment.
    """

    edges: dict[int, tuple[tuple[int, bool, float], ...]] = {}
    for baseline_index, left in enumerate(baseline):
        available = []
        for rotated_index, right in enumerate(rotated):
            if (
                left.defining_faces <= right.defining_faces
                or right.defining_faces <= left.defining_faces
            ):
                overlap = len(left.defining_faces & right.defining_faces) / len(
                    left.defining_faces | right.defining_faces
                )
                available.append((rotated_index, left.family == right.family, overlap))
        edges[baseline_index] = tuple(available)

    @cache
    def solve(index: int, used: int) -> tuple[int, int, float, tuple[tuple[int, int], ...]]:
        if index == len(baseline):
            return (0, 0, 0.0, ())
        best = solve(index + 1, used)
        for rotated_index, same_family, overlap in edges[index]:
            bit = 1 << rotated_index
            if used & bit:
                continue
            count, same, score, pairs = solve(index + 1, used | bit)
            option = (
                count + 1,
                same + int(same_family),
                score + overlap,
                ((index, rotated_index), *pairs),
            )
            if option[:3] > best[:3] or (option[:3] == best[:3] and option[3] < best[3]):
                best = option
        return best

    pairs = solve(0, 0)[3]
    used_baseline = {left for left, _right in pairs}
    used_rotated = {right for _left, right in pairs}
    return (
        pairs,
        tuple(index for index in range(len(baseline)) if index not in used_baseline),
        tuple(index for index in range(len(rotated)) if index not in used_rotated),
    )


def _rotation_result(part, baseline: tuple[Occurrence, ...], rotation: Rotation) -> dict[str, Any]:
    rotated_part = part.rotate(rotation.axis, rotation.degrees)
    _validate_face_correspondence(part, rotated_part, rotation)
    rotated = _occurrences(rotated_part)
    pairs, absent_indices, new_indices = _match(baseline, rotated)

    same = Counter()
    transitions = Counter()
    for baseline_index, rotated_index in pairs:
        left, right = baseline[baseline_index], rotated[rotated_index]
        if left.family == right.family:
            same[left.family] += 1
        else:
            transitions[f"{left.family}->{right.family}"] += 1
    absent = Counter(baseline[index].family for index in absent_indices)
    introduced = Counter(rotated[index].family for index in new_indices)
    return {
        "baseline_records": len(baseline),
        "retained_same_family": sum(same.values()),
        "reclassified": sum(transitions.values()),
        "absent": len(absent_indices),
        "introduced": len(new_indices),
        "same_family": dict(sorted(same.items())),
        "transitions": dict(sorted(transitions.items())),
        "absent_by_family": dict(sorted(absent.items())),
        "introduced_by_family": dict(sorted(introduced.items())),
    }


def sweep() -> dict[str, Any]:
    fixtures: dict[str, Any] = {}
    totals = {rotation.name: Counter() for rotation in ROTATIONS}
    for fixture_path in sorted(GOLDEN_ROOT.glob("*/fixture.py")):
        part = load_fixture(fixture_path).build_fixture()
        baseline = _occurrences(part)
        rotations = {}
        for rotation in ROTATIONS:
            result = _rotation_result(part, baseline, rotation)
            rotations[rotation.name] = result
            for field in (
                "baseline_records",
                "retained_same_family",
                "reclassified",
                "absent",
                "introduced",
            ):
                totals[rotation.name][field] += result[field]
        fixtures[fixture_path.parent.name] = {
            "baseline_records": len(baseline),
            "rotations": rotations,
        }
    return {
        "schema": 1,
        "baseline_commit": BASELINE_COMMIT,
        "matching": "one-to-one defining-face containment after validated rigid correspondence",
        "totals": {name: dict(counts) for name, counts in totals.items()},
        "fixtures": fixtures,
    }


def markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Golden-corpus rigid-motion sweep",
        "",
        f"Baseline: `{report['baseline_commit']}`. Generated by `tools/rigid_motion_sweep.py`.",
        "No recogniser predicates or public outputs are changed by this evidence report.",
        "",
        "Matching is occurrence-level: defining face indices are first validated to preserve",
        "surface type, edge count, area and inverse-rotated centre, then matched one-to-one by",
        "evidence containment. Reclassification is therefore observed, not inferred from counts.",
        "",
        "| rotation | baseline | same family | reclassified | absent | introduced |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in ("Z30", "X30", "X90"):
        row = report["totals"][name]
        lines.append(
            f"| {name} | {row['baseline_records']} | {row['retained_same_family']} | "
            f"{row['reclassified']} | {row['absent']} | {row['introduced']} |"
        )
    lines.extend(["", "## Affected fixtures", ""])
    for fixture, data in report["fixtures"].items():
        affected = []
        for name, result in data["rotations"].items():
            if result["reclassified"] or result["absent"] or result["introduced"]:
                detail = [
                    f"{name}: {result['reclassified']} reclassified, {result['absent']} absent"
                ]
                if result["transitions"]:
                    detail.append(
                        "transitions "
                        + ", ".join(
                            f"{key} ×{value}" for key, value in result["transitions"].items()
                        )
                    )
                if result["absent_by_family"]:
                    detail.append(
                        "absent "
                        + ", ".join(
                            f"{key} ×{value}" for key, value in result["absent_by_family"].items()
                        )
                    )
                affected.append("; ".join(detail))
        if affected:
            lines.append(f"- **{fixture}** — " + "; ".join(affected))
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "This report measures frame coupling. It does not decide whether input world axes are",
            "semantically meaningful, and therefore does not itself require rotation-invariant",
            "predicates or amend ADR 0001. That contract decision follows the measured evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="update the checked-in JSON/Markdown")
    args = parser.parse_args()
    report = sweep()
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.write:
        JSON_REPORT.write_text(rendered, encoding="utf-8")
        MARKDOWN_REPORT.write_text(markdown(report), encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
