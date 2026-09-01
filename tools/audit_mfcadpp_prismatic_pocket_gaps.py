#!/usr/bin/env python3
"""Classify untouched MFCAD++ pocket proxies against unchanged recess proofs.

Dataset labels select components to describe. They never participate in proposal discovery or a
geometry predicate. MFCAD++ has no native instance IDs, so connected same-label faces are reported
as component proxies rather than physical feature instances.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from b123d_recognisers._adjacency import (  # noqa: E402
    FaceGraph,
    FaceNode,
    connected_components,
)
from b123d_recognisers._candidates import FamilyId  # noqa: E402
from b123d_recognisers._dispositions import Outcome  # noqa: E402
from b123d_recognisers._geometry import AXIS_ZERO_COS  # noqa: E402
from b123d_recognisers._recess_core import _pocket_proposals_one  # noqa: E402
from b123d_recognisers._rings import (  # noqa: E402
    SPAN_EPS,
    _capped_ends,
    _cross_section,
    _is_void,
    rings,
)
from b123d_recognisers.result import _take_inventory  # noqa: E402
from tools.derive_mfcadpp_components import _components  # noqa: E402
from tools.effectiveness_report import load_mfcadpp_truth  # noqa: E402

_PUBLISHED_VERSION = (
    "MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823"
)
_GATES = (
    "no_principal_planar_walls",
    "no_equal_span_component",
    "not_simple_cycle",
    "invalid_cross_section",
    "material_not_void",
    "not_single_cap",
    "recognisable",
)


@dataclass(frozen=True, slots=True)
class RingProbe:
    stage: int
    first_failed_gate: str
    axis: int | None
    eligible_walls: int
    span_members: int
    cap_counts: tuple[int, int] | None


def _commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def _selection_hash(ids: list[str]) -> str:
    return hashlib.sha256(("\n".join(ids) + "\n").encode()).hexdigest()


def _source_selection_hash(sources: list[tuple[str, str]]) -> str:
    value = "".join(f"{model_id}:{source_hash}\n" for model_id, source_hash in sources)
    return hashlib.sha256(value.encode()).hexdigest()


def _failed(
    stage: int,
    *,
    axis: int | None = None,
    eligible_walls: int = 0,
    span_members: int = 0,
    cap_counts: tuple[int, int] | None = None,
) -> RingProbe:
    return RingProbe(stage, _GATES[stage], axis, eligible_walls, span_members, cap_counts)


def _probe_span_component(
    part: Any,
    graph: FaceGraph,
    ring: tuple[FaceNode, ...],
    axis: int,
    eligible_walls: int,
) -> RingProbe:
    members = set(ring)
    if len(ring) < 3 or any(
        len(set(graph.neighbours(node)) & members) != 2 for node in ring
    ):
        return _failed(
            2, axis=axis, eligible_walls=eligible_walls, span_members=len(ring)
        )
    section = _cross_section(graph, ring, members, axis)
    if section is None:
        return _failed(
            3, axis=axis, eligible_walls=eligible_walls, span_members=len(ring)
        )
    spans = [graph.bounds(node)[axis] for node in ring]
    low, high = min(lo for lo, _hi in spans), max(hi for _lo, hi in spans)
    if not _is_void(part, section, axis, low, high):
        return _failed(
            4, axis=axis, eligible_walls=eligible_walls, span_members=len(ring)
        )
    caps = _capped_ends(graph, ring, members, axis, low, high)
    cap_counts = (len(caps[0]), len(caps[1]))
    if bool(caps[0]) == bool(caps[1]):
        return _failed(
            5,
            axis=axis,
            eligible_walls=eligible_walls,
            span_members=len(ring),
            cap_counts=cap_counts,
        )
    return _failed(
        6,
        axis=axis,
        eligible_walls=eligible_walls,
        span_members=len(ring),
        cap_counts=cap_counts,
    )


def _probe_component(part: Any, graph: FaceGraph, component: frozenset[FaceNode]) -> RingProbe:
    attempts: list[RingProbe] = []
    for axis in (0, 1, 2):
        walls = [
            node
            for node in component
            if graph.is_planar(node)
            and (normal := graph.normal(node)) is not None
            and abs(normal[axis]) <= AXIS_ZERO_COS
        ]
        if not walls:
            attempts.append(_failed(0, axis=axis))
            continue
        adjacent = {node: set(graph.neighbours(node)) for node in walls}

        def shares_span(
            a: FaceNode,
            b: FaceNode,
            *,
            selected_axis: int = axis,
            selected_adjacency: dict[FaceNode, set[FaceNode]] = adjacent,
        ) -> bool:
            return (
                b in selected_adjacency[a]
                and abs(
                    graph.bounds(a)[selected_axis][0]
                    - graph.bounds(b)[selected_axis][0]
                )
                <= SPAN_EPS
                and abs(
                    graph.bounds(a)[selected_axis][1]
                    - graph.bounds(b)[selected_axis][1]
                )
                <= SPAN_EPS
            )

        spans = tuple(connected_components(walls, shares_span))
        if not spans:
            attempts.append(_failed(1, axis=axis, eligible_walls=len(walls)))
            continue
        attempts.extend(
            _probe_span_component(part, graph, span, axis, len(walls)) for span in spans
        )
    return max(
        attempts,
        key=lambda probe: (probe.stage, probe.span_members, probe.eligible_walls),
    )


def _accepted_evidence(product: Any) -> tuple[frozenset[FaceNode], ...]:
    result = []
    for family in FamilyId:
        if family is FamilyId.LEGACY:
            continue
        for disposition in product.reconciliation.for_family(family):
            if disposition.outcome is Outcome.ACCEPTED:
                candidate = disposition.candidate
                result.append(
                    product.evidence.defining_of(candidate)
                    | product.evidence.constituent_of(candidate)
                )
    return tuple(result)


def _overlap(component: frozenset[FaceNode], proposals: tuple[frozenset[FaceNode], ...]) -> int:
    return max((len(component & proposal) for proposal in proposals), default=0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--class-id", type=int, default=15)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    from build123d import import_step

    paths = sorted(args.root.glob("*.st*p"))[: args.limit]
    if not paths:
        parser.error("the selected workload contains no STEP files")
    rows = []
    sources = []
    for path in paths:
        truth = load_mfcadpp_truth(path)
        sources.append((truth.model_id, truth.source_sha256))
        labelled = {
            index for index, class_id in enumerate(truth.semantic) if class_id == args.class_id
        }
        if not labelled:
            continue
        part = import_step(path)
        faces = tuple(part.faces())
        if len(faces) != len(truth.semantic):
            raise RuntimeError(f"{truth.model_id}: imported face count does not match labels")
        product = _take_inventory(part)
        graph = product.context.graph
        components = _components(graph, {graph.require_node(faces[index]) for index in labelled})
        accepted = _accepted_evidence(product)
        ring_proposals = tuple(
            frozenset((*ring.nodes, *ring.cap_nodes[0], *ring.cap_nodes[1]))
            for ring in rings(part, graph)
        )
        solids = list(part.solids()) or [part]
        pocket_proposals = tuple(
            proposal.planar
            | proposal.floors
            | frozenset(node for group in proposal.caps for node in group)
            for solid in solids
            for proposal in _pocket_proposals_one(solid, graph=graph)
        )
        for ordinal, component in enumerate(components):
            covered = set().union(*(component & evidence for evidence in accepted))
            if covered:
                continue
            probe = _probe_component(part, graph, component)
            degrees = Counter(
                len(set(graph.neighbours(node)) & set(component)) for node in component
            )
            surfaces = Counter(str(graph.surface(node)).rsplit(".", 1)[-1] for node in component)
            rows.append(
                {
                    "model_id": truth.model_id,
                    "ordinal": ordinal,
                    "faces": len(component),
                    "source_sha256": truth.source_sha256,
                    "surfaces": dict(sorted(surfaces.items())),
                    "internal_degrees": {str(key): value for key, value in sorted(degrees.items())},
                    "one_valid_solid": graph.common_valid_solid(component) is not None,
                    "ring_overlap_faces": _overlap(component, ring_proposals),
                    "pocket_overlap_faces": _overlap(component, pocket_proposals),
                    "ring_probe": asdict(probe),
                }
            )
    gates = Counter(row["ring_probe"]["first_failed_gate"] for row in rows)
    report = {
        "format": "b123d-recognisers-mfcadpp-prismatic-pocket-gap-audit",
        "format_version": 1,
        "implementation_commit": _commit(),
        "dataset_version": _PUBLISHED_VERSION,
        "class_id": args.class_id,
        "component_derivation": "same-label original faces connected by shared-edge adjacency",
        "native_instance_labels": False,
        "selection": {
            "limit": args.limit,
            "selected_ids_sha256": _selection_hash([path.stem for path in paths]),
            "selected_sources_sha256": _source_selection_hash(sources),
        },
        "untouched_components": len(rows),
        "untouched_faces": sum(row["faces"] for row in rows),
        "first_failed_gates": dict(sorted(gates.items())),
        "global_ring_overlaps": sum(row["ring_overlap_faces"] > 0 for row in rows),
        "global_pocket_overlaps": sum(row["pocket_overlap_faces"] > 0 for row in rows),
        "rows": rows,
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
