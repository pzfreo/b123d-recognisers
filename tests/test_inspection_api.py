"""Independent contract tests for the supported F7 inspection API."""

from __future__ import annotations

import copy
import dataclasses
import importlib
import inspect
import json
import subprocess
import sys
import typing
from enum import Enum
from pathlib import Path

import pytest
from build123d import Cylinder, GeomType, Torus, Vertex

import b123d_recognisers as recognition
import b123d_recognisers.experimental_geometry as experimental
import b123d_recognisers.inspection as inspection

ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "src" / "b123d_recognisers" / "inspection_api.json"

EXPECTED_KINDS = {
    "AnalyticSurface": "dataclass",
    "BevelReject": "exception",
    "FaceInspection": "dataclass",
    "OrientationCapability": "enum",
    "RefusedSurface": "dataclass",
    "SurfaceFact": "type-alias",
    "SurfaceKind": "enum",
    "SurfaceProvenance": "enum",
    "SurfaceRefusalReason": "enum",
    "classify_bevel": "function",
    "cone_rims": "function",
    "floor_face_anchor": "function",
    "inspect_face": "function",
    "read_double_d_tool": "function",
}


def _symbols() -> list[dict[str, object]]:
    manifest = inspection.inspection_api_manifest()
    return typing.cast(list[dict[str, object]], manifest["api"]["symbols"])


def _resolve(qualified_name: str) -> object:
    module_name, _, name = qualified_name.rpartition(".")
    return getattr(importlib.import_module(module_name), name)


def test_manifest_query_is_deterministic_isolated_and_separately_versioned() -> None:
    first = inspection.inspection_api_manifest()
    expected = json.loads(MANIFEST.read_text(encoding="utf-8"))

    assert first == inspection.inspection_api_manifest() == expected
    assert inspection.inspection_api_manifest_json() == MANIFEST.read_text(encoding="utf-8")
    assert first["format"] == inspection.INSPECTION_API_FORMAT
    assert first["format_version"] == inspection.INSPECTION_API_FORMAT_VERSION
    assert first["package"] == {
        "name": "b123d-recognisers",
        "version": recognition.__version__,
    }
    assert "inspection" not in recognition.capability_manifest()
    typing.cast(dict[str, object], first["api"])["symbols"] = []
    assert _symbols(), "callers must not mutate the installed contract"
    with pytest.raises(inspection.InspectionApiManifestError, match="unsupported requested"):
        inspection.inspection_api_manifest(format_version=2)
    with pytest.raises(inspection.InspectionApiManifestError, match="unsupported requested"):
        inspection.inspection_api_manifest_json(format_version=2)
    with pytest.raises(inspection.InspectionApiManifestError, match="unsupported requested"):
        inspection.inspection_api_manifest(format_version=True)


def test_manifest_roster_and_runtime_contracts_are_derived_independently() -> None:
    declared = {typing.cast(str, item["name"]): item for item in _symbols()}
    assert {name: item["kind"] for name, item in declared.items()} == EXPECTED_KINDS

    for name, kind in EXPECTED_KINDS.items():
        value = getattr(inspection, name)
        contract = typing.cast(dict[str, object], declared[name]["contract"])
        if kind == "dataclass":
            assert contract == {"fields": [field.name for field in dataclasses.fields(value)]}
        elif kind == "enum":
            assert inspect.isclass(value) and issubclass(value, Enum)
            assert contract == {"values": [member.value for member in value]}
        elif kind == "exception":
            assert inspect.isclass(value) and issubclass(value, ValueError)
            assert contract == {"base": "ValueError"}
        elif kind == "function":
            assert contract == {"signature": str(inspect.signature(value))}
        else:
            assert kind == "type-alias"
            assert set(typing.get_args(value)) == {
                inspection.AnalyticSurface,
                inspection.RefusedSurface,
            }
            assert contract == {"definition": "AnalyticSurface|RefusedSurface"}


def test_every_manifested_compatibility_alias_preserves_exact_identity() -> None:
    for symbol in _symbols():
        primary = _resolve(typing.cast(str, symbol["qualified_name"]))
        assert primary is getattr(inspection, typing.cast(str, symbol["name"]))
        for alias in typing.cast(list[str], symbol["aliases"]):
            assert _resolve(alias) is primary, alias


def test_only_standalone_inspection_graduated_from_the_experimental_facade() -> None:
    for name in (
        "AnalyticSurface",
        "FaceInspection",
        "OrientationCapability",
        "RefusedSurface",
        "SurfaceFact",
        "SurfaceKind",
        "SurfaceProvenance",
        "SurfaceRefusalReason",
        "inspect_face",
    ):
        assert getattr(experimental, name) is getattr(inspection, name)

    assert not hasattr(inspection, "GeometryGraph")
    assert not hasattr(recognition, "GeometryGraph")
    assert "GeometryGraph" not in inspection.__all__


