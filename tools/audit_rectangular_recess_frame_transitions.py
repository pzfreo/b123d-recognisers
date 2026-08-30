"""Classify the residual E2 Pocket/Slot raw-to-framed transitions by defining faces.

MFCAD++ is open development evidence. This tool does not infer truth from its labels: it asks
whether each unmatched accepted occurrence is principal in only the caller presentation or only
the inferred part frame. Face indices are run-local handles, but rigid ``TopLoc`` normalization
preserves their one-to-one topology within this measurement.
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from build123d import import_step  # noqa: E402

from b123d_recognisers._adjacency import FaceGraph  # noqa: E402
from b123d_recognisers._recess_records import Pocket, Slot  # noqa: E402
from b123d_recognisers._recess_reduce import _region_center  # noqa: E402
from b123d_recognisers.frames import (  # noqa: E402
    RefusedPartFrame,
    _normalize_part,
    infer_part_frame,
)
from tools.rigid_motion_sweep import _match, _occurrences  # noqa: E402

_TARGETS = frozenset(("pocket", "slot"))
_AXIS_TOL = 1e-3


def _commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _selection_hash(paths: list[Path]) -> str:
    return hashlib.sha256("".join(f"{path.stem}\n" for path in paths).encode()).hexdigest()


def _principal_axes(graph: FaceGraph, indices: frozenset[int]) -> list[str | None]:
    axes = []
    for index in sorted(indices):
        node = graph.nodes[index]
        normal = graph.normal(node) if graph.is_planar(node) else None
        axis = None
        if normal is not None:
            components = tuple(abs(component) for component in normal)
            for index, (candidate, component) in enumerate(
                zip("xyz", components, strict=True)
            ):
                if abs(component - 1.0) <= _AXIS_TOL and all(
                    other <= _AXIS_TOL
                    for other_index, other in enumerate(components)
                    if other_index != index
                ):
                    axis = candidate
                    break
        axes.append(axis)
    return axes


def _same_region_pocket(record: object, records: tuple[object, ...]) -> bool:
    if not isinstance(record, Slot):
        return False
    centre = _region_center(record)
    return any(
        isinstance(other, Pocket)
        and sum(
            (left - right) ** 2
            for left, right in zip(centre, _region_center(other), strict=True)
        )
        ** 0.5
        <= 1e-3
        for other in records
    )


def _detail(
    *,
    file: str,
    direction: str,
    family: str,
    faces: frozenset[int],
    source_record: object,
    source_records: tuple[object, ...],
    raw_graph: FaceGraph,
    framed_graph: FaceGraph,
) -> dict[str, Any]:
    raw_axes = _principal_axes(raw_graph, faces)
    framed_axes = _principal_axes(framed_graph, faces)
    source_axes, other_axes = (
        (raw_axes, framed_axes) if direction == "absent" else (framed_axes, raw_axes)
    )
    if _same_region_pocket(source_record, source_records):
        reason = "alternate_projection_of_blind_pocket"
    elif source_axes and all(axis is not None for axis in source_axes) and any(
        axis is None for axis in other_axes
    ):
        reason = "principal_only_in_accepting_presentation"
    elif any(axis is None for axis in source_axes):
        reason = "internally_oblique_defining_evidence"
    else:
        reason = "unclassified"
    return {
        "file": file,
        "direction": direction,
        "family": family,
        "defining_face_indices": sorted(faces),
        "raw_principal_axes": raw_axes,
        "framed_principal_axes": framed_axes,
        "reason": reason,
    }


def audit(root: Path, *, limit: int = 500) -> dict[str, Any]:
    paths = sorted(root.glob("*.step"), key=lambda path: path.name)[:limit]
    if len(paths) < limit:
        raise ValueError(f"requested {limit} models but only {len(paths)} STEP files exist")
    details: list[dict[str, Any]] = []
    refused: list[dict[str, str]] = []
    for path in paths:
        part = import_step(path)
        frame = infer_part_frame(part)
        if isinstance(frame, RefusedPartFrame):
            refused.append({"file": path.name, "reason": frame.reason.value})
            continue
        framed = _normalize_part(part, frame)
        raw_faces = part.faces()
        framed_faces = framed.faces()
        if len(raw_faces) != len(framed_faces):
            raise RuntimeError(f"{path.name}: normalization changed face count")
        raw = _occurrences(part)
        local = _occurrences(framed)
        _pairs, absent, introduced = _match(raw, local)
        if not any(raw[index].family in _TARGETS for index in absent) and not any(
            local[index].family in _TARGETS for index in introduced
        ):
            continue
        raw_graph = FaceGraph(part)
        framed_graph = FaceGraph(framed)
        for direction, inventory, indices in (
            ("absent", raw, absent),
            ("introduced", local, introduced),
        ):
            for index in indices:
                occurrence = inventory[index]
                if occurrence.family not in _TARGETS:
                    continue
                details.append(
                    _detail(
                        file=path.name,
                        direction=direction,
                        family=occurrence.family,
                        faces=occurrence.defining_faces,
                        source_record=occurrence.record,
                        source_records=tuple(item.record for item in inventory),
                        raw_graph=raw_graph,
                        framed_graph=framed_graph,
                    )
                )
    counts = Counter(
        f"{detail['direction']}:{detail['family']}:{detail['reason']}" for detail in details
    )
    return {
        "schema": 1,
        "implementation_commit": _commit(),
        "dataset": "MFCAD++ published test split (development evidence)",
        "selection": f"first {limit} STEP filenames, lexical ascending",
        "selected_ids_sha256": _selection_hash(paths),
        "axis_alignment_tolerance": _AXIS_TOL,
        "matching": "one-to-one defining-face containment after topology-preserving normalization",
        "counts": dict(sorted(counts.items())),
        "transitions": details,
        "refused": refused,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(audit(args.root, limit=args.limit), indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
