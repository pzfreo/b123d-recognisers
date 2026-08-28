#!/usr/bin/env python3
"""Build the committed inspection API manifest from reviewed roster metadata.

The generator owns only the intended roster, kinds, compatibility aliases and
introduction versions. Tests independently derive the runtime contracts and verify
that the committed document and built archives agree with them.
"""

from __future__ import annotations

import argparse
import dataclasses
import inspect
import json
import types
import typing
from enum import Enum
from pathlib import Path
from typing import Any

import b123d_recognisers.inspection as inspection
from b123d_recognisers import __version__

ROOT = Path(__file__).parents[1]
TARGET = ROOT / "src" / "b123d_recognisers" / "inspection_api.json"
NAMESPACE = "b123d_recognisers.inspection"

SURFACE_PARAMETERS = {
    "cone": [
        ("apex_x", "model-length"),
        ("apex_y", "model-length"),
        ("apex_z", "model-length"),
        ("axis_x", "unitless"),
        ("axis_y", "unitless"),
        ("axis_z", "unitless"),
        ("signed_semi_angle", "radian"),
    ],
    "cylinder": [
        ("axis_point_x", "model-length"),
        ("axis_point_y", "model-length"),
        ("axis_point_z", "model-length"),
        ("axis_x", "unitless"),
        ("axis_y", "unitless"),
        ("axis_z", "unitless"),
        ("radius", "model-length"),
    ],
    "plane": [
        ("normal_x", "unitless"),
        ("normal_y", "unitless"),
        ("normal_z", "unitless"),
        ("offset", "model-length"),
    ],
    "sphere": [
        ("centre_x", "model-length"),
        ("centre_y", "model-length"),
        ("centre_z", "model-length"),
        ("radius", "model-length"),
    ],
}

SYMBOLS: dict[str, tuple[str, list[str]]] = {
    "AnalyticSurface": (
        "dataclass",
        ["b123d_recognisers.experimental_geometry.AnalyticSurface"],
    ),
    "BevelReject": (
        "exception",
        [
            "b123d_recognisers.BevelReject",
            "b123d_recognisers.chamfers.BevelReject",
        ],
    ),
    "FaceInspection": (
        "dataclass",
        ["b123d_recognisers.experimental_geometry.FaceInspection"],
    ),
    "OrientationCapability": (
        "enum",
        ["b123d_recognisers.experimental_geometry.OrientationCapability"],
    ),
    "RefusedSurface": (
        "dataclass",
        ["b123d_recognisers.experimental_geometry.RefusedSurface"],
    ),
    "SurfaceFact": (
        "type-alias",
        ["b123d_recognisers.experimental_geometry.SurfaceFact"],
    ),
    "SurfaceKind": (
        "enum",
        ["b123d_recognisers.experimental_geometry.SurfaceKind"],
    ),
    "SurfaceProvenance": (
        "enum",
        ["b123d_recognisers.experimental_geometry.SurfaceProvenance"],
    ),
    "SurfaceRefusalReason": (
        "enum",
        ["b123d_recognisers.experimental_geometry.SurfaceRefusalReason"],
    ),
    "classify_bevel": (
        "function",
        [
            "b123d_recognisers.chamfers.classify_bevel",
            "b123d_recognisers.classify_bevel",
        ],
    ),
    "cone_rims": (
        "function",
        [
            "b123d_recognisers.cone_rims",
            "b123d_recognisers.countersinks.cone_rims",
        ],
    ),
    "floor_face_anchor": (
        "function",
        [
            "b123d_recognisers.floor_face_anchor",
            "b123d_recognisers.grooves.floor_face_anchor",
        ],
    ),
    "inspect_face": (
        "function",
        ["b123d_recognisers.experimental_geometry.inspect_face"],
    ),
    "read_double_d_tool": (
        "function",
        ["b123d_recognisers.profiled_bores.read_double_d_tool"],
    ),
}


def _type_name(annotation: object) -> str:
    if annotation is type(None):
        return "null"
    if annotation in {bool, float, int, str}:
        return typing.cast(type, annotation).__name__
    if inspect.isclass(annotation) and annotation.__module__.startswith("b123d_recognisers"):
        return annotation.__name__
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    if origin in {typing.Union, types.UnionType}:
        return "|".join(
            sorted({_type_name(arg) for arg in args}, key=lambda item: (item == "null", item))
        )
    if origin is tuple:
        return "tuple[" + ",".join(
            "..." if arg is Ellipsis else _type_name(arg) for arg in args
        ) + "]"
    raise TypeError(f"unsupported inspection field annotation {annotation!r}")


def _contract(name: str, kind: str, value: object) -> dict[str, object]:
    if kind == "dataclass":
        hints = typing.get_type_hints(value)
        parameters = value.__dataclass_params__
        return {
            "fields": [
                {"name": field.name, "type": _type_name(hints[field.name])}
                for field in dataclasses.fields(value)
            ],
            "frozen": bool(parameters.frozen),
            "slots": bool(getattr(parameters, "slots", "__slots__" in value.__dict__)),
        }
    if kind == "enum":
        assert inspect.isclass(value) and issubclass(value, Enum)
        return {
            "members": [
                {"name": member.name, "value": member.value} for member in value
            ]
        }
    if kind == "exception":
        assert inspect.isclass(value) and issubclass(value, Exception)
        return {"base": value.__bases__[0].__name__}
    if kind == "function":
        return {"signature": str(inspect.signature(value))}
    if name == "SurfaceFact" and kind == "type-alias":
        return {"definition": "AnalyticSurface|RefusedSurface"}
    raise AssertionError(f"unsupported inspection API kind {kind!r}")


def document() -> dict[str, Any]:
    symbols = []
    for name, (kind, aliases) in sorted(SYMBOLS.items()):
        value = getattr(inspection, name)
        symbols.append(
            {
                "aliases": sorted(aliases),
                "contract": _contract(name, kind, value),
                "introduced_in": "0.4.4",
                "kind": kind,
                "name": name,
                "qualified_name": f"{NAMESPACE}.{name}",
            }
        )
    return {
        "api": {
            "major": 1,
            "namespace": NAMESPACE,
            "surface_parameters": {
                kind: [{"name": name, "unit": unit} for name, unit in layout]
                for kind, layout in SURFACE_PARAMETERS.items()
            },
            "symbols": symbols,
        },
        "format": inspection.INSPECTION_API_FORMAT,
        "format_version": inspection.INSPECTION_API_FORMAT_VERSION,
        "package": {"name": "b123d-recognisers", "version": __version__},
    }


def rendered() -> str:
    return json.dumps(document(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = rendered()
    if args.write:
        TARGET.write_text(expected, encoding="utf-8")
        return 0
    if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != expected:
        raise SystemExit(
            "inspection API manifest is stale; run "
            "`uv run python tools/generate_inspection_api_manifest.py --write`"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
