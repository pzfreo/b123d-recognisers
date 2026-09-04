# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Constant-section recess records and recognition.

``SectionRecess`` is the public, geometry-first recess contract selected by ADR 0019.  Face and
body references are zero-based indices in the input part's deterministic face/solid rosters;
they are meaningful only within the recognition result produced for that part.
"""

from __future__ import annotations

from dataclasses import dataclass

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers._claims import EvidenceWriter
from b123d_recognisers._section_recess import (
    ClosedSectionProfile,
    SectionEnd,
    SectionRecessClassification,
    SectionRecessEnds,
    SectionRecessEvidence,
    SectionRecessGeometry,
    SectionRecessOccurrence,
    _candidates,
)
from b123d_recognisers._typing import Part


@dataclass(frozen=True, order=True, slots=True)
class SectionRecess(SectionRecessOccurrence):
    """One indexed, reconstructible constant-section recess occurrence."""


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


__all__ = [
    "ClosedSectionProfile",
    "SectionEnd",
    "SectionRecess",
    "SectionRecessClassification",
    "SectionRecessEnds",
    "SectionRecessEvidence",
    "SectionRecessGeometry",
    "recognise_section_recesses",
]
