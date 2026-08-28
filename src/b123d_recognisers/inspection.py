# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Supported geometry reads shared by declared and recognised features.

This is the deliberately narrow F7 API from ADR 0010.  It publishes only the five
consumer-proven inspection operations; graph identity, adjacency, blend collapse,
recognition evidence and correspondence remain private or experimental.

``experimental_geometry.inspect_face`` remains an identity-preserving compatibility
alias.  New consumers should import the supported names from this module.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from enum import Enum
from importlib.resources import files
from typing import Any, TypeAlias, cast

from OCP.BRepAdaptor import BRepAdaptor_Surface
from OCP.Standard import Standard_Failure

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._bevel import BevelReject, classify_bevel
from b123d_recognisers._effective_surfaces import (
    AnalyticSurfaceFact,
    EffectiveSurfaceIndex,
    RefusedSurfaceFact,
)
from b123d_recognisers._typing import FaceLike
from b123d_recognisers.countersinks import cone_rims
from b123d_recognisers.grooves import floor_face_anchor
from b123d_recognisers.profiled_bores import read_double_d_tool

INSPECTION_API_FORMAT = "b123d-recognisers-inspection-api"
INSPECTION_API_FORMAT_VERSION = 1
_INSPECTION_API_MAJOR = 1
_INSPECTION_NAMESPACE = "b123d_recognisers.inspection"
_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[.+-][A-Za-z0-9.-]+)?$")
_SYMBOL = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_KINDS = {"dataclass", "enum", "exception", "function", "type-alias"}

InspectionApiManifest: TypeAlias = dict[str, Any]


class InspectionApiManifestError(ValueError):
    """The installed inspection API manifest is missing, stale, or unsupported."""


class SurfaceKind(Enum):
    PLANE = "plane"
    CYLINDER = "cylinder"
    CONE = "cone"
    SPHERE = "sphere"


class SurfaceProvenance(Enum):
    NATIVE = "native"
    RECOVERED = "recovered"


class OrientationCapability(Enum):
    NATIVE_ORIENTED = "native-oriented"
    RECOVERED_UNORIENTED = "recovered-unoriented"


class SurfaceRefusalReason(Enum):
    UNSUPPORTED_KIND = "unsupported-kind"
    UNSUPPORTED_TORUS_RECOVERY = "unsupported-torus-recovery"
    FIT_UNAVAILABLE = "fit-unavailable"
    INVALID_INPUT = "invalid-input"
    INVALID_RESULT = "invalid-result"
    RESIDUAL_EXCEEDED = "residual-exceeded"
    AMBIGUOUS_PRIMITIVE = "ambiguous-primitive"
    UNSUPPORTED_OCCT_CONTRACT = "unsupported-occt-contract"


@dataclass(frozen=True, slots=True)
class AnalyticSurface:
    """One native or bounded-recovered analytic surface fact."""

    kind: SurfaceKind
    provenance: SurfaceProvenance
    orientation: OrientationCapability
    parameters: tuple[float, ...]
    requested_tolerance: float
    kernel_reported_gap: float


@dataclass(frozen=True, slots=True)
class RefusedSurface:
    """A closed reason why a face has no supported analytic fact."""

    reason: SurfaceRefusalReason


SurfaceFact: TypeAlias = AnalyticSurface | RefusedSurface


@dataclass(frozen=True, slots=True)
class FaceInspection:
    """One face's closed analytic result and optional point on its trimmed surface."""

    surface: SurfaceFact
    anchor: tuple[float, float, float] | None


def _project_surface_fact(fact: AnalyticSurfaceFact | RefusedSurfaceFact) -> SurfaceFact:
    if isinstance(fact, RefusedSurfaceFact):
        return RefusedSurface(SurfaceRefusalReason(fact.reason.value))
    return AnalyticSurface(
        SurfaceKind(fact.kind.value),
        SurfaceProvenance(fact.provenance.value),
        OrientationCapability(fact.orientation.value),
        fact.parameters,
        fact.requested_tolerance,
        fact.kernel_reported_gap,
    )


