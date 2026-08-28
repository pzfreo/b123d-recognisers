# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from build123d import Box, Cylinder, Part, export_step
from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._effective_surfaces import (
    AnalyticSurfaceFact,
    EffectiveSurfaceIndex,
    SurfaceProvenance,
)
from tools.nurbs_dataset_spike import (
    Candidate,
    _count_declarations,
    _counterfactual_binding,
    _measure_counterfactual,
    discover,
    markdown,
    measure,
    publication_report,
    uniform_sample,
)


def test_declaration_count_handles_a_chunk_boundary_without_double_counting() -> None:
    token = b"B_SPLINE_SURFACE_WITH_KNOTS("
    payload = b"B_SPLINE_SURFACE(" + b" " * (1024 * 1024 - 30) + token

    assert _count_declarations(io.BytesIO(payload)) == 2


def test_discovery_and_uniform_sample_are_archive_order_independent(tmp_path: Path) -> None:
    archive_path = tmp_path / "corpus.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("z.step", "#1=B_SPLINE_SURFACE(1,1,());")
        archive.writestr("notes.txt", "B_SPLINE_SURFACE(")
        archive.writestr("a.STP", "#1=PLANE('');")
        archive.writestr("m.step", "#1=B_SPLINE_SURFACE_WITH_KNOTS((2,2));")

    with zipfile.ZipFile(archive_path) as archive:
        candidates, step_files = discover(archive)

    assert step_files == 3
    assert [candidate.name for candidate in candidates] == ["m.step", "z.step"]
    population = [Candidate(str(index), 1, 1) for index in range(10)]
    assert [candidate.name for candidate in uniform_sample(population, 3)] == ["0", "4", "9"]


def test_measure_recovers_exact_converted_planes_and_reads_segmentation(tmp_path: Path) -> None:
    converted = Part(BRepBuilderAPI_NurbsConvert(Box(10, 8, 4).wrapped, True).Shape())
    step_path = tmp_path / "converted.step"
    assert export_step(converted, step_path)
    archive_path = tmp_path / "fusion.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(step_path, "s2/breps/step/converted.step")
        archive.writestr("s2/breps/seg/converted.seg", "\n".join("0" for _ in converted.faces()))
        archive.writestr("s2/segment_names.json", '["ExtrudeSide"]')

    report = measure(archive_path, max_models=1, progress_every=0)

    assert report["selection"]["method"] == (
        "evenly spaced indices over sorted B-spline-bearing STEP entries"
    )
    assert report["selection"]["step_files"] == 1
    assert report["selection"]["bspline_bearing_step_files"] == 1
    assert report["selection"]["selected_models"] == 1
    assert report["selection"]["segmentation_label_names"] == ["ExtrudeSide"]
    assert report["totals"]["bspline_faces"] == 6
    assert report["totals"]["recovered_by_primitive"] == {"plane": 6}
    assert report["totals"]["refused_faces"] == 0
    assert report["totals"]["segmentation_face_count_matches"] == 1
    assert report["totals"]["label_outcomes"] == {"ExtrudeSide:recovered-plane": 6}
    plane = report["feature_counterfactual"]["orchestrations"]["prismatic"]["scenarios"]["plane"]
    assert plane["eligible_models"] == 1
    assert plane["completed_models"] == 1
    assert plane["exposed_faces"] == 6
    rendered = markdown(report)
    assert "6/6 spline faces" in rendered
    assert "Feature-unlock counterfactual" in rendered
    assert "does not by\nitself justify blanket family migration" in rendered
    published = publication_report(report)
    assert "models" not in published
    assert "failed_entries" not in published
    assert published["totals"] == report["totals"]
    assert published["feature_counterfactual"] == report["feature_counterfactual"]


def test_counterfactual_measures_features_unlocked_by_recovered_surfaces() -> None:
    converted = Part(BRepBuilderAPI_NurbsConvert(Cylinder(5, 10).wrapped, True).Shape())
    graph = FaceGraph(converted)
    surfaces = EffectiveSurfaceIndex(graph)
    bindings = []
    for node in graph.nodes:
        fact = surfaces.fact(node)
        if isinstance(fact, AnalyticSurfaceFact) and fact.provenance is SurfaceProvenance.RECOVERED:
            bindings.append(_counterfactual_binding(graph.face(node), fact))

    measured = _measure_counterfactual(converted, bindings)

    assert measured["baseline_counts"]["external_cylinder_patches"] == 0
    assert measured["scenarios"]["cylinder"]["delta"] == {
        "external_cylinder_patches": 1,
        "bosses": 1,
    }
    assert measured["scenarios"]["combined"]["delta"] == {
        "external_cylinder_patches": 1,
        "bosses": 1,
    }
