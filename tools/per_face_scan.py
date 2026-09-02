#!/usr/bin/env python3
"""Registry-driven physical attribution plus an MFCAD++ label comparison adapter.

Epic 0002 item 0. Every recall figure this package quotes outside chamfers and angled steps
comes from non-negative least squares fitting record counts against labelled-face counts across
models -- correlational, unable to separate "not recognised" from "recognised under a different
family name", and weak for several families. This observes attribution instead: a claim names
the faces that established a record, the corpus names each face, so the join is direct.

**It measures attribution, not recognition, and the difference is the point.** Every registered
physical family appears, including incomplete families with zero attributed occurrences. The
generic counts come from the one completed frozen inventory; MFCAD++ labels are only a comparison
adapter and never define ownership or attribution status.

Reads any directory of MFCAD++-style STEP whose per-face label is the ``ADVANCED_FACE`` name,
defaulting to the vendored subset. ``--json`` writes the raw counts for a caller that wants to
do its own arithmetic.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).parents[1]
VENDORED = ROOT / "tests" / "corpus" / "mfcadpp"
_LABEL = re.compile(rb"ADVANCED_FACE\('(\d+)'")

#: MFCAD++'s own mapping, from ``feature_labels.txt`` in the published archive.
LABELS = {
    0: "Chamfer",
    1: "Through hole",
    2: "Triangular passage",
    3: "Rectangular passage",
    4: "6-sided passage",
    5: "Triangular through slot",
    6: "Rectangular through slot",
    7: "Circular through slot",
    8: "Rectangular through step",
    9: "2-sided through step",
    10: "Slanted through step",
    11: "O-ring",
    12: "Blind hole",
    13: "Triangular pocket",
    14: "Rectangular pocket",
    15: "6-sided pocket",
    16: "Circular end pocket",
    17: "Rectangular blind slot",
    18: "Vertical circular end blind slot",
    19: "Horizontal circular end blind slot",
    20: "Triangular blind step",
    21: "Circular blind step",
    22: "Rectangular blind step",
    23: "Round",
    24: "Stock",
}


def inventory_attribution(product):
    """Primitive-only attribution counts for all registered physical families."""

    from b123d_recognisers._registry import (
        PHYSICAL_DEFINITIONS,
        FullyAttributed,
    )

    result = {}
    for definition in PHYSICAL_DEFINITIONS:
        proposed = product.physical.candidate_set(definition.family).candidates
        accepted = product.accepted.candidate_set(definition.family).candidates
        attributed_candidates = tuple(
            candidate for candidate in proposed if product.evidence.defining_of(candidate)
        )
        attributed_accepted = tuple(
            candidate for candidate in accepted if product.evidence.defining_of(candidate)
        )
        defining = tuple(
            node
            for candidate in attributed_candidates
            for node in product.evidence.defining_of(candidate)
        )
        disposition = definition.attribution
        result[definition.family.value] = {
            "records": len(getattr(product.result, definition.result_field)),
            "candidates": len(proposed),
            "accepted": len(accepted),
            "attributed_candidates": len(attributed_candidates),
            "attributed_accepted": len(attributed_accepted),
            "defining_face_occurrences": len(defining),
            "distinct_defining_faces": len(set(defining)),
            "status": (
                "fully_attributed"
                if isinstance(disposition, FullyAttributed)
                else "incomplete_attribution"
            ),
            "reason": (
                disposition.proof_contract
                if isinstance(disposition, FullyAttributed)
                else disposition.reason
            ),
        }
    return result


def _scan_part(part, labels):
    """One part's claimed faces, as ``{family: Counter(label)}`` plus the record counts.

    Runs the claiming families against one ledger and applies the reconcilers, so what is
    counted is what a consumer receives rather than what was proposed. A claim whose record a
    rule dropped is skipped -- counting it would credit the family with a face the caller never
    sees, which is the arithmetic that made the old fitted figures unreadable.
    """

    from b123d_recognisers._registry import PHYSICAL_DEFINITIONS
    from b123d_recognisers.result import _take_inventory

    faces = list(part.faces())
    product = _take_inventory(part)
    graph = product.context.graph
    at = {face: i for i, face in enumerate(faces)}
    family_names = {
        definition.family: definition.record_types[0].__name__
        for definition in PHYSICAL_DEFINITIONS
    }
    accepted = tuple(
        candidate
        for family in family_names
        for candidate in product.accepted.candidate_set(family).candidates
    )
    records = {
        name: len(product.accepted.candidate_set(family).candidates)
        for family, name in family_names.items()
    }

    claimed: dict[str, Counter] = defaultdict(Counter)
    # Distinct faces, because two families legitimately claim one -- a rectangular passage's
    # wall is a pocket wall to the family that reads it blind. Summing the per-family counters
    # instead reported *124%* of one class claimed, which is how this was found: a share above
    # 100% is arithmetically impossible and the overlap it exposed is a real reconciliation
    # question, not a counting artefact.
    covered: set[int] = set()
    for candidate in accepted:
        family = family_names[candidate.family]
        for node in product.evidence.defining_of(candidate):
            index = at[graph.face(node)]
            claimed[family][labels[index]] += 1
            covered.add(index)
    return (
        claimed,
        records,
        Counter(labels[index] for index in covered),
        inventory_attribution(product),
    )


def scan_part(part, labels):
    """Compatibility label adapter; generic attribution is available separately."""

    claimed, records, covered, _attribution = _scan_part(part, labels)
    return claimed, records, covered


def scan(corpus: Path):
    """Every model in *corpus*, skipping any whose label count and face count disagree."""

    from b123d_recognisers import import_step_geometry as import_step

    claimed: dict[str, Counter] = defaultdict(Counter)
    records: Counter = Counter()
    per_label: Counter = Counter()
    covered: Counter = Counter()
    attribution: dict[str, dict] = {}
    models = skipped = 0

    for path in sorted(corpus.glob("*.st*p")):
        part = import_step(path)
        labels = [int(name) for name in _LABEL.findall(path.read_bytes())]
        if len(labels) != len(part.faces()):
            skipped += 1
            continue
        models += 1
        per_label.update(labels)
        part_claimed, part_records, part_covered, part_attribution = _scan_part(part, labels)
        for family, counts in part_claimed.items():
            claimed[family].update(counts)
        records.update(part_records)
        covered.update(part_covered)
        for family, row in part_attribution.items():
            aggregate = attribution.setdefault(
                family,
                {
                    "records": 0,
                    "candidates": 0,
                    "accepted": 0,
                    "attributed_candidates": 0,
                    "attributed_accepted": 0,
                    "defining_face_occurrences": 0,
                    "distinct_defining_faces": 0,
                    "status": row["status"],
                    "reason": row["reason"],
                },
            )
            if (aggregate["status"], aggregate["reason"]) != (row["status"], row["reason"]):
                raise ValueError("registry attribution metadata changed during one scan")
            for field in (
                "records",
                "candidates",
                "accepted",
                "attributed_candidates",
                "attributed_accepted",
                "defining_face_occurrences",
                "distinct_defining_faces",
            ):
                aggregate[field] += row[field]

    return {
        "models": models,
        "skipped": skipped,
        "records": dict(records),
        "claimed": {family: dict(counts) for family, counts in claimed.items()},
        "faces_per_label": dict(per_label),
        "faces_covered": dict(covered),
        "attribution": attribution,
    }


def report(result) -> str:
    """The two tables, as text."""

    from b123d_recognisers._registry import PHYSICAL_DEFINITIONS

    claimed = {family: Counter(counts) for family, counts in result["claimed"].items()}
    registry_family_for = {
        definition.record_types[0].__name__: definition.family.value
        for definition in PHYSICAL_DEFINITIONS
    }
    lines = [f"models scanned: {result['models']} (skipped {result['skipped']})", ""]

    lines.append("PER-FAMILY -- frozen inventory attribution and corpus labels")
    lines.append(
        f"{'family':<24}{'records':>8}{'candidates':>12}{'accepted':>10}"
        f"{'attr cand':>11}{'attr acc':>10}"
        f"{'faces':>7}  status / labels"
    )
    for family in sorted(result["records"]):
        counts = claimed.get(family, Counter())
        dist = ", ".join(f"{LABELS.get(k, k)}={v}" for k, v in counts.most_common())
        n = sum(counts.values())
        registry_family = registry_family_for[family]
        row = result["attribution"][registry_family]
        lines.append(
            f"{family:<24}{row['records']:>8}{row['candidates']:>12}{row['accepted']:>10}"
            f"{row['attributed_candidates']:>11}{row['attributed_accepted']:>10}"
            f"{n:>7}  {row['status']} / {dist or '-'}"
        )

    covered = {int(k): v for k, v in result["faces_covered"].items()}

    lines += ["", "PER-LABEL -- the fraction of each class any physical family claims", ""]
    lines.append(f"{'label':<34}{'faces':>7}{'claimed':>9}{'share':>8}")
    for label, total in sorted(result["faces_per_label"].items(), key=lambda kv: -kv[1]):
        got = covered.get(int(label), 0)
        name = LABELS.get(int(label), label)
        lines.append(f"{name:<34}{total:>7}{got:>9}{100 * got / total:>7.0f}%")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", nargs="?", type=Path, default=VENDORED)
    parser.add_argument("--json", type=Path, help="write raw counts here as well")
    args = parser.parse_args()

    result = scan(args.corpus)
    print(report(result))
    if args.json:
        args.json.write_text(json.dumps(result, indent=1, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
