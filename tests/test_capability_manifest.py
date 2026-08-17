"""Independent fail-closed checks for the ADR 0005 package capability contract."""

from __future__ import annotations

import copy
import dataclasses
import inspect
import json
import subprocess
import sys
import types
import typing
from pathlib import Path

import pytest
from build123d import Box

import b123d_recognisers as recognition
import b123d_recognisers.capabilities as capabilities_module
from b123d_recognisers import (
    CAPABILITY_FORMAT,
    CAPABILITY_FORMAT_VERSION,
    CapabilityManifestError,
    RecognitionResult,
    capability_manifest,
    capability_manifest_json,
    feature_census,
    validate_capability_manifest,
)
from b123d_recognisers._record import Record

ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "src" / "b123d_recognisers" / "capabilities.json"


def _families() -> list[dict]:
    return capability_manifest()["families"]


def _public_recognisers() -> set[str]:
    return {name for name in recognition.__all__ if name.startswith("recognise_")}


def _public_records() -> set[str]:
    return {
        name
        for name in recognition.__all__
        if inspect.isclass(candidate := getattr(recognition, name))
        and issubclass(candidate, Record)
        and candidate is not Record
    }


def _record_types(annotation: object) -> set[type[Record]]:
    if inspect.isclass(annotation) and issubclass(typing.cast(type, annotation), Record):
        return {typing.cast(type[Record], annotation)}
    return set().union(*(_record_types(arg) for arg in typing.get_args(annotation)), set())


def _type_name(annotation: object) -> str:
    if annotation is type(None):
        return "null"
    if annotation in {bool, int, float, str}:
        return typing.cast(type, annotation).__name__
    if inspect.isclass(annotation) and issubclass(typing.cast(type, annotation), Record):
        return f"record:{typing.cast(type, annotation).__name__}"
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin in {typing.Union, types.UnionType}:
        return "|".join(
            sorted({_type_name(arg) for arg in args}, key=lambda item: (item == "null", item))
        )
    if origin is tuple:
        if len(args) == 2 and args[1] is Ellipsis:
            return f"list[{_type_name(args[0])}]"
        rendered = [_type_name(arg) for arg in args]
        if len(set(rendered)) == 1:
            return f"tuple[{rendered[0]},{len(rendered)}]"
        union = "|".join(sorted({_type_name(arg) for arg in args}))
        return f"list[{union}]"
    raise TypeError(annotation)


def test_manifest_query_is_deterministic_isolated_and_versioned() -> None:
    first = capability_manifest()
    second = capability_manifest()

    assert first == second == json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert capability_manifest_json() == MANIFEST.read_text(encoding="utf-8")
    assert first["format"] == CAPABILITY_FORMAT
    assert first["format_version"] == CAPABILITY_FORMAT_VERSION
    assert first["package"] == {"name": "b123d-recognisers", "version": recognition.__version__}
    first["families"].clear()
    assert capability_manifest()["families"], "callers must not mutate the cached contract"
    with pytest.raises(CapabilityManifestError, match="unsupported requested"):
        capability_manifest(format_version=2)


def test_manifest_inventories_are_derived_independently_from_public_runtime() -> None:
    families = _families()
    manifest_recognisers = {
        item["entry_point"].removeprefix("b123d_recognisers.")
        for family in families
        for item in family["recognisers"]
    }
    manifest_records = {record["name"] for family in families for record in family["records"]}

    assert manifest_recognisers == _public_recognisers()
    assert manifest_records == _public_records()
    assert sum(len(family["recognisers"]) for family in families) == len(manifest_recognisers)
    assert sum(len(family["records"]) for family in families) == len(manifest_records)


def test_manifest_entry_kinds_and_record_returns_match_runtime_signatures() -> None:
    for family in _families():
        family_records = {record["name"] for record in family["records"]}
        for item in family["recognisers"]:
            name = item["entry_point"].removeprefix("b123d_recognisers.")
            recogniser = getattr(recognition, name)
            parameters = list(inspect.signature(recogniser).parameters.values())
            actual_kind = "part" if parameters[0].name == "part" else "derived"
            returned = {
                record.__name__
                for record in _record_types(typing.get_type_hints(recogniser)["return"])
            }
            assert item["kind"] == actual_kind, name
            assert returned and returned <= family_records, name


