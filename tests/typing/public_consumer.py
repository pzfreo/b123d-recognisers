"""Strict external-consumer fixture, checked against the built wheel."""

from build123d import BoundBox, Face, Solid
from typing_extensions import assert_type

from b123d_recognisers import (
    BossRecord,
    HoleRecord,
    RecognitionResult,
    build_recognition_result,
    classify_bevel,
    feature_census,
    recognise_bosses,
    recognise_holes,
)


def consume(part: Solid, face: Face, bounds: BoundBox) -> None:
    holes = recognise_holes(part)
    bosses = recognise_bosses(part)
    result = build_recognition_result(part)

    assert_type(holes, list[HoleRecord])
    assert_type(bosses, list[BossRecord])
    assert_type(result, RecognitionResult)
    assert_type(result.holes, tuple[HoleRecord, ...])
    assert_type(result.bosses, tuple[BossRecord, ...])
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
