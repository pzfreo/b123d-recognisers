# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Supported within-run references from accepted recognition to caller faces.

References issued here are deliberately not persistent names. They are valid only with the
exact :class:`RecognitionEvidence` that issued them and while its input part remains unchanged.
"""

from __future__ import annotations

import copy
import json
from importlib.resources import files
from typing import NoReturn, Protocol, SupportsIndex, cast

from b123d_recognisers import __version__
from b123d_recognisers._adjacency import FaceNode
from b123d_recognisers._candidates import Candidate, EvidenceIndex
from b123d_recognisers._registry import PHYSICAL_DEFINITIONS
from b123d_recognisers._typing import CylinderInventory, FaceLike, Part
from b123d_recognisers.result import RecognitionResult, _take_inventory

EVIDENCE_API_FORMAT = "b123d-recognisers-evidence-api"
EVIDENCE_API_FORMAT_VERSION = 1


class EvidenceApiManifestError(ValueError):
    """The installed recognition-evidence API document is unavailable or unsupported."""


class RecognitionRecord(Protocol):
    """Common serializable surface of every physical recognition record."""

    def to_dict(self) -> dict[str, object]: ...


class FaceRef:
    """Opaque identity for one original face within one recognition-evidence view."""

    __slots__ = ("__authority",)
    __authority: object

    def __init__(self) -> None:
        raise TypeError("face references are issued by build_recognition_evidence")

    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        del protocol
        raise TypeError("face references are run-local and cannot be serialized")


class FeatureRef:
    """Opaque identity for one accepted feature occurrence within one evidence view."""

    __slots__ = ("__authority",)
    __authority: object

    def __init__(self) -> None:
        raise TypeError("feature references are issued by build_recognition_evidence")

    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        del protocol
        raise TypeError("feature references are run-local and cannot be serialized")


class RecognitionEvidence:
    """One immutable projection of accepted occurrences and exact caller-part faces."""

    __slots__ = (
        "__authority",
        "__result",
        "__features",
        "__feature_candidates",
        "__feature_families",
        "__faces",
        "__face_nodes",
        "__node_refs",
        "__node_faces",
        "__evidence",
    )
    __authority: object
    __result: RecognitionResult
    __features: tuple[FeatureRef, ...]
    __feature_candidates: tuple[Candidate[object], ...]
    __feature_families: tuple[str, ...]
    __faces: frozenset[FaceRef]
    __face_nodes: dict[int, FaceNode]
    __node_refs: dict[FaceNode, FaceRef]
    __node_faces: dict[FaceNode, FaceLike]
    __evidence: EvidenceIndex

    def __init__(self) -> None:
        raise TypeError("recognition evidence is created by build_recognition_evidence")

    @property
    def result(self) -> RecognitionResult:
        """The existing immutable result projected from this view's one recognition run."""

        return self.__result

    @property
    def features(self) -> tuple[FeatureRef, ...]:
        """Accepted physical feature occurrences in stable registry/source order."""

        return self.__features

    @property
    def faces(self) -> frozenset[FaceRef]:
        """All original faces in the exact input part, as unordered opaque references."""

        return self.__faces

    def family(self, feature: FeatureRef) -> str:
        """Return the stable package family identifier for *feature*."""

        position = self.__feature_position(feature)
        return self.__feature_families[position]

    def record(self, feature: FeatureRef) -> RecognitionRecord:
        """Return the existing immutable recognition record for *feature*."""

        return cast(
            RecognitionRecord,
            self.__feature_candidates[self.__feature_position(feature)].record,
        )

    def defining_faces(self, feature: FeatureRef) -> frozenset[FaceRef]:
        """Return the exact original faces that establish *feature*."""

        candidate = self.__feature_candidates[self.__feature_position(feature)]
        return frozenset(
            self.__node_refs[node] for node in self.__evidence.defining_of(candidate)
        )

    def face(self, reference: FaceRef) -> FaceLike:
        """Resolve *reference* to its borrowed original build123d face."""

        node = self.__face_node(reference)
        return self.__node_faces[node]

    def __feature_position(self, feature: FeatureRef) -> int:
        if type(feature) is not FeatureRef:
            raise TypeError("feature must be a FeatureRef")
        if getattr(feature, "_FeatureRef__authority", None) is not self.__authority:
            raise ValueError("feature reference is foreign, copied, forged, or stale")
        try:
            position = self.__features.index(feature)
        except ValueError as error:  # copied values carry the token but not issued identity
            raise ValueError("feature reference is foreign, copied, forged, or stale") from error
        return position

    def __face_node(self, reference: FaceRef) -> FaceNode:
        if type(reference) is not FaceRef:
            raise TypeError("face must be a FaceRef")
        if getattr(reference, "_FaceRef__authority", None) is not self.__authority:
            raise ValueError("face reference is foreign, copied, forged, or stale")
        node = self.__face_nodes.get(id(reference))
        if node is None or self.__node_refs.get(node) is not reference:
            raise ValueError("face reference is foreign, copied, forged, or stale")
        return node


def _issue_reference(
    reference_type: type[FaceRef] | type[FeatureRef], authority: object
) -> FaceRef | FeatureRef:
    reference = object.__new__(reference_type)
    object.__setattr__(reference, f"_{reference_type.__name__}__authority", authority)
    return reference