def test_manifest_record_schemas_match_exported_dataclasses() -> None:
    for family in _families():
        for declared in family["records"]:
            record_type = getattr(recognition, declared["name"])
            hints = typing.get_type_hints(record_type)
            actual = {}
            for field in sorted(dataclasses.fields(record_type), key=lambda item: item.name):
                actual[field.name] = {
                    "required": field.default is dataclasses.MISSING
                    and field.default_factory is dataclasses.MISSING,
                    "type": _type_name(hints[field.name]),
                }
            projected = {
                name: {"required": schema["required"], "type": schema["type"]}
                for name, schema in declared["fields"].items()
            }
            assert projected == actual, declared["name"]
            assert declared["qualified_name"] == f"b123d_recognisers.{declared['name']}"
            assert getattr(recognition, declared["name"]) is record_type


def test_aggregate_membership_paths_resolve_to_the_declared_record() -> None:
    for family in _families():
        for record in family["records"]:
            for path in record["aggregate_membership"]:
                assert path.startswith("RecognitionResult.")
                candidates: set[object] = {RecognitionResult}
                for segment in path.split(".")[1:]:
                    next_candidates: set[object] = set()
                    for candidate in candidates:
                        if inspect.isclass(candidate) and dataclasses.is_dataclass(candidate):
                            annotation = typing.get_type_hints(candidate)[segment]
                            next_candidates.update(_record_types(annotation))
                    candidates = next_candidates
                    assert candidates, path
                assert record["name"] in {candidate.__name__ for candidate in candidates}, path


def test_manifest_census_names_match_the_runtime_census_exactly() -> None:
    actual = set(feature_census(Box(20, 20, 20)))
    declared = {family["census_name"] for family in _families() if family["census_name"]}

    assert declared == actual


def test_manifest_preserves_consumed_output_and_geometry_only_evidence_boundaries() -> None:
    families = {family["id"]: family for family in _families()}

    boss = families["bosses"]
    repeating = families["repeating-radial-profiles"]
    assert [(record["name"], record["role"]) for record in boss["records"]] == [
        ("BossRecord", "output")
    ]
    assert [(record["name"], record["role"]) for record in repeating["records"]] == [
        ("RepeatingRadialProfile", "evidence")
    ]
    assert repeating["census_name"] is None and repeating["census_rationale"]
    assert "tests/golden/repeating_radial_profile/expected.json" in repeating["golden_evidence"]


def test_manifest_evidence_and_documentation_are_live_source_paths() -> None:
    for family in _families():
        for key in ("documentation", "golden_evidence", "test_evidence"):
            for reference in family[key]:
                path = ROOT / reference.split("#", 1)[0]
                assert path.is_file(), f"{family['id']} has stale {key} path {reference}"
        for reference in family["golden_evidence"]:
            payload = json.loads((ROOT / reference).read_text(encoding="utf-8"))
            assert payload, f"{reference} is not canonical expected data"


