from __future__ import annotations

from build123d import Align, Axis, Box, Pos

from tools import benchmark_plate_area_authority as benchmark


def _rolled_plate():
    align = (Align.CENTER, Align.CENTER, Align.MIN)
    part = Box(40, 10, 4, align=align) + Pos(0, 7, 4) * Box(1, 14, 20, align=align)
    return part.rotate(Axis.Z, 37)


def test_paired_measurement_isolated_the_oriented_plate_transition() -> None:
    report = benchmark._measure([("rolled", _rolled_plate())])

    assert report["all_other_outputs_equal"] is True
    assert report["all_legacy_records_retained"] is True
    assert report["legacy_plates"] == 0
    assert report["oriented_plates"] == report["introduced_plates"] == 1
    assert report["models"][0]["introduced"][0]["axis"] == "z"


def test_acceptance_requires_parity_retention_and_bounded_runtime() -> None:
    report = {
        "all_other_outputs_equal": True,
        "all_legacy_records_retained": True,
        "oriented_to_legacy_total_ratio": 1.10,
    }
    assert benchmark._acceptable(report)
    for key in tuple(report):
        broken = dict(report)
        broken[key] = 1.100001 if key.endswith("ratio") else False
        assert not benchmark._acceptable(broken)