def build_recognition_evidence(
    part: Part,
    *,
    cylinders: CylinderInventory | None = None,
    rotational: bool = False,
) -> RecognitionEvidence:
    """Recognise *part* once and project accepted occurrences to its exact original faces.

    The caller must not mutate *part* while using the returned view. This raw-coordinate API is
    intentionally separate from framed recognition until framed evidence can be mapped back to
    faces of the caller's part.
    """

    product = _take_inventory(part, cylinders=cylinders, rotational=rotational)
    authority = object()
    result = object.__new__(RecognitionEvidence)
    node_refs: dict[FaceNode, FaceRef] = {}
    face_nodes: dict[int, FaceNode] = {}
    node_faces: dict[FaceNode, FaceLike] = {}
    for node in product.context.graph.nodes:
        reference = cast(FaceRef, _issue_reference(FaceRef, authority))
        node_refs[node] = reference
        face_nodes[id(reference)] = node
        node_faces[node] = product.context.graph.face(node)

    feature_refs: list[FeatureRef] = []
    candidates: list[Candidate[object]] = []
    families: list[str] = []
    accepted = product.accepted
    for definition in PHYSICAL_DEFINITIONS:
        for candidate in accepted.candidate_set(definition.family).candidates:
            feature_refs.append(cast(FeatureRef, _issue_reference(FeatureRef, authority)))
            candidates.append(candidate)
            families.append(definition.family.value)

    object.__setattr__(result, "_RecognitionEvidence__authority", authority)
    object.__setattr__(result, "_RecognitionEvidence__result", product.result)
    object.__setattr__(result, "_RecognitionEvidence__features", tuple(feature_refs))
    object.__setattr__(result, "_RecognitionEvidence__feature_candidates", tuple(candidates))
    object.__setattr__(result, "_RecognitionEvidence__feature_families", tuple(families))
    object.__setattr__(result, "_RecognitionEvidence__faces", frozenset(node_refs.values()))
    object.__setattr__(result, "_RecognitionEvidence__face_nodes", face_nodes)
    object.__setattr__(result, "_RecognitionEvidence__node_refs", node_refs)
    object.__setattr__(result, "_RecognitionEvidence__node_faces", node_faces)
    object.__setattr__(result, "_RecognitionEvidence__evidence", product.evidence)
    return result


def evidence_api_manifest(
    *, format_version: int = EVIDENCE_API_FORMAT_VERSION
) -> dict[str, object]:
    """Return an isolated copy of the installed evidence API contract."""

    if type(format_version) is not int or format_version != EVIDENCE_API_FORMAT_VERSION:
        raise EvidenceApiManifestError(f"unsupported requested format version {format_version!r}")
    raw = files("b123d_recognisers").joinpath("evidence_api.json").read_text(encoding="utf-8")
    manifest = cast(dict[str, object], json.loads(raw))
    _validate_manifest(manifest)
    return copy.deepcopy(manifest)


def _validate_manifest(manifest: object) -> None:
    if not isinstance(manifest, dict) or set(manifest) != {
        "api",
        "format",
        "format_version",
        "package",
    }:
        raise EvidenceApiManifestError("evidence API manifest has an invalid closed shape")
    if manifest["format"] != EVIDENCE_API_FORMAT or (
        type(manifest["format_version"]) is not int
        or manifest["format_version"] != EVIDENCE_API_FORMAT_VERSION
    ):
        raise EvidenceApiManifestError("evidence API manifest format is unsupported")
    package = manifest["package"]
    if not isinstance(package, dict) or set(package) != {"name", "version"} or (
        package["name"] != "b123d-recognisers" or package["version"] != __version__
    ):
        raise EvidenceApiManifestError("evidence API package identity or version is invalid")
    api = manifest["api"]
    if not isinstance(api, dict) or set(api) != {
        "major",
        "namespace",
        "references",
        "symbols",
    }:
        raise EvidenceApiManifestError("evidence API declaration has an invalid closed shape")
    symbols = api["symbols"]
    references = api["references"]
    expected_symbols = sorted(
        {
            "EVIDENCE_API_FORMAT",
            "EVIDENCE_API_FORMAT_VERSION",
            "EvidenceApiManifestError",
            "FaceRef",
            "FeatureRef",
            "RecognitionEvidence",
            "RecognitionRecord",
            "build_recognition_evidence",
            "evidence_api_manifest",
            "evidence_api_manifest_json",
        }
    )
    if (
        api["major"] != 1
        or api["namespace"] != "b123d_recognisers.evidence"
        or not isinstance(references, dict)
        or set(references) != {"FaceRef", "FeatureRef"}
        or not all(isinstance(value, str) and value for value in references.values())
        or symbols != expected_symbols
    ):
        raise EvidenceApiManifestError("evidence API declaration is malformed")


def evidence_api_manifest_json(*, format_version: int = EVIDENCE_API_FORMAT_VERSION) -> str:
    """Return the canonical installed evidence API document."""

    manifest = evidence_api_manifest(format_version=format_version)
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


__all__ = [
    "EVIDENCE_API_FORMAT",
    "EVIDENCE_API_FORMAT_VERSION",
    "EvidenceApiManifestError",
    "FaceRef",
    "FeatureRef",
    "RecognitionEvidence",
    "RecognitionRecord",
    "build_recognition_evidence",
    "evidence_api_manifest",
    "evidence_api_manifest_json",
]