def _surface_anchor(face: FaceLike) -> tuple[float, float, float]:
    """Midpoint of the original trimmed parameter domain, or a closed refusal."""

    try:
        surface = BRepAdaptor_Surface(face.wrapped)
        u = 0.5 * (surface.FirstUParameter() + surface.LastUParameter())
        v = 0.5 * (surface.FirstVParameter() + surface.LastVParameter())
        point = surface.Value(u, v)
        return (float(point.X()), float(point.Y()), float(point.Z()))
    except (AttributeError, Standard_Failure, RuntimeError, ValueError) as error:
        raise ValueError("surface anchor is unavailable") from error


def inspect_face(face: FaceLike) -> FaceInspection:
    """Return a bounded analytic fact and optional on-surface anchor for one face.

    The call is graph-independent for its consumer: no graph handle or topology identity
    enters or leaves the API.  Internally it uses the same run-owned effective-surface
    authority as aggregate recognition.  Unsupported, ambiguous or unbounded geometry is
    returned as :class:`RefusedSurface`; anchor failure is represented by ``None``.
    """

    graph = FaceGraph(face)
    node = graph.require_node(face)
    surface = _project_surface_fact(EffectiveSurfaceIndex(graph).fact(node))
    try:
        anchor = _surface_anchor(face)
    except ValueError:
        anchor = None
    return FaceInspection(surface, anchor)


