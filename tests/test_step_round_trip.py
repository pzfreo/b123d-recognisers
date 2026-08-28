# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""Recognition of geometry that has travelled through a STEP file.

The golden corpus builds its parts with build123d modelling operations, so nothing else in the
suite exercises the path the README actually advertises: a STEP file arriving from disk with no
construction history. These tests close that gap and pin its boundary.

Two things are proved here, and they are deliberately separate.

*Analytic surfaces survive.* Every fixture exported to STEP and re-imported produces the same
pinned canonical records as the constructed part. STEP carries planes, cylinders and cones as
analytic surface entities, and OCCT restores them as such, so the recognisers see what they saw
before. This is the case a CAD kernel that preserves analytic geometry delivers.

*B-spline support is family-specific.* Raised Pads now consume bounded effective-plane facts and a
separate material-side certificate. Every other family still classifies native surface types, so
the cylinder-based control below remains absent after conversion. The selected-family positive and
its exact evidence are pinned by ``test_nurbs_conversion_sweep.py`` and Pad adversaries.

These tests write STEP to a temporary directory. No STEP bytes are committed: per
``migration/PARITY.md`` the goldens compare semantic record projections, never file contents.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from build123d import Compound, Shape, Solid, export_step, import_step
from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
from OCP.GeomAbs import GeomAbs_SurfaceType
from OCP.TopAbs import TopAbs_ShapeEnum

import b123d_recognisers as recognition
from b123d_recognisers import feature_census

ROOT = Path(__file__).parents[1]
GOLDEN_ROOT = ROOT / "tests" / "golden"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from golden_support import canonicalize  # noqa: E402
from recognition_snapshot import recognition_snapshot  # noqa: E402

from tests.golden._common import load_fixture  # noqa: E402

CASES = sorted(GOLDEN_ROOT.glob("*/fixture.py"))


def _through_step(part, tmp_path: Path, name: str) -> Shape:
    """Export *part* to STEP and return what a consumer importing that file receives."""

    step_file = tmp_path / f"{name}.step"
    export_step(part, str(step_file))
    assert step_file.stat().st_size > 0, "export produced no STEP data"
    return import_step(str(step_file))


def _as_nurbs(part) -> Shape:
    """Re-express *part* with every surface as a B-spline, preserving its shape exactly.

    This is the condition a NURBS-only CAD export delivers: the geometry is unchanged and the
    faces are still exactly a cylinder and six planes, but none of them carries an analytic
    surface type any more.
    """

    converted = BRepBuilderAPI_NurbsConvert(part.wrapped, True).Shape()
    if converted.ShapeType() == TopAbs_ShapeEnum.TopAbs_SOLID:
        return Solid(converted)
    return Compound(converted)


def _surface_types(part) -> set[GeomAbs_SurfaceType]:
    return {BRepAdaptor_Surface(face.wrapped).GetType() for face in part.faces()}


@pytest.mark.parametrize("fixture_path", CASES, ids=lambda path: path.parent.name)
def test_step_round_trip_reproduces_the_pinned_golden(fixture_path, tmp_path):
    """A part read back from STEP recognises identically to the part that was built."""

    fixture = load_fixture(fixture_path)
    expected = json.loads(fixture_path.with_name("expected.json").read_text(encoding="utf-8"))

    imported = _through_step(fixture.build_fixture(), tmp_path, fixture_path.parent.name)
    actual = recognition_snapshot(recognition, feature_census, imported)

    assert canonicalize(actual) == expected["recognition"]


def test_step_round_trip_preserves_analytic_surface_types(tmp_path):
    """The round trip above is meaningful because STEP keeps planes and cylinders analytic."""

    part = load_fixture(GOLDEN_ROOT / "simple_through_hole" / "fixture.py").build_fixture()
    imported = _through_step(part, tmp_path, "surface_types")

    assert _surface_types(imported) == {
        GeomAbs_SurfaceType.GeomAbs_Plane,
        GeomAbs_SurfaceType.GeomAbs_Cylinder,
    }


def test_nurbs_only_cylinders_remain_outside_non_migrated_families(tmp_path):
    """Pad plane support does not silently unlock cylinder-dependent families."""

    part = load_fixture(GOLDEN_ROOT / "simple_through_hole" / "fixture.py").build_fixture()
    analytic_census = feature_census(part)
    assert analytic_census["hole"] == 1 and analytic_census["boss"] == 1

    nurbs = _through_step(_as_nurbs(part), tmp_path, "nurbs")

    assert _surface_types(nurbs) == {GeomAbs_SurfaceType.GeomAbs_BSplineSurface}
    assert set(feature_census(nurbs).values()) == {0}
