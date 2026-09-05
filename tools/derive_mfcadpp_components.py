#!/usr/bin/env python3
"""Derive non-native face-adjacency instance components for one MFCAD++ class."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from tools.effectiveness_report import load_mfcadpp_truth  # noqa: E402


def _commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _selection_hash(ids: list[str]) -> str:
    return hashlib.sha256(("\n".join(ids) + "\n").encode()).hexdigest()


def _components(graph: Any, nodes: set[Any]) -> tuple[frozenset[Any], ...]:
    remaining = set(nodes)
    found = []
    while remaining:
        seed = min(remaining, key=lambda node: node.index)
        component = {seed}
        pending = [seed]
        while pending:
            current = pending.pop()
            for neighbour in graph.neighbours(current):
                if neighbour in remaining and neighbour not in component:
                    component.add(neighbour)
                    pending.append(neighbour)
        remaining -= component
        found.append(frozenset(component))
    return tuple(found)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--class-id", type=int, default=8)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    from quiddity import import_step_geometry as import_step
    from quiddity._candidates import FamilyId
    from quiddity._dispositions import Outcome
    from quiddity.result import _take_inventory

    paths = sorted(args.root.glob("*.st*p"))[: args.limit]
    if not paths:
        parser.error("the selected workload contains no STEP files")
    rows = []
    truth_total = recalled_total = 0
    for path in paths:
        truth = load_mfcadpp_truth(path)
        labelled_indices = {
            index for index, class_id in enumerate(truth.semantic) if class_id == args.class_id
        }
        if not labelled_indices:
            continue
        part = import_step(path)
        faces = tuple(part.faces())
        if len(faces) != len(truth.semantic):
            raise RuntimeError(f"{path.stem}: imported face count does not match labels")
        product = _take_inventory(part)
        graph = product.context.graph
        nodes = {graph.require_node(faces[index]) for index in labelled_indices}
        components = _components(graph, nodes)
        claims = tuple(
            product.evidence.defining_of(disposition.candidate)
            for disposition in product.reconciliation.for_family(FamilyId.THROUGH_STEPS)
            if disposition.outcome is Outcome.ACCEPTED
        )
        recalled = sum(any(component & claim for claim in claims) for component in components)
        truth_total += len(components)
        recalled_total += recalled
        rows.append(
            {
                "model_id": path.stem,
                "labelled_faces": len(labelled_indices),
                "derived_components": len(components),
                "recalled_components": recalled,
                "through_step_claims": len(claims),
            }
        )
    report = {
        "format": "b123d-recognisers-mfcadpp-derived-components",
        "format_version": 1,
        "implementation_commit": _commit(),
        "class_id": args.class_id,
        "derivation": (
            "connected components of same-class original faces under shared-edge adjacency"
        ),
        "native_instance_labels": False,
        "selection": {
            "limit": args.limit,
            "selected_ids_sha256": _selection_hash([path.stem for path in paths]),
        },
        "models_with_class": len(rows),
        "labelled_faces": sum(row["labelled_faces"] for row in rows),
        "derived_components": truth_total,
        "recalled_components": recalled_total,
        "derived_component_recall": recalled_total / truth_total if truth_total else None,
        "models": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "models"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
