from __future__ import annotations

from build123d import Box, Compound, Pos

from b123d_recognisers import recognise_plates
from tools import benchmark_plate_body_locality as benchmark


def _bracket():
    return (Pos(0, 0, 5) * Box(80, 60, 10)) + (Pos(0, 0, 35) * Box(80, 10, 50))


def test_disabled_arm_recreates_only_the_whole_compound_plate_projection(monkeypatch) -> None:
    import b123d_recognisers.plates as plates

    part = Compound(children=[Pos(-70, 0, 0) * _bracket(), Pos(70, 0, 0) * _bracket()])
    body_local = recognise_plates(part)
    monkeypatch.setattr(plates, "_plate_scopes", lambda value: [value])
    legacy = recognise_plates(part)

    assert len(body_local) == 4
    assert len(legacy) == 2
    assert {record.u for record in body_local} == {-70.0, 70.0}
    assert {record.u for record in legacy} == {0.0}


def test_paired_measurement_preserves_non_plate_outputs_and_legacy_records() -> None:
    report = benchmark._measure([("single", _bracket())])

    assert report["all_other_outputs_equal"] is True
    assert report["all_legacy_records_retained"] is True
    assert report["legacy_plates"] == report["body_local_plates"] == 2


def test_acceptance_requires_parity_retention_and_bounded_runtime() -> None:
    report = {
        "all_other_outputs_equal": True,
        "all_legacy_records_retained": True,
        "body_local_to_legacy_total_ratio": 1.10,
    }
    assert benchmark._acceptable(report)
    for key in tuple(report):
        broken = dict(report)
        broken[key] = 1.100001 if key.endswith("ratio") else False
        assert not benchmark._acceptable(broken)
