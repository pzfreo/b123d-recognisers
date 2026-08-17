#!/usr/bin/env python3
"""Build the committed capability manifest deterministically from reviewed metadata.

This is a maintenance tool, not the validator. CI independently derives exports, dataclass
schemas, aggregate membership, census keys, and archive contents in
``tests/test_capability_manifest.py`` and compares those facts with the committed document.
"""

from __future__ import annotations

import argparse
import dataclasses
import inspect
import json
import types
import typing
from pathlib import Path

import b123d_recognisers as recognition
from b123d_recognisers._record import Record

ROOT = Path(__file__).parents[1]
TARGET = ROOT / "src" / "b123d_recognisers" / "capabilities.json"

FAMILIES = {
    # `introduced` defaults to 0.1.0 -- every family relicensed from Draftwright arrived
    # together in that release, so only a family originated here needs to state its own.
    "angled-steps": {
        "recognisers": [("recognise_angled_steps", "part")],
        "records": [("AngledStep", "output", ["RecognitionResult.angled_steps"])],
        "census": "angled_step",
        "goldens": ["angled_blind_step"],
        "introduced": "0.2.5",
        "tests": ["tests/test_angled_steps.py"],
    },
    "bosses": {
        "recognisers": [("recognise_bosses", "part")],
        "records": [("BossRecord", "output", ["RecognitionResult.bosses"])],
        "census": "boss",
        "goldens": ["simple_through_hole", "turned_steps_and_grooves"],
    },
    "chamfers": {
        "recognisers": [("recognise_chamfers", "part")],
        "records": [("Chamfer", "output", ["RecognitionResult.chamfers"])],
        "census": "chamfer",
        "goldens": ["chamfers_fillets_and_flats"],
    },
    "channels": {
        "recognisers": [("recognise_channels", "part")],
        "records": [("Channel", "output", ["RecognitionResult.channels"])],
        "census": "channel",
        "goldens": ["open_channels"],
    },
    "countersinks": {
        "recognisers": [("recognise_countersinks", "part")],
        "records": [
            (
                "CounterSink",
                "output",
                ["RecognitionResult.countersinks", "RecognitionResult.holes.csink"],
            )
        ],
        "census": "countersink",
        "goldens": ["counterbored_and_countersunk_holes"],
    },
    "double-d-bores": {
        "recognisers": [("recognise_double_d_bores", "part")],
        "records": [("DoubleDBore", "output", ["RecognitionResult.double_d_bores"])],
        "census": None,
        "goldens": ["double_d_bore"],
    },
    "face-levels": {
        "recognisers": [("recognise_face_levels", "part")],
        "records": [("FaceLevel", "evidence", ["RecognitionResult.step_levels"])],
        "census": None,
        "goldens": ["plates_pads_levels_and_slanted_steps", "slanted_steps"],
    },
    "fillets": {
        "recognisers": [("recognise_fillets", "part")],
        "records": [("Fillet", "output", ["RecognitionResult.fillets"])],
        "census": "fillet",
        "goldens": ["chamfers_fillets_and_flats"],
    },
    "flats": {
        "recognisers": [("recognise_flats", "part")],
        "records": [("Flat", "output", ["RecognitionResult.flats"])],
        "census": "flat",
        "goldens": ["chamfers_fillets_and_flats"],
    },
    "grooves": {
        "recognisers": [("recognise_grooves", "part")],
        "records": [("Groove", "output", ["RecognitionResult.grooves"])],
        "census": "groove",
        "goldens": ["turned_steps_and_grooves"],
    },
    "hole-patterns": {
        "recognisers": [("recognise_hole_patterns", "derived")],
        "records": [
            ("BoltCircle", "output", ["RecognitionResult.hole_patterns"]),
            ("LinearArray", "output", ["RecognitionResult.hole_patterns"]),
            ("RectGrid", "output", ["RecognitionResult.hole_patterns"]),
        ],
        "census": "hole_pattern",
        "goldens": ["bolt_circle_and_rectangular_grid"],
    },
    "holes": {
        "recognisers": [("recognise_holes", "part")],
        "records": [
            (
                "CounterBore",
                "nested",
                ["RecognitionResult.holes.cbore", "RecognitionResult.holes.spotface"],
            ),
            ("HoleRecord", "output", ["RecognitionResult.holes"]),
            ("HoleSpec", "evidence", []),
        ],
        "census": "hole",
        "goldens": ["simple_through_hole", "counterbored_and_countersunk_holes"],
    },
    "plates": {
        "recognisers": [("recognise_plates", "part")],
        "records": [("Plate", "output", ["RecognitionResult.plates"])],
        "census": "plate",
        "goldens": ["plates_pads_levels_and_slanted_steps"],
    },
    "pocket-patterns": {
        "recognisers": [("recognise_pocket_patterns", "derived")],
        "records": [
            ("PocketArray", "output", ["RecognitionResult.pocket_patterns"]),
            ("PocketGrid", "output", ["RecognitionResult.pocket_patterns"]),
        ],
        "census": None,
        "goldens": ["blind_pockets_and_pocket_patterns"],
    },
    "pockets": {
        "recognisers": [("recognise_pockets", "part")],
        "records": [("Pocket", "output", ["RecognitionResult.pockets"])],
        "census": "pocket",
        "goldens": ["blind_pockets_and_pocket_patterns"],
    },
    "polygonal-bosses": {
        "recognisers": [("recognise_polygonal_bosses", "part")],
        "records": [("PolygonalBoss", "output", ["RecognitionResult.polygonal_bosses"])],
        "census": None,
        "goldens": ["polygonal_boss"],
    },
    "polygonal-stock": {
        "recognisers": [("recognise_polygonal_stock", "part")],
        "records": [("PolygonalStock", "output", ["RecognitionResult.polygonal_stock"])],
        "census": None,
        "goldens": ["polygonal_stock"],
    },
    "rectangular-pads": {
        "recognisers": [("recognise_rectangular_pads", "part")],
        "records": [("RaisedPad", "output", ["RecognitionResult.pads"])],
        "census": None,
        "goldens": ["plates_pads_levels_and_slanted_steps"],
    },
    "repeating-radial-profiles": {
        "recognisers": [("recognise_repeating_radial_profiles", "part")],
        "records": [
            (
                "RepeatingRadialProfile",
                "evidence",
                ["RecognitionResult.repeating_radial_profiles"],
            )
        ],
        "census": None,
        "goldens": ["repeating_radial_profile", "traversal_order"],
    },
    "risers": {
        "recognisers": [("recognise_risers", "part")],
        "records": [
            ("RiserEvidence", "evidence", ["RecognitionResult.risers"]),
            ("StepShoulder", "projection", []),
        ],
        "census": None,
        "goldens": ["plates_pads_levels_and_slanted_steps", "slanted_steps"],
    },
    "slot-patterns": {
        "recognisers": [("recognise_slot_patterns", "derived")],
        "records": [
            ("SlotArray", "output", ["RecognitionResult.slot_patterns"]),
            ("SlotGrid", "output", ["RecognitionResult.slot_patterns"]),
        ],
        "census": None,
        "goldens": ["straight_and_obround_slots"],
    },
    "slots": {
        "recognisers": [("recognise_slots", "part")],
        "records": [("Slot", "output", ["RecognitionResult.slots"])],
        "census": "slot",
        "goldens": ["straight_and_obround_slots"],
    },
    "turned-steps": {
        "recognisers": [("recognise_turned_steps", "part")],
        "records": [
            ("TurnedProfile", "aggregate", []),
            ("TurnedStep", "output", ["RecognitionResult.turned_steps"]),
        ],
        "census": "step",
        "goldens": ["turned_steps_and_grooves"],
    },
}

