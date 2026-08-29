"""Strict external-consumer fixture, checked against the built wheel."""

from typing import Literal

from build123d import BoundBox, Edge, Face, Shape, Solid
from OCP.TopoDS import TopoDS_Shape
from typing_extensions import assert_type

from b123d_recognisers import (
    BossRecord,
    FramedRecognitionReport,
    FramedRecognitionResult,
    HoleRecord,
    PairedRampStep,
    RecognitionReport,
    RecognitionResult,
    build_framed_recognition_report,
    build_framed_recognition_result,
    build_raw_recognition_report,
    build_raw_recognition_result,
    build_recognition_report,
    build_recognition_result,
    classify_bevel,
    feature_census,
    recognise_bosses,
    recognise_holes,
    recognise_paired_ramp_steps,
)
from b123d_recognisers.inspection import (
    BevelReject,
    FaceInspection,
    cone_rims,
    floor_face_anchor,
    inspect_face,
    read_double_d_tool,
)


def consume_bevel_rejection(error: BevelReject) -> None:
    assert_type(
        error.reason,
        Literal["nonplanar", "degenerate", "aligned", "compound"],
    )


def consume(part: Solid, face: Face, bounds: BoundBox) -> None:
    holes = recognise_holes(part)
    bosses = recognise_bosses(part)
    paired_ramp_steps = recognise_paired_ramp_steps(part)
    result = build_recognition_result(part)
    report = build_recognition_report(part)
    raw_result = build_raw_recognition_result(part)
    raw_report = build_raw_recognition_report(part)

    assert_type(holes, list[HoleRecord])
    assert_type(bosses, list[BossRecord])
    assert_type(paired_ramp_steps, list[PairedRampStep])
    assert_type(result, RecognitionResult)
    assert_type(report, RecognitionReport)
    assert_type(report.result, RecognitionResult)
    assert_type(raw_result, RecognitionResult)
    assert_type(raw_report, RecognitionReport)
    assert_type(result.holes, tuple[HoleRecord, ...])
    assert_type(result.bosses, tuple[BossRecord, ...])
    assert_type(result.paired_ramp_steps, tuple[PairedRampStep, ...])
    framed = build_framed_recognition_result(part)
    if isinstance(framed, FramedRecognitionResult):
        assert_type(framed.part, Shape[TopoDS_Shape])
    framed_report = build_framed_recognition_report(part)
    if isinstance(framed_report, FramedRecognitionReport):
        assert_type(framed_report.part, Shape[TopoDS_Shape])
        assert_type(framed_report.report, RecognitionReport)
    assert_type(result.step_ladder_for_z_span(0.0, 10.0), list[float])
    assert_type(result.step_ladder(bounds), list[float])
    assert_type(feature_census(part), dict[str, int])
    assert_type(
        classify_bevel(face),
        tuple[
            int,
            tuple[float, float, float],
            dict[int, tuple[float, float]],
            float,
            float,
        ],
    )
    assert_type(inspect_face(face), FaceInspection)
    assert_type(cone_rims(face), tuple[Edge, Edge, float] | None)
    assert_type(floor_face_anchor(face), tuple[float, float, float])
    assert_type(
        read_double_d_tool(part),
        tuple[str, float, float, tuple[float, float, float], float, tuple[float, float, float]],
    )
