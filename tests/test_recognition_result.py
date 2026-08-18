# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

import json
import math
from dataclasses import FrozenInstanceError, replace

import pytest
from build123d import Align, Box, Cylinder, Pos

from b123d_recognisers import (
    STEP_LADDER_BOUNDARY_MARGIN,
    FaceLevel,
    RecognitionResult,
    TurnedStep,
    build_recognition_result,
)


def _plate_with_holes():
    plate = Box(60, 40, 8)
    return plate - Pos(-15, 0, 0) * Cylinder(3, 8) - Pos(15, 0, 0) * Cylinder(3, 8)


def test_recognition_result_is_frozen_and_owns_tuple_inventories():
    result = build_recognition_result(_plate_with_holes())

    assert isinstance(result, RecognitionResult)
    assert len(result.holes) == 2
    assert all(
        isinstance(value, tuple)
        for value in result.__dict__.values()
        if not isinstance(value, bool)
    )
    with pytest.raises(FrozenInstanceError):
        result.holes = ()


def test_orchestrator_injects_each_shared_dependency_once(monkeypatch):
    import b123d_recognisers.result as result_module

    calls: dict[str, int] = {}
    cylinders = ([{"axis": "z"}], [{"axis": "x"}])
    countersinks = [object()]
    holes = [object()]
    slots = [object()]
    pockets = [object()]

    def counted(name, returns):
        def fake(part, **kwargs):
            calls[name] = calls.get(name, 0) + 1
            return returns

        return fake

    def cyl_consumer(name, returns):
        def fake(part, *, cyls=None, **kwargs):
            calls[name] = calls.get(name, 0) + 1
            assert cyls[0] is cylinders[0] and cyls[1] is cylinders[1]
            return returns

        return fake

    def derived(name, source, returns):
        def fake(records):
            calls[name] = calls.get(name, 0) + 1
            assert records is source
            return returns

        return fake

    def fake_cylinders(part):
        calls["cylinders"] = calls.get("cylinders", 0) + 1
        return cylinders

    def fake_holes(part, *, cyls=None, csinks=None):
        calls["holes"] = calls.get("holes", 0) + 1
        assert cyls[0] is cylinders[0] and cyls[1] is cylinders[1]
        assert csinks is countersinks
        return holes

    monkeypatch.setattr(result_module, "analyse_cylinders", fake_cylinders)
    monkeypatch.setattr(
        result_module, "recognise_countersinks", counted("countersinks", countersinks)
    )
    monkeypatch.setattr(result_module, "recognise_holes", fake_holes)
    monkeypatch.setattr(result_module, "recognise_double_d_bores", counted("double_d_bores", []))
    monkeypatch.setattr(result_module, "recognise_hole_patterns", derived("patterns", holes, []))
    monkeypatch.setattr(result_module, "recognise_bosses", cyl_consumer("bosses", []))
    monkeypatch.setattr(
        result_module, "recognise_polygonal_bosses", counted("polygonal_bosses", [])
    )
    monkeypatch.setattr(result_module, "recognise_polygonal_stock", counted("polygonal_stock", []))
    monkeypatch.setattr(result_module, "recognise_channels", counted("channels", []))
    monkeypatch.setattr(result_module, "recognise_slots", counted("slots", slots))
    monkeypatch.setattr(
        result_module, "recognise_slot_patterns", derived("slot_patterns", slots, [])
    )
    monkeypatch.setattr(result_module, "recognise_grooves", cyl_consumer("grooves", []))
    monkeypatch.setattr(result_module, "recognise_flats", cyl_consumer("flats", []))
    monkeypatch.setattr(result_module, "recognise_pockets", counted("pockets", pockets))
    monkeypatch.setattr(
        result_module, "recognise_pocket_patterns", derived("pocket_patterns", pockets, [])
    )
    monkeypatch.setattr(result_module, "recognise_rectangular_pads", counted("pads", []))
    monkeypatch.setattr(
        result_module, "recognise_repeating_radial_profiles", counted("radial_profiles", [])
    )
    monkeypatch.setattr(result_module, "recognise_turned_steps", cyl_consumer("turned_steps", []))
    levels = [FaceLevel(4.0, (0.0, 8.0), (0.0, 6.0)), FaceLevel(9.0)]
    monkeypatch.setattr(result_module, "step_level_records", counted("step_levels", levels))
    monkeypatch.setattr(result_module, "recognise_risers", counted("risers", []))
    monkeypatch.setattr(result_module, "recognise_chamfers", counted("chamfers", []))
    monkeypatch.setattr(result_module, "recognise_angled_steps", counted("angled_steps", []))
    # The orchestrator no longer calls `recognise_passages` itself: a through slot is also a
    # passage, and the rule that decides between them belongs outside both recognisers, so what
    # this layer injects is the reconciler and the ledger the slots were written into.
    def fake_passages(part, ledger):
        calls["passages"] = calls.get("passages", 0) + 1
        assert ledger is not None
        return []

    monkeypatch.setattr(result_module, "passages_that_are_not_slots", fake_passages)
    monkeypatch.setattr(result_module, "recognise_fillets", counted("fillets", []))
    monkeypatch.setattr(result_module, "recognise_plates", counted("plates", []))

    # A part rather than a bare object: the orchestrator now builds one face graph for the
    # families that record which faces they were built from, and an empty inventory is all this
    # test needs -- every recogniser that would read it is replaced above.
    class _Part:
        def faces(self):
            return []

    built = result_module.build_recognition_result(_Part())

    expected = {
        "angled_steps",
        "passages",
        "cylinders",
        "countersinks",
        "holes",
        "double_d_bores",
        "patterns",
        "bosses",
        "polygonal_bosses",
        "polygonal_stock",
        "channels",
        "slots",
        "slot_patterns",
        "grooves",
        "flats",
        "pockets",
        "pocket_patterns",
        "pads",
        "radial_profiles",
        "turned_steps",
        "step_levels",
        "risers",
        "chamfers",
        "fillets",
        "plates",
    }
    assert set(calls) == expected
    assert set(calls.values()) == {1}
    assert built.holes == tuple(holes)
    assert built.step_levels == tuple(levels)
    assert built.step_ladder_for_z_span(0.0, 10.0) == [4.0, 9.0]


