# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""Prismatic passage recognition: a polygonal void running through the material.

A **passage** is a closed ring of planar walls with nothing capping either end. MFCAD++ splits
them by cross-section -- triangular, rectangular, six-sided -- but the geometry does not: they
are one shape with a side count, and measured over 120 of its models the count is exactly the
polygon's, 3 in 74 of 91 triangular instances, 4 in 40 of 64 rectangular, 6 in 46 of 60
six-sided.

What separates a passage from its neighbours is what is *not* there:

- **from a pocket, the floor.** A pocket's ring is capped at one end by a face perpendicular to
  the run axis and filling the ring's cross-section. A passage's is capped at neither end.
  Distinguishing that cap from the part's own end face matters and is easy to get wrong: at a
  passage mouth the outer face is perpendicular and edge-adjacent too, so the test is whether
  it *fills* the ring or the ring is a hole punched through it.
- **from a polygonal boss, the material.** The same ring bounds a prism when the material is
  inside it and a void when the material is outside, which one solid-classifier probe answers --
  at a point proved to lie inside the cross-section, not at an average that may not.

**A through slot is also a passage, and this module says so.** The two families describe the
same void from different directions, and reconciling them is not this recogniser's job: a
recogniser that dropped a ring because `recognise_slots` had claimed it would be consulting
another family's result during discovery, which ADR 0002 forbids outright ("recognisers do not
call sibling recognisers") and ADR 0003 forbids by name. An earlier draft did exactly that,
comparing a ring's averaged centre against a slot record's XY centre within 1e-6. So this module
reports every ring it finds and records which faces each was built from;
:func:`b123d_recognisers.build_recognition_result` holds the one named rule that resolves the
overlap. `recognise_passages` therefore reports *candidates* and the aggregate reports the
reconciled set, differing by exactly the through slots. That is not this family being special:
every base recogniser proposes under ADR 0003, and this is simply the first pair the reconciler
has had a rule for. `recognise_grooves` and `recognise_turned_steps` describe one band twice
today and nothing decides between them yet.

Over 120 MFCAD++ models: 100% precision, 51% instance recall (65 of 128) and 49% of
labelled faces, measured against that corpus's own labels. The corpus is synthetic and the
recall gap is one thing rather than many -- walls whose spans differ, because a passage running
through a stepped region has one wall shorter than the rest, so the ring never forms.

Every gate is topological or a direction comparison. There is no size gate and no tolerance on
a length, so a passage is a passage at any scale -- ``tests/test_scale_invariance.py`` carries
the family with no exclusion.

The face attributes come from :class:`b123d_recognisers._adjacency.FaceGraph`. An earlier draft
built its own index map, neighbour map, planar-normal map and bounding-box map inside this
function -- an ad hoc face graph private to one recogniser, which is what the substrate exists
to stop. Ring-finding is :func:`b123d_recognisers._adjacency.connected_components`, shared with
``polygonal_bosses``, which finds the same ring from outside.
"""

from __future__ import annotations

from dataclasses import dataclass

from b123d_recognisers._adjacency import (
    FaceEdges,
    FaceGraph,
    FaceNode,
)
from b123d_recognisers._candidates import EvidenceSink, FamilyId
from b123d_recognisers._claims import ClaimLedger, EvidenceWriter
from b123d_recognisers._record import Record
from b123d_recognisers._rings import _centroid, rings
from b123d_recognisers._typing import Part

#: Two walls belong to one ring when their spans along the run axis agree. A coordinate
#: comparison between two faces of one feature, so ADR 0008 makes it a tolerance rather than a
#: minimum-evidence threshold -- but it compares two derivations of the *same* extrusion, which
#: differ only by kernel noise, so it is a float epsilon and not a length at all.
_SPAN_EPS = 1e-6


@dataclass(frozen=True, order=True)
class Passage(Record):
    """A recognised passage.

    ``axis`` is the direction it runs ("x"/"y"/"z"); ``sides`` is the number of walls, so a
    triangular passage reports 3 and a hexagonal one 6; ``length`` is how far it runs; ``at`` is
    the centre of the void in part space.

    ``section`` is the cross-section: its corners in part coordinates, in the two axes other
    than ``axis`` and in that axis order, walked around the ring. Without it the record could
    not describe the feature it names -- two passages of radically different size, aspect ratio
    and rotation produced the same record apart from centre and length, which is a taxonomy
    label rather than a dimension a consumer can draw from. From the corners a consumer can
    take across-flats, area, aspect and orientation; a single scalar could not, because 63% of
    the corpus's passages are not regular polygons.

    The walk is canonical, not the kernel's: corners run anticlockwise in the two section axes,
    starting at the lexicographically smallest, so equivalent geometry gives an equal record
    however the part was traversed.
    """

    axis: str
    sides: int
    length: float
    at: tuple[float, float, float]
    section: tuple[tuple[float, float], ...]


def recognise_passages(
    part: Part,
    *,
    face_edges: FaceEdges | None = None,
    ledger: ClaimLedger | EvidenceWriter | None = None,
) -> list[Passage]:
    """Recognise the prismatic passages of *part* (see module docstring).

    Returns one :class:`Passage` per closed uncapped ring, sorted deterministically. Empty when
    the part has none. Only passages whose walls all run parallel to one principal axis, share
    one span, and meet their neighbours along a single edge parallel to that axis are recovered;
    a passage whose walls step or taper along its length is not one.

    **A through slot is reported here too** -- it is a closed uncapped ring. The families are
    reconciled in :func:`b123d_recognisers.build_recognition_result` and not here; see the
    module docstring for why that separation is not optional.

    *ledger* records which faces each returned passage was built from: its ring, and nothing
    else. When it is given, its graph is used as the face inventory, so *face_edges* is then the
    memo that graph was built with rather than one taken here.
    """

    graph = FaceGraph(part, face_edges=face_edges) if ledger is None else ledger.graph
    return _discover_passages(part, graph, None if ledger is None else ledger.sink)


def _discover_passages(
    part: Part,
    graph: FaceGraph,
    sink: EvidenceSink | None,
) -> list[Passage]:
    """Discover passages from neutral graph facts and an optional write-only evidence sink."""

    found: list[tuple[Passage, tuple[FaceNode, ...]]] = []
    for ring in rings(part, graph):
        if any(ring.caps):
            continue  # a floor fills the ring: that is a pocket, and `_rings` reports which end
        axis, section = ring.axis, ring.section
        others = [a for a in (0, 1, 2) if a != axis]
        middle = _centroid(section)
        at = [0.0, 0.0, 0.0]
        at[axis] = 0.5 * (ring.low + ring.high)
        at[others[0]], at[others[1]] = middle
        found.append(
            (
                Passage(
                    axis="xyz"[axis],
                    sides=len(ring.nodes),
                    length=round(ring.high - ring.low, 3),
                    at=(round(at[0], 3), round(at[1], 3), round(at[2], 3)),
                    section=tuple((round(u, 3), round(v, 3)) for u, v in section),
                ),
                tuple(ring.nodes),
            )
        )

    found.sort(key=lambda pair: (pair[0].axis, pair[0].at))
    if sink is not None:
        for passage, nodes in found:
            sink.propose(FamilyId.PASSAGES, passage, defining=nodes)
    return [passage for passage, _ in found]