def test_committed_manifest_is_the_deterministic_generator_output() -> None:
    subprocess.run(
        [sys.executable, "tools/generate_capability_manifest.py", "--check"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value.clear(), "missing required top-level"),
        (lambda value: value.update({"format": "something-else"}), "document kind"),
        (lambda value: value.update({"future_policy": {}}), "unknown fields"),
        (lambda value: value.update({"format_version": 2}), "unsupported capability format"),
        (lambda value: value.update({"package": None}), "package must be"),
        (lambda value: value["package"].update({"name": "other"}), "package identity"),
        (lambda value: value["package"].update({"version": ""}), "non-empty string"),
        (lambda value: value["package"].update({"version": "next"}), "semantic package"),
        (lambda value: value.update({"families": []}), "non-empty array"),
        (lambda value: value["families"].append(copy.deepcopy(value["families"][0])), "unique"),
        (lambda value: value["families"].reverse(), "unique and sorted"),
        (lambda value: value["families"].__setitem__(0, None), "must be an object"),
        (lambda value: value["families"][0].pop("documentation"), "missing required"),
        (lambda value: value["families"][0].update({"id": "Not valid"}), "id is invalid"),
        (lambda value: value["families"][0].update({"status": "maybe"}), "unknown status"),
        (
            lambda value: value["families"][0].update({"recognisers": []}),
            "needs runtime entries",
        ),
        (
            lambda value: value["families"][0].update({"recognisers": {}}),
            "recognisers must be an array",
        ),
        (
            lambda value: value["families"][0]["recognisers"].__setitem__(0, None),
            "recogniser must be an object",
        ),
        (
            lambda value: value["families"][0]["recognisers"][0].update({"kind": "magic"}),
            "recogniser is invalid",
        ),
        (
            lambda value: value["families"][0]["recognisers"][0].update(
                {"entry_point": "private.recognise_bosses"}
            ),
            "entry point is not public",
        ),
        (
            lambda value: value["families"][0].update({"records": {}}),
            "records must be an array",
        ),
        (
            lambda value: value["families"][0]["records"].__setitem__(0, None),
            r"record\[0\] must be an object",
        ),
        (
            lambda value: value["families"][0]["records"][0].pop("role"),
            "missing required fields",
        ),
        (
            lambda value: value["families"][0]["records"][0].update({"name": ""}),
            "name must be a non-empty",
        ),
        (
            lambda value: value["families"][0]["records"][0].update(
                {"qualified_name": "private.BossRecord"}
            ),
            "non-public qualified",
        ),
        (
            lambda value: value["families"][0]["records"][0].update({"role": "helper"}),
            "unknown role",
        ),
        (
            lambda value: value["families"][0]["records"][0].update({"schema_version": 0}),
            "positive integer",
        ),
        (
            lambda value: value["families"][0]["records"][0].update(
                {"aggregate_membership": "RecognitionResult.bosses"}
            ),
            "aggregate_membership is invalid",
        ),
        (lambda value: value["families"][0]["records"][0]["fields"].clear(), "non-empty"),
        (
            lambda value: value["families"][0]["records"][0]["fields"].__setitem__(
                "axis", None
            ),
            "axis must be an object",
        ),
        (
            lambda value: value["families"][0]["records"][0]["fields"]["axis"].pop(
                "units"
            ),
            "missing schema data",
        ),
        (
            lambda value: value["families"][0]["records"][0]["fields"]["axis"].update(
                {"required": 1}
            ),
            "required must be boolean",
        ),
        (
            lambda value: value["families"][0]["records"][0]["fields"]["axis"].update(
                {"type": "whatever"}
            ),
            "outside format 1 grammar",
        ),
        (
            lambda value: value["families"][0]["records"][0]["fields"]["axis"].update(
                {"type": "float]"}
            ),
            "outside format 1 grammar",
        ),
        (
            lambda value: value["families"][0]["records"][0]["fields"]["axis"].update(
                {"type": "list[float"}
            ),
            "outside format 1 grammar",
        ),
        (
            lambda value: value["families"][0]["records"][0]["fields"]["axis"].update(
                {"type": "list[float ]"}
            ),
            "outside format 1 grammar",
        ),
        (
            lambda value: value["families"][0]["records"][0]["fields"]["axis"].update(
                {"units": "pixels"}
            ),
            "unknown units",
        ),
        (
            lambda value: value["families"][0].update({"introduced_in": "9.0.0"}),
            "introduced after",
        ),
        (
            lambda value: value["families"][5].pop("census_rationale"),
            "needs census_rationale",
        ),
        (
            lambda value: value["families"][0].update({"census_name": 3}),
            "census_name is invalid",
        ),
        (
            lambda value: value["families"][0].update({"documentation": []}),
            "non-empty path list",
        ),
        (
            lambda value: value["families"][0].update({"documentation": ["../private"]}),
            "invalid source-relative",
        ),
        (lambda value: value.update({"aliases": {}}), "aliases must be an array"),
    ],
)
def test_schema_validation_fails_closed(mutate, message: str) -> None:
    manifest = capability_manifest()
    mutate(manifest)
    with pytest.raises(CapabilityManifestError, match=message):
        validate_capability_manifest(manifest)


def test_alias_transition_validation_accepts_a_live_alias_and_rejects_stale_removal() -> None:
    manifest = capability_manifest()
    alias = {
        "deprecated_in": "0.1.0",
        "kind": "family",
        "old": "cylindrical-bosses",
        "rationale": "Retained for one compatibility cycle after the stable ID was clarified.",
        "remove_in": "0.3.0",
        "replacement": "bosses",
    }
    manifest["aliases"] = [alias]
    validate_capability_manifest(manifest)

    alias["remove_in"] = "0.1.0"
    with pytest.raises(CapabilityManifestError, match="removal must follow|passed its removal"):
        validate_capability_manifest(manifest)


