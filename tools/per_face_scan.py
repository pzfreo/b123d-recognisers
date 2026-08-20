#!/usr/bin/env python3
"""Per-face precision and recall for the claiming families against a labelled corpus.

Epic 0002 item 0. Every recall figure this package quotes outside chamfers and angled steps
comes from non-negative least squares fitting record counts against labelled-face counts across
models -- correlational, unable to separate "not recognised" from "recognised under a different
family name", and weak for several families. This observes attribution instead: a claim names
the faces that established a record, the corpus names each face, so the join is direct.

**It measures claiming, not recognition, and the difference is the point.** Only families that
write into the :class:`~b123d_recognisers._claims.ClaimLedger` appear here. A class this package
recognises through a non-claiming family scores zero, which is a statement about the ledger and
not about the recogniser. Read the per-label table with :data:`CLAIMING` in front of you.

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

#: The families that write a defining claim, and so the only ones this scan can see. Grooves
#: and turned steps claim too but have no MFCAD++ counterpart at all -- the corpus is prismatic
#: and those are turning features -- so they are absent from a run over it rather than scoring
#: zero on it.
CLAIMING = ("Slot", "Pocket", "PrismaticPocket", "Passage", "Chamfer", "AngledStep")

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


def scan_part(part, labels):
    """One part's claimed faces, as ``{family: Counter(label)}`` plus the record counts.

    Runs the claiming families against one ledger and applies the reconcilers, so what is
    counted is what a consumer receives rather than what was proposed. A claim whose record a
    rule dropped is skipped -- counting it would credit the family with a face the caller never
    sees, which is the arithmetic that made the old fitted figures unreadable.
    """

    import b123d_recognisers as r
    from b123d_recognisers._adjacency import FaceGraph
    from b123d_recognisers._claims import ClaimLedger
    from b123d_recognisers._reconcile import (
        chamfers_that_are_not_angled_steps,
        reconcile_recesses,
    )

    faces = list(part.faces())
    graph = FaceGraph(part)
    ledger = ClaimLedger(graph)
    at = {face: i for i, face in enumerate(faces)}

    slots = r.recognise_slots(part, ledger=ledger)
    pockets = r.recognise_pockets(part, ledger=ledger)
    ring_pockets = r.recognise_prismatic_pockets(part, ledger=ledger)
    slots, pockets, ring_pockets, passages = reconcile_recesses(
        part, slots, pockets, ring_pockets, ledger
    )
    proposed = r.recognise_chamfers(part, ledger=ledger)
    steps = r.recognise_angled_steps(part, ledger=ledger)
    chamfers = chamfers_that_are_not_angled_steps(proposed, ledger)

    kept = {
        id(record)
        for record in (*slots, *pockets, *ring_pockets, *passages, *chamfers, *steps)
    }
    records = {
        "Slot": len(slots),
        "Pocket": len(pockets),
        "PrismaticPocket": len(ring_pockets),
        "Passage": len(passages),
        "Chamfer": len(chamfers),
        "AngledStep": len(steps),
    }

    claimed: dict[str, Counter] = defaultdict(Counter)
    # Distinct faces, because two families legitimately claim one -- a rectangular passage's
    # wall is a pocket wall to the family that reads it blind. Summing the per-family counters
    # instead reported *124%* of one class claimed, which is how this was found: a share above
    # 100% is arithmetically impossible and the overlap it exposed is a real reconciliation
    # question, not a counting artefact.
    covered: set[int] = set()
    for claim in ledger.claims:
        family = type(claim.claimant).__name__
        if family not in CLAIMING or id(claim.claimant) not in kept:
            continue
        for node in claim.defining:
            index = at[graph.face(node)]
            claimed[family][labels[index]] += 1
            covered.add(index)
    return claimed, records, Counter(labels[index] for index in covered)


def scan(corpus: Path):
    """Every model in *corpus*, skipping any whose label count and face count disagree."""

    from build123d import import_step

    claimed: dict[str, Counter] = defaultdict(Counter)
    records: Counter = Counter()
    per_label: Counter = Counter()
    covered: Counter = Counter()
    models = skipped = 0

    for path in sorted(corpus.glob("*.st*p")):
        part = import_step(path)
        labels = [int(name) for name in _LABEL.findall(path.read_bytes())]
        if len(labels) != len(part.faces()):
            skipped += 1
            continue
        models += 1
        per_label.update(labels)
        part_claimed, part_records, part_covered = scan_part(part, labels)
        for family, counts in part_claimed.items():
            claimed[family].update(counts)
        records.update(part_records)
        covered.update(part_covered)

    return {
        "models": models,
        "skipped": skipped,
        "records": dict(records),
        "claimed": {family: dict(counts) for family, counts in claimed.items()},
        "faces_per_label": dict(per_label),
        "faces_covered": dict(covered),
    }


def report(result) -> str:
    """The two tables, as text."""

    claimed = {family: Counter(counts) for family, counts in result["claimed"].items()}
    lines = [f"models scanned: {result['models']} (skipped {result['skipped']})", ""]

    lines.append("PER-FAMILY -- what the faces a family claims are actually labelled")
    lines.append(f"{'family':<12}{'records':>8}{'faces':>7}  labels")
    for family in CLAIMING:
        counts = claimed.get(family, Counter())
        dist = ", ".join(f"{LABELS.get(k, k)}={v}" for k, v in counts.most_common())
        n = sum(counts.values())
        lines.append(f"{family:<12}{result['records'].get(family, 0):>8}{n:>7}  {dist or '-'}")

    covered = {int(k): v for k, v in result["faces_covered"].items()}

    lines += ["", "PER-LABEL -- the fraction of each class any CLAIMING family claims", ""]
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