NO_MEMBERSHIP_RATIONALE = {
    "HoleSpec": (
        "Derived grouping key; it is computed from HoleRecord and is not retained by "
        "RecognitionResult."
    ),
    "StepShoulder": "Pure consumer projection from RiserEvidence plus a caller-supplied level set.",
    "TurnedProfile": "Consumer aggregate built on demand from RecognitionResult.turned_steps.",
}


def _union_type(args: tuple[object, ...]) -> str:
    rendered = sorted(
        {_type_name(arg) for arg in args}, key=lambda value: (value == "null", value)
    )
    return "|".join(rendered)


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
        return _union_type(args)
    if origin is tuple:
        if len(args) == 2 and args[1] is Ellipsis:
            return f"list[{_type_name(args[0])}]"
        rendered = [_type_name(arg) for arg in args]
        if len(set(rendered)) == 1:
            return f"tuple[{rendered[0]},{len(rendered)}]"
        return f"list[{_union_type(args)}]"
    raise TypeError(f"unsupported manifest annotation: {annotation!r}")


def _units(field: dataclasses.Field, annotation: object) -> str:
    name = field.name
    rendered = _type_name(annotation)
    if name in {"angle", "included_angle"}:
        return "deg"
    if name in {"axis_direction", "direction", "flat_direction", "flat_directions"}:
        return "unit-vector"
    if name == "axis" and rendered.startswith("tuple[float,3]"):
        return "unit-vector"
    if rendered in {"bool", "int", "str"} or rendered.startswith("record:"):
        return "none"
    if rendered.startswith("list[record:") or name in {
        "body_key",
        "cbore",
        "csink",
        "holes",
        "pockets",
        "sector_signature",
        "slots",
        "spotface",
        "steps",
    }:
        return "none"
    return "mm"


