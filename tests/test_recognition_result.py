# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

from dataclasses import FrozenInstanceError
from types import SimpleNamespace

import pytest
from build123d import Box, Cylinder, Pos

from b123d_recognisers import FaceLevel, RecognitionResult, build_recognition_result


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
    monkeypatch.setattr(result_module, "recognise_fillets", counted("fillets", []))
    monkeypatch.setattr(result_module, "recognise_plates", counted("plates", []))

    built = result_module.build_recognition_result(object())

    expected = {
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
    bb = SimpleNamespace(min=SimpleNamespace(Z=0.0), max=SimpleNamespace(Z=10.0))
    assert built.step_ladder(bb) == [4.0, 9.0]


def test_supplied_cylinder_inventory_is_not_rediscovered(monkeypatch):
    import b123d_recognisers.result as result_module

    cylinders = ([], [])

    def forbidden(part):
        raise AssertionError("supplied cylinder substrate was rediscovered")

    monkeypatch.setattr(result_module, "analyse_cylinders", forbidden)
    result = result_module.build_recognition_result(Box(10, 10, 10), cylinders=cylinders)
    assert result.cylinders == ((), ())
