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
import math
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from build123d import Compound, Shape  # noqa: E402
from OCP.BRepAdaptor import BRepAdaptor_Surface  # noqa: E402
from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform  # noqa: E402
from OCP.BRepGProp import BRepGProp  # noqa: E402
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane  # noqa: E402
from OCP.gp import gp_Trsf  # noqa: E402
from OCP.GProp import GProp_GProps  # noqa: E402

from tests.golden._common import load_fixture  # noqa: E402
from tools.rigid_motion_sweep import ROTATIONS, _match, _occurrences  # noqa: E402

GOLDEN_ROOT = ROOT / "tests" / "golden"

Vector3 = tuple[float, float, float]


@dataclass(frozen=True, slots=True)
class InferredFrame:
    """Right-handed world-to-local rotation, with evidence useful for diagnosis."""

    axes: tuple[Vector3, Vector3, Vector3]
    support_areas: tuple[float, float]


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _cross(left: Vector3, right: Vector3) -> Vector3:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _unit(vector: Sequence[float]) -> Vector3:
    norm = math.hypot(*vector)
    if norm <= 1e-12:
        raise ValueError("frame direction is degenerate")
    return tuple(float(value) / norm for value in vector)  # type: ignore[return-value]


def _clean(vector: Vector3) -> Vector3:
    """Remove transform-generated final-bit noise at exact cardinal components."""

    return tuple(
        0.0
        if abs(value) <= 1e-12
        else math.copysign(1.0, value)
        if abs(abs(value) - 1.0) <= 1e-12
        else value
        for value in vector
    )  # type: ignore[return-value]


def _canonical_sign(vector: Vector3) -> Vector3:
    """Choose one representative of an unoriented line; sign cannot change recognition."""

    pivot = max(range(3), key=lambda index: (abs(vector[index]), index))
    sign = -1.0 if vector[pivot] < 0.0 else 1.0
    return tuple(sign * value for value in vector)  # type: ignore[return-value]


def infer_frame(part, *, parallel_cos: float = 0.999) -> InferredFrame:
    """Infer two dominant perpendicular analytic direction classes from ``part``.

    Planar normals contribute their face area.  Cylinder axes are admitted with their lateral
    area so a prismatic/turned mixture need not manufacture a world direction.  Direction signs
    are ignored while clustering because the two material sides of a slab establish one axis.
    """

    classes: list[tuple[Vector3, float]] = []
    for face in part.faces():
        surface = BRepAdaptor_Surface(face.wrapped)
        kind = surface.GetType()
        if kind == GeomAbs_Plane:
            raw = tuple(float(value) for value in face.normal_at())
        elif kind == GeomAbs_Cylinder:
            raw = tuple(float(value) for value in surface.Cylinder().Axis().Direction().Coord())
        else:
            continue
        direction = _canonical_sign(_unit(raw))
        props = GProp_GProps()
        BRepGProp.SurfaceProperties_s(face.wrapped, props)
        area = float(props.Mass())
        for index, (existing, support) in enumerate(classes):
            if abs(_dot(direction, existing)) >= parallel_cos:
                classes[index] = (existing, support + area)
                break
        else:
            classes.append((direction, area))

    ranked = sorted(classes, key=lambda item: (-item[1], item[0]))
    for first_index, (first, first_area) in enumerate(ranked):
        for second, second_area in ranked[first_index + 1 :]:
            if abs(_dot(first, second)) > 1.0 - parallel_cos:
                continue
            # Remove small modelling skew before constructing the right-handed third axis.
            orthogonal = _unit(tuple(second[i] - _dot(first, second) * first[i] for i in range(3)))
            first = _clean(first)
            orthogonal = _clean(orthogonal)
            third = _clean(_unit(_cross(first, orthogonal)))
            return InferredFrame((first, orthogonal, third), (first_area, second_area))
    if ranked:
        # A surface of revolution has one geometrically meaningful direction.  Roll about it
        # is unobservable, so a stable world seed is merely a gauge and cannot change the solid.
        first, first_area = ranked[0]
        seed = min(
            ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
            key=lambda candidate: abs(_dot(first, candidate)),
        )
        orthogonal = _unit(
            tuple(seed[index] - _dot(first, seed) * first[index] for index in range(3))
        )
        first = _clean(first)
        orthogonal = _clean(orthogonal)
        third = _clean(_unit(_cross(first, orthogonal)))
        return InferredFrame((first, orthogonal, third), (first_area, 0.0))
    raise ValueError("part does not expose two independent analytic direction classes")


def normalize_part(part) -> tuple[Shape, InferredFrame]:
    """Return a copied part rotated from its inferred world frame into local XYZ."""

    frame = infer_frame(part)
    transform = gp_Trsf()
    values = tuple(component for axis in frame.axes for component in axis)
    transform.SetValues(
        values[0],
        values[1],
        values[2],
        0.0,
        values[3],
        values[4],
        values[5],
        0.0,
        values[6],
        values[7],
        values[8],
        0.0,
    )
    # Transform each source solid independently, then reassemble the aggregate. Transforming a
    # complete multi-solid Compound lets OCCT rebuild face-to-solid ancestry differently on macOS,
    # making opposite Plate role groups appear to belong to different bodies.
    transformed = tuple(
        Compound.cast(BRepBuilderAPI_Transform(solid.wrapped, transform, True).Shape())
        for solid in part.solids()
    )
    if not transformed:
        raise ValueError("part has no solids")
    return Compound(transformed), frame


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
            try:
                rotated = part.rotate(rotation.axis, rotation.degrees)
                normalized_rotated, _rotated_frame = normalize_part(rotated)
                occurrences = _occurrences(normalized_rotated)
            except Exception as exc:
                raise RuntimeError(
                    f"golden {fixture!r} failed after {rotation.name} normalization"
                ) from exc
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