def _record(name: str, role: str, membership: list[str]) -> dict[str, object]:
    record_type = getattr(recognition, name)
    hints = typing.get_type_hints(record_type)
    fields = {}
    for field in sorted(dataclasses.fields(record_type), key=lambda item: item.name):
        annotation = hints[field.name]
        fields[field.name] = {
            "required": field.default is dataclasses.MISSING
            and field.default_factory is dataclasses.MISSING,
            "type": _type_name(annotation),
            "units": _units(field, annotation),
        }
    result: dict[str, object] = {
        "aggregate_membership": membership,
        "fields": fields,
        "name": name,
        "qualified_name": f"b123d_recognisers.{name}",
        "role": role,
        "schema_version": 1,
    }
    if not membership:
        result["aggregate_membership_rationale"] = NO_MEMBERSHIP_RATIONALE[name]
    return result


def build_manifest() -> dict[str, object]:
    families = []
    for family_id, spec in sorted(FAMILIES.items()):
        census = spec["census"]
        family: dict[str, object] = {
            "census_name": census,
            "documentation": ["docs/capabilities.md#proven-recognition-capability"],
            "golden_evidence": sorted(
                f"tests/golden/{name}/expected.json" for name in spec["goldens"]
            ),
            "id": family_id,
            "introduced_in": spec.get("introduced", "0.1.0"),
            "recognisers": [
                {
                    "entry_point": f"b123d_recognisers.{name}",
                    "kind": kind,
                }
                for name, kind in spec["recognisers"]
            ],
            "records": [_record(*record) for record in spec["records"]],
            "status": "supported",
            "test_evidence": sorted(
                [
                    "tests/test_capability_claims.py",
                    "tests/test_recogniser_contract.py",
                    *spec.get("tests", []),
                ]
            ),
        }
        if census is None:
            family["census_rationale"] = (
                "Geometry evidence is deliberately absent from the feature census; "
                "the census is not a completeness denominator."
            )
        families.append(family)
    return {
        "aliases": [],
        "families": families,
        "format": "b123d-recognisers-capabilities",
        "format_version": 1,
        "package": {"name": "b123d-recognisers", "version": recognition.__version__},
    }


def rendered_manifest() -> str:
    return json.dumps(build_manifest(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if the committed JSON differs")
    parser.add_argument("--write", action="store_true", help="replace the committed JSON")
    args = parser.parse_args()
    rendered = rendered_manifest()
    if args.check:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != rendered:
            parser.error(f"{TARGET.relative_to(ROOT)} is stale; run this tool with --write")
        return 0
    if args.write:
        TARGET.write_text(rendered, encoding="utf-8")
        return 0
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