def test_stable_inspect_face_returns_native_fact_anchor_and_closed_refusal() -> None:
    cylinder = Cylinder(8, 20).faces().filter_by(GeomType.CYLINDER)[0]
    inspected = inspection.inspect_face(cylinder)

    assert isinstance(inspected.surface, inspection.AnalyticSurface)
    assert inspected.surface.kind is inspection.SurfaceKind.CYLINDER
    assert inspected.surface.provenance is inspection.SurfaceProvenance.NATIVE
    assert inspected.surface.parameters[6] == pytest.approx(8)
    assert inspected.anchor is not None
    assert Vertex(*inspected.anchor).distance_to(cylinder) < 1e-7

    refused = inspection.inspect_face(Torus(8, 2).faces()[0])
    assert isinstance(refused.surface, inspection.RefusedSurface)
    assert refused.surface.reason in set(inspection.SurfaceRefusalReason)


def test_committed_manifest_is_the_deterministic_generator_output() -> None:
    subprocess.run(
        [sys.executable, "tools/generate_inspection_api_manifest.py", "--check"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value.clear(), "missing required"),
        (lambda value: value.update({"future": 1}), "unknown fields"),
        (lambda value: value.update({"format": "other"}), "document kind"),
        (lambda value: value.update({"format_version": 2}), "format version"),
        (lambda value: value.update({"format_version": True}), "format version"),
        (lambda value: value.update({"package": None}), "package must be"),
        (lambda value: value["package"].pop("version"), "package identity"),
        (lambda value: value["package"].update({"name": "other"}), "package identity"),
        (lambda value: value["package"].update({"version": "next"}), "semantic"),
        (lambda value: value.update({"api": None}), "api must be"),
        (lambda value: value["api"].pop("major"), "missing required"),
        (lambda value: value["api"].update({"major": 2}), "API major"),
        (lambda value: value["api"].update({"major": True}), "API major"),
        (lambda value: value["api"].update({"namespace": "other"}), "namespace"),
        (lambda value: value["api"].update({"symbols": []}), "non-empty"),
        (lambda value: value["api"]["symbols"].__setitem__(0, None), "must be an object"),
        (lambda value: value["api"]["symbols"][0].pop("kind"), "missing required"),
        (lambda value: value["api"]["symbols"][0].update({"future": 1}), "unknown fields"),
        (lambda value: value["api"]["symbols"][0].update({"name": "not valid"}), "name"),
        (
            lambda value: value["api"]["symbols"][0].update({"qualified_name": "other"}),
            "qualified_name",
        ),
        (lambda value: value["api"]["symbols"][0].update({"kind": "record"}), "kind"),
        (lambda value: value["api"]["symbols"][0].update({"kind": []}), "kind"),
        (
            lambda value: value["api"]["symbols"][0].update({"introduced_in": "future"}),
            "semantic",
        ),
        (
            lambda value: value["api"]["symbols"][0].update({"introduced_in": "9.0.0"}),
            "introduced after",
        ),
        (lambda value: value["api"]["symbols"][0].update({"aliases": {}}), "aliases"),
        (
            lambda value: value["api"]["symbols"][0].update(
                {"aliases": ["b123d_recognisers.bad"] * 2}
            ),
            "aliases",
        ),
        (lambda value: value["api"]["symbols"][0].update({"contract": None}), "contract"),
        (
            lambda value: value["api"]["symbols"][0]["contract"].update({"future": 1}),
            "unknown fields",
        ),
        (
            lambda value: value["api"]["symbols"][0].update({"contract": {"fields": []}}),
            "contract values",
        ),
        (lambda value: value["api"]["symbols"].reverse(), "name-sorted"),
        (
            lambda value: value["api"]["symbols"].append(
                copy.deepcopy(value["api"]["symbols"][-1])
            ),
            "unique",
        ),
    ],
)
def test_validator_fails_closed_on_malformed_documents(mutate, message: str) -> None:
    manifest = inspection.inspection_api_manifest()
    mutate(manifest)
    with pytest.raises(inspection.InspectionApiManifestError, match=message):
        inspection.validate_inspection_api_manifest(manifest)


def test_validator_rejects_non_objects_and_invalid_scalar_contracts() -> None:
    with pytest.raises(inspection.InspectionApiManifestError, match="JSON object"):
        inspection.validate_inspection_api_manifest(None)

    manifest = inspection.inspection_api_manifest()
    function = next(item for item in manifest["api"]["symbols"] if item["kind"] == "function")
    function["contract"]["signature"] = ""
    with pytest.raises(inspection.InspectionApiManifestError, match="contract value"):
        inspection.validate_inspection_api_manifest(manifest)
