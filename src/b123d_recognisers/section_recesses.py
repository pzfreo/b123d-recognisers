# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Constant-section recess records and recognition.

``SectionRecess`` is the public, geometry-first recess contract selected by ADR 0019.  Face and
body references are zero-based indices in the input part's deterministic face/solid rosters;
they are meaningful only within the recognition result produced for that part.
"""

from __future__ import annotations

from dataclasses import replace

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import EvidenceWriter
from b123d_recognisers._section_recess import (
    ClosedSectionProfile,
    OpenSectionProfile,
    SectionEnd,
    SectionRecess,
    SectionRecessBodyRef,
    SectionRecessClassification,
    SectionRecessDocument,
    SectionRecessEnds,
    SectionRecessEvidence,
    SectionRecessFaceRef,
    SectionRecessGeometry,
    _candidates,
)
from b123d_recognisers._typing import Part


def _discover_section_recesses(
    part: Part, *, writer: EvidenceWriter | None = None
) -> list[SectionRecess]:
    graph = writer.graph if writer is not None else FaceGraph(part)
    found = _candidates(graph)
    records = [
        SectionRecess(
            index,
            candidate.body,
            candidate.geometry,
            SectionRecessClassification("pocket", candidate.section_shape),
            SectionRecessEvidence(candidate.defining_faces, candidate.constituent_faces),
        )
        for index, candidate in enumerate(found)
    ]
    if writer is not None:
        for record in records:
            defining = tuple(graph.nodes[index] for index in record.evidence.defining_faces)
            constituent = tuple(graph.nodes[index] for index in record.evidence.constituent_faces)
            writer.add_defining(
                record,
                defining,
                family=FamilyId.SECTION_RECESSES,
                constituent=constituent,
            )
    return records


def recognise_section_recesses(part: Part) -> list[SectionRecess]:
    """Recognise truthful one-ended constant-section recesses in *part*."""

    return _discover_section_recesses(part)


def build_section_recess_document(part: Part) -> SectionRecessDocument:
    """Project accepted aggregate recesses into one deterministic JSON-safe document.

    Recognition and reconciliation run exactly once through the ordinary raw/caller-coordinate
    aggregate.  Occurrence indices are then made dense within this document; body and face indices
    retain the aggregate run's complete input rosters.
    """

    # Local to avoid making result.py and this public facade depend on one another at import time.
    from b123d_recognisers.result import build_raw_recognition_result

    result = build_raw_recognition_result(part)
    occurrences = tuple(
        replace(record, index=index) for index, record in enumerate(result.section_recesses)
    )
    return SectionRecessDocument(
        1,
        "result",
        tuple(SectionRecessBodyRef(index) for index, _ in enumerate(part.solids())),
        tuple(SectionRecessFaceRef(index) for index, _ in enumerate(part.faces())),
        occurrences,
    )


__all__ = [
    "ClosedSectionProfile",
    "OpenSectionProfile",
    "SectionEnd",
    "SectionRecess",
    "SectionRecessBodyRef",
    "SectionRecessClassification",
    "SectionRecessDocument",
    "SectionRecessEnds",
    "SectionRecessEvidence",
    "SectionRecessFaceRef",
    "SectionRecessGeometry",
    "build_section_recess_document",
    "recognise_section_recesses",
]