def test_supplied_cylinder_inventory_is_not_rediscovered(monkeypatch):
    import b123d_recognisers.result as result_module

    cylinders = ([], [])

    def forbidden(part):
        raise AssertionError("supplied cylinder substrate was rediscovered")

    monkeypatch.setattr(result_module, "analyse_cylinders", forbidden)
    result = result_module.build_recognition_result(Box(10, 10, 10), cylinders=cylinders)
    assert result.cylinders == ((), ())


def _ladder_result(
    *, steps: tuple[TurnedStep, ...] = (), levels: tuple[FaceLevel, ...] = ()
) -> RecognitionResult:
    return replace(
        build_recognition_result(Box(10, 10, 10)),
        turned_steps=steps,
        step_levels=levels,
    )


def test_explicit_z_span_filters_only_interior_z_shoulders_at_the_named_margin() -> None:
    steps = tuple(
        TurnedStep("z", lo, hi, diameter)
        for lo, hi, diameter in (
            (0.0, 0.6, 10.0),
            (0.6, 1.2, 8.0),
            (1.2, 9.4, 12.0),
            (9.4, 10.0, 10.0),
        )
    )
    result = _ladder_result(steps=steps)

    assert STEP_LADDER_BOUNDARY_MARGIN == 0.6
    first = result.step_ladder_for_z_span(0.0, 10.0)
    second = result.step_ladder_for_z_span(0.0, 10.0)

    assert first == second == [1.2]
    assert all(type(value) is float for value in first)
    assert json.loads(json.dumps(first)) == [1.2]


def test_explicit_z_span_validates_bounds_margin_and_narrow_span_edges() -> None:
    result = _ladder_result(
        steps=(
            TurnedStep("z", 0.0, 1.0, 10.0),
            TurnedStep("z", 1.0, 2.0, 8.0),
        )
    )

    assert result.step_ladder_for_z_span(0.0, 2.0, boundary_margin=1.0) == []
    with pytest.raises(ValueError, match="z_min must not exceed z_max"):
        result.step_ladder_for_z_span(2.0, 1.0)
    for value in (math.nan, math.inf, -math.inf):
        with pytest.raises(ValueError, match="finite"):
            result.step_ladder_for_z_span(value, 2.0)
    for margin in (-0.1, math.nan, math.inf):
        with pytest.raises(ValueError, match="boundary_margin"):
            result.step_ladder_for_z_span(0.0, 2.0, boundary_margin=margin)


def test_non_z_or_prismatic_ladder_preserves_pre_filtered_face_levels() -> None:
    levels = (FaceLevel(4.0), FaceLevel(9.0))
    prismatic = _ladder_result(levels=levels)
    x_turned = _ladder_result(
        steps=(
            TurnedStep("x", 0.0, 4.0, 10.0),
            TurnedStep("x", 4.0, 10.0, 8.0),
        ),
        levels=levels,
    )

    assert prismatic.step_ladder_for_z_span(0.0, 10.0) == [4.0, 9.0]
    assert x_turned.step_ladder_for_z_span(0.0, 10.0) == [4.0, 9.0]


def test_build123d_bounds_call_is_compatible_but_deprecated_until_1_0() -> None:
    result = _ladder_result(
        steps=(
            TurnedStep("z", 0.0, 4.0, 10.0),
            TurnedStep("z", 4.0, 10.0, 8.0),
        )
    )
    bounds = Box(10, 10, 10, align=Align.MIN).bounding_box()

    with pytest.warns(DeprecationWarning, match=r"0\.2\.1.*no earlier than 1\.0\.0"):
        legacy = result.step_ladder(bounds)

    assert legacy == result.step_ladder_for_z_span(bounds.min.Z, bounds.max.Z) == [4.0]