def test_alias_validation_rejects_unknown_targets_cycles_reuse_and_bad_order() -> None:
    base = {
        "deprecated_in": "0.1.0",
        "kind": "family",
        "rationale": "Compatibility alias.",
        "remove_in": "0.3.0",
    }

    manifest = capability_manifest()
    manifest["aliases"] = [{**base, "old": "old-boss", "replacement": "missing"}]
    with pytest.raises(CapabilityManifestError, match="unknown family"):
        validate_capability_manifest(manifest)

    manifest["aliases"] = [{**base, "old": "bosses", "replacement": "bosses"}]
    with pytest.raises(CapabilityManifestError, match="reuses a current name"):
        validate_capability_manifest(manifest)

    manifest["aliases"] = [
        {**base, "old": "old-a", "replacement": "old-b"},
        {**base, "old": "old-b", "replacement": "old-a"},
    ]
    with pytest.raises(CapabilityManifestError, match="alias cycle"):
        validate_capability_manifest(manifest)

    manifest["aliases"] = [
        {**base, "old": "old-b", "replacement": "bosses"},
        {**base, "old": "old-a", "replacement": "bosses"},
    ]
    with pytest.raises(CapabilityManifestError, match="unique and sorted"):
        validate_capability_manifest(manifest)


def test_alias_validation_rejects_non_objects_bad_kinds_empty_values_and_elapsed_aliases() -> None:
    manifest = capability_manifest()
    manifest["aliases"] = [None]
    with pytest.raises(CapabilityManifestError, match="must be an object"):
        validate_capability_manifest(manifest)

    alias = {
        "deprecated_in": "0.0.1",
        "kind": "other",
        "old": "old-boss",
        "rationale": "Compatibility alias.",
        "remove_in": "0.3.0",
        "replacement": "bosses",
    }
    manifest["aliases"] = [alias]
    with pytest.raises(CapabilityManifestError, match="kind must be"):
        validate_capability_manifest(manifest)

    alias["kind"] = "family"
    alias["rationale"] = ""
    with pytest.raises(CapabilityManifestError, match="non-empty strings"):
        validate_capability_manifest(manifest)

    alias["rationale"] = "Compatibility alias."
    alias["remove_in"] = "0.1.0"
    with pytest.raises(CapabilityManifestError, match="passed its removal version"):
        validate_capability_manifest(manifest)


def test_reserved_family_shape_and_global_uniqueness_rules_fail_closed() -> None:
    manifest = capability_manifest()
    family = manifest["families"][0]
    family["status"] = "deferred"
    family["rationale"] = "Reserved until independent geometry evidence exists."
    with pytest.raises(CapabilityManifestError, match="claims runtime support"):
        validate_capability_manifest(manifest)

    family["recognisers"] = []
    family["records"] = []
    family["golden_evidence"] = []
    family["census_name"] = None
    family["census_rationale"] = "No runtime family exists to count."
    validate_capability_manifest(manifest)

    family.pop("rationale")
    with pytest.raises(CapabilityManifestError, match="needs rationale"):
        validate_capability_manifest(manifest)

    manifest = capability_manifest()
    manifest["families"][10]["records"].reverse()
    with pytest.raises(CapabilityManifestError, match="records are not sorted"):
        validate_capability_manifest(manifest)

    manifest = capability_manifest()
    duplicate = copy.deepcopy(manifest["families"][1]["records"][0])
    manifest["families"][0]["records"].append(duplicate)
    with pytest.raises(CapabilityManifestError, match="exactly one primary family"):
        validate_capability_manifest(manifest)

    manifest = capability_manifest()
    duplicate_entry = copy.deepcopy(manifest["families"][0]["recognisers"][0])
    manifest["families"][0]["recognisers"].append(duplicate_entry)
    with pytest.raises(CapabilityManifestError, match="exactly one family"):
        validate_capability_manifest(manifest)


def test_format_type_grammar_accepts_nested_fixed_tuple_and_union() -> None:
    manifest = capability_manifest()
    axis = manifest["families"][0]["records"][0]["fields"]["axis"]
    axis["type"] = "tuple[list[float|null],2]"
    validate_capability_manifest(manifest)


def test_runtime_version_mismatch_and_cli_are_fail_closed(monkeypatch, capsys) -> None:
    monkeypatch.setattr(capabilities_module, "__version__", "9.9.9")
    with pytest.raises(CapabilityManifestError, match="does not match installed package"):
        capability_manifest()

    monkeypatch.setattr(capabilities_module, "__version__", recognition.__version__)
    assert capabilities_module.main(["--format-version", "1"]) == 0
    assert capsys.readouterr().out == MANIFEST.read_text(encoding="utf-8")
