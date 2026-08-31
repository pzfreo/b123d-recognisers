#!/usr/bin/env python3
"""Measure accepted evidence overlap with derived MFCAD++ class components.

This is evidence tooling, not a recogniser. Dataset labels select an audit population only;
they never influence production candidates, reconciliation, or geometric predicates. MFCAD++
does not publish instance identifiers, so connected same-label faces are reported explicitly as
non-native shared-edge component proxies rather than ground-truth feature instances.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from b123d_recognisers._adjacency import axis_aligned_axis  # noqa: E402
from b123d_recognisers._candidates import FamilyId  # noqa: E402
from b123d_recognisers._dispositions import Outcome  # noqa: E402
from b123d_recognisers.result import _take_inventory  # noqa: E402
from tools.derive_mfcadpp_components import _components  # noqa: E402
from tools.effectiveness_report import load_mfcadpp_truth  # noqa: E402


def _commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _selection_hash(ids: list[str]) -> str:
    return hashlib.sha256(("\n".join(ids) + "\n").encode()).hexdigest()


def _accepted_claims(product: Any) -> tuple[dict[str, Any], ...]:
    claims = []
    for family in FamilyId:
        if family is FamilyId.LEGACY:
            continue
        for disposition in product.reconciliation.for_family(family):
            if disposition.outcome is not Outcome.ACCEPTED:
                continue
            candidate = disposition.candidate
            claims.append(
                {
                    "family": family.value,
                    "defining": product.evidence.defining_of(candidate),
                    "constituent": product.evidence.constituent_of(candidate),
                }
            )
    return tuple(claims)


def _relation(component: frozenset[Any], claims: tuple[dict[str, Any], ...], role: str) -> dict:
    touched = [claim for claim in claims if component & claim[role]]
    covered = set().union(*(claim[role] for claim in touched)) if touched else set()
    return {
        "covered_faces": len(component & covered),
        "touching_records": len(touched),
        "touching_families": sorted({claim["family"] for claim in touched}),
        "full": component <= covered,
    }


def _internal_arcs(graph: Any, node: Any, ordered: list[Any]) -> list[dict[str, Any]]:
    arcs = []
    for other in ordered:
        if other.index <= node.index:
            continue
        kind = graph.arc(node, other)
        if kind is not None:
            arcs.append({"to": other.index, "kind": kind})
    return arcs


def _plane_value(plane: tuple[int, float] | None) -> dict[str, str | float] | None:
    if plane is None:
        return None
    return {"axis": "xyz"[plane[0]], "coordinate": plane[1]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--class-id", type=int, required=True)
    parser.add_argument("--mapped-family", action="append", default=[])
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    from build123d import import_step

    paths = sorted(args.root.glob("*.st*p"))[: args.limit]
    if not paths:
        parser.error("the selected workload contains no STEP files")
    known = {family.value for family in FamilyId if family is not FamilyId.LEGACY}
    unknown = set(args.mapped_family) - known
    if unknown:
        parser.error(f"unknown mapped families: {', '.join(sorted(unknown))}")

    rows = []
    family_component_touches: Counter[str] = Counter()
    totals: Counter[str] = Counter()
    for path in paths:
        truth = load_mfcadpp_truth(path)
        indices = {
            index for index, class_id in enumerate(truth.semantic) if class_id == args.class_id
        }
        if not indices:
            continue
        part = import_step(path)
        faces = tuple(part.faces())
        if len(faces) != len(truth.semantic):
            raise RuntimeError(f"{path.stem}: imported face count does not match labels")
        product = _take_inventory(part)
        graph = product.context.graph
        nodes = {graph.require_node(faces[index]) for index in indices}
        claims = _accepted_claims(product)
        mapped = tuple(claim for claim in claims if claim["family"] in args.mapped_family)
        for ordinal, component in enumerate(_components(graph, nodes), start=1):
            ordered = sorted(component, key=lambda node: node.index)
            planes = {
                node: axis_aligned_axis(graph.face(node).wrapped)
                for node in ordered
            }
            principal_axis_names = []
            for node in ordered:
                plane = planes[node]
                if graph.face(node).geom_type.name == "PLANE" and plane is not None:
                    principal_axis_names.append("xyz"[plane[0]])
            defining = _relation(component, claims, "defining")
            constituent = _relation(component, claims, "constituent")
            mapped_defining = _relation(component, mapped, "defining")
            mapped_constituent = _relation(component, mapped, "constituent")
            for family in constituent["touching_families"]:
                family_component_touches[family] += 1
            totals["components"] += 1
            totals["faces"] += len(component)
            for name, relation in (
                ("defining", defining),
                ("constituent", constituent),
                ("mapped_defining", mapped_defining),
                ("mapped_constituent", mapped_constituent),
            ):
                totals[f"{name}_covered_faces"] += relation["covered_faces"]
                totals[f"{name}_touched_components"] += relation["covered_faces"] > 0
                totals[f"{name}_full_components"] += relation["full"]
            rows.append(
                {
                    "model_id": path.stem,
                    "component": ordinal,
                    "face_indices": [node.index for node in ordered],
                    "face_count": len(component),
                    "surface_counts": dict(
                        sorted(Counter(graph.face(node).geom_type.name for node in ordered).items())
                    ),
                    "principal_plane_axes": dict(
                        sorted(Counter(principal_axis_names).items())
                    ),
                    "faces": [
                        {
                            "index": node.index,
                            "plane": _plane_value(planes[node]),
                            "bounds": graph.bounds(node),
                            "area": float(graph.face(node).area),
                            "internal_arcs": _internal_arcs(graph, node, ordered),
                            "external_neighbours": sum(
                                neighbour not in component for neighbour in graph.neighbours(node)
                            ),
                        }
                        for node in ordered
                    ],
                    "accepted": {"defining": defining, "constituent": constituent},
                    "mapped": {
                        "families": sorted(args.mapped_family),
                        "defining": mapped_defining,
                        "constituent": mapped_constituent,
                    },
                }
            )

    report = {
        "format": "b123d-recognisers-mfcadpp-component-overlap-audit",
        "format_version": 1,
        "implementation_commit": _commit(),
        "class_id": args.class_id,
        "derivation": (
            "connected components of same-class original faces under shared-edge adjacency"
        ),
        "native_instance_labels": False,
        "mapped_families": sorted(args.mapped_family),
        "selection": {
            "limit": args.limit,
            "selected_ids_sha256": _selection_hash([path.stem for path in paths]),
        },
        "models_with_class": len({row["model_id"] for row in rows}),
        "summary": dict(sorted(totals.items())),
        "constituent_component_touches_by_family": dict(sorted(family_component_touches.items())),
        "components": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    summary = {key: value for key, value in report.items() if key != "components"}
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
