"""Contract tests for the paired principal-axis Pad benchmark."""

from build123d import Box, Pos, Rot

from tools.benchmark_pad_axes import _acceptable, _measure


def test_paired_counterfactual_retains_positive_z_and_finds_principal_pad() -> None:
    positive_z = Box(80, 60, 10) + Pos(0, 0, 7) * Box(30, 20, 4)
    positive_x = Rot(0, 90, 0) * positive_z

    report = _measure([("positive-z", positive_z), ("positive-x", positive_x)])

    assert report["all_other_outputs_equal"] is True
    assert report["all_legacy_records_retained"] is True
    assert report["legacy_positive_z_pads"] == 1
    assert report["principal_axis_pads"] == 2
    assert report["introduced_pads"] == 1
    assert report["models"][0]["introduced"] == []
    assert report["models"][1]["introduced"][0]["axis"] == "x"


def test_acceptance_gate_requires_legacy_retention() -> None:
    report = {
        "all_other_outputs_equal": True,
        "all_legacy_records_retained": False,
        "enabled_to_disabled_total_ratio": 1.0,
    }

    assert _acceptable(report) is False