def _keys(value: dict[str, Any], allowed: set[str], context: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise InspectionApiManifestError(
            f"{context} has unknown fields: {', '.join(unknown)}"
        )


def _version(value: object, context: str) -> tuple[int, int, int]:
    if not isinstance(value, str) or not (match := _VERSION.fullmatch(value)):
        raise InspectionApiManifestError(f"{context} must be a semantic package version")
    return cast(tuple[int, int, int], tuple(int(item) for item in match.groups()))


def validate_inspection_api_manifest(manifest: object) -> None:
    """Validate the closed format-1 inspection API document."""

    if not isinstance(manifest, dict):
        raise InspectionApiManifestError("inspection API manifest must be a JSON object")
    _keys(manifest, {"api", "format", "format_version", "package"}, "manifest")
    if set(manifest) != {"api", "format", "format_version", "package"}:
        raise InspectionApiManifestError("inspection API manifest is missing required fields")
    if manifest["format"] != INSPECTION_API_FORMAT:
        raise InspectionApiManifestError(
            f"unsupported inspection document kind {manifest['format']!r}"
        )
    if (
        type(manifest["format_version"]) is not int
        or manifest["format_version"] != INSPECTION_API_FORMAT_VERSION
    ):
        raise InspectionApiManifestError(
            f"unsupported inspection format version {manifest['format_version']!r}"
        )

    package = manifest["package"]
    if not isinstance(package, dict):
        raise InspectionApiManifestError("package must be an object")
    _keys(package, {"name", "version"}, "package")
    if set(package) != {"name", "version"} or package["name"] != "b123d-recognisers":
        raise InspectionApiManifestError(
            "package identity must be b123d-recognisers with a version"
        )
    package_version = _version(package["version"], "package.version")

    api = manifest["api"]
    if not isinstance(api, dict):
        raise InspectionApiManifestError("api must be an object")
    _keys(api, {"major", "namespace", "symbols"}, "api")
    if set(api) != {"major", "namespace", "symbols"}:
        raise InspectionApiManifestError("api is missing required fields")
    if type(api["major"]) is not int or api["major"] != _INSPECTION_API_MAJOR:
        raise InspectionApiManifestError(f"unsupported inspection API major {api['major']!r}")
    if api["namespace"] != _INSPECTION_NAMESPACE:
        raise InspectionApiManifestError("inspection API namespace is invalid")
    symbols = api["symbols"]
    if not isinstance(symbols, list) or not symbols:
        raise InspectionApiManifestError("api.symbols must be a non-empty array")

    names: list[str] = []
    for index, symbol in enumerate(symbols):
        context = f"api.symbols[{index}]"
        if not isinstance(symbol, dict):
            raise InspectionApiManifestError(f"{context} must be an object")
        required = {
            "aliases",
            "contract",
            "introduced_in",
            "kind",
            "name",
            "qualified_name",
        }
        _keys(symbol, required, context)
        if set(symbol) != required:
            raise InspectionApiManifestError(f"{context} is missing required fields")
        name = symbol["name"]
        if not isinstance(name, str) or not _SYMBOL.fullmatch(name):
            raise InspectionApiManifestError(f"{context}.name is invalid")
        names.append(name)
        if symbol["qualified_name"] != f"{_INSPECTION_NAMESPACE}.{name}":
            raise InspectionApiManifestError(f"{context}.qualified_name is invalid")
        kind = symbol["kind"]
        if not isinstance(kind, str) or kind not in _KINDS:
            raise InspectionApiManifestError(f"{context}.kind is invalid")
        introduced = _version(symbol["introduced_in"], f"{context}.introduced_in")
        if introduced > package_version:
            raise InspectionApiManifestError(f"{context} is introduced after this package")
        aliases = symbol["aliases"]
        if (
            not isinstance(aliases, list)
            or not all(
                isinstance(alias, str)
                and alias.startswith("b123d_recognisers.")
                and alias != symbol["qualified_name"]
                for alias in aliases
            )
            or aliases != sorted(set(aliases))
        ):
            raise InspectionApiManifestError(f"{context}.aliases is invalid")
        contract = symbol["contract"]
        if not isinstance(contract, dict) or not contract:
            raise InspectionApiManifestError(f"{context}.contract must be a non-empty object")
        expected_contract = {
            "dataclass": {"fields"},
            "enum": {"values"},
            "exception": {"base"},
            "function": {"signature"},
            "type-alias": {"definition"},
        }[kind]
        _keys(contract, expected_contract, f"{context}.contract")
        if set(contract) != expected_contract:
            raise InspectionApiManifestError(f"{context}.contract is incomplete")
        (contract_value,) = contract.values()
        if kind in {"dataclass", "enum"}:
            if (
                not isinstance(contract_value, list)
                or not contract_value
                or not all(isinstance(item, str) and item for item in contract_value)
                or contract_value != list(dict.fromkeys(contract_value))
            ):
                raise InspectionApiManifestError(f"{context}.contract values are invalid")
        elif not isinstance(contract_value, str) or not contract_value:
            raise InspectionApiManifestError(f"{context}.contract value is invalid")
    if names != sorted(names) or len(names) != len(set(names)):
        raise InspectionApiManifestError("inspection API symbols must be unique and name-sorted")


def _load_inspection_api_manifest() -> InspectionApiManifest:
    resource = files("b123d_recognisers").joinpath("inspection_api.json")
    manifest = cast(
        InspectionApiManifest, json.loads(resource.read_text(encoding="utf-8"))
    )
    validate_inspection_api_manifest(manifest)
    from b123d_recognisers import __version__

    package = cast(dict[str, object], manifest["package"])
    if package["version"] != __version__:
        raise InspectionApiManifestError(
            f"inspection API manifest version {package['version']!r} does not match installed "
            f"package version {__version__!r}"
        )
    return manifest


def inspection_api_manifest(
    *, format_version: int = INSPECTION_API_FORMAT_VERSION
) -> InspectionApiManifest:
    """Return an isolated copy of the installed inspection API contract."""

    if type(format_version) is not int or format_version != INSPECTION_API_FORMAT_VERSION:
        raise InspectionApiManifestError(
            f"unsupported requested inspection format version {format_version!r}"
        )
    return copy.deepcopy(_load_inspection_api_manifest())


def inspection_api_manifest_json(
    *, format_version: int = INSPECTION_API_FORMAT_VERSION
) -> str:
    """Return the installed inspection API contract as canonical JSON."""

    return json.dumps(
        inspection_api_manifest(format_version=format_version), indent=2, sort_keys=True
    ) + "\n"


__all__ = [
    "INSPECTION_API_FORMAT",
    "INSPECTION_API_FORMAT_VERSION",
    "AnalyticSurface",
    "BevelReject",
    "FaceInspection",
    "InspectionApiManifestError",
    "OrientationCapability",
    "RefusedSurface",
    "SurfaceFact",
    "SurfaceKind",
    "SurfaceProvenance",
    "SurfaceRefusalReason",
    "classify_bevel",
    "cone_rims",
    "floor_face_anchor",
    "inspect_face",
    "inspection_api_manifest",
    "inspection_api_manifest_json",
    "read_double_d_tool",
    "validate_inspection_api_manifest",
]
