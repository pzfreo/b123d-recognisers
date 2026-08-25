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

import math
from dataclasses import dataclass
from typing import cast

from b123d_recognisers._adjacency import (
    FaceEdges,
    FaceGraph,
    FaceNode,
    SolidRef,
)
from b123d_recognisers._candidates import EvidenceSink, FamilyId
from b123d_recognisers._claims import ClaimLedger, EvidenceWriter
from b123d_recognisers._record import Record
from b123d_recognisers._rings import _canonical
from b123d_recognisers._section_passages import SectionRingProposal, section_ring_proposals
from b123d_recognisers._typing import Part

#: Two walls belong to one ring when their spans along the run axis agree. A coordinate
#: comparison between two faces of one feature, so ADR 0008 makes it a tolerance rather than a
#: minimum-evidence threshold -- but it compares two derivations of the *same* extrusion, which
#: differ only by kernel noise, so it is a float epsilon and not a length at all.
_SPAN_EPS = 1e-6
_SECTION_SERIALIZATION_LIMIT = 0.002


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


def _numbers(value: object, size: int, *, name: str) -> tuple[float, ...]:
    if not isinstance(value, tuple) or len(value) != size:
        raise ValueError(f"{name} must be a {size}-tuple")
    if any(isinstance(item, bool) or not isinstance(item, int | float) for item in value):
        raise ValueError(f"{name} must contain finite numbers")
    result = tuple(float(item) for item in value)
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"{name} must contain finite numbers")
    return tuple(0.0 if item == 0.0 else item for item in result)


def _dot(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _cross(
    left: tuple[float, float, float], right: tuple[float, float, float]
) -> tuple[float, float, float]:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _unit(value: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(_dot(value, value))
    if not math.isfinite(length) or length == 0.0:
        raise ValueError("frame direction must be finite and nonzero")
    return tuple(component / length for component in value)  # type: ignore[return-value]


def _serialized(values: tuple[float, ...], digits: int, *, name: str) -> None:
    if any(value != round(value, digits) for value in values):
        raise ValueError(f"{name} must use at most {digits} decimal places")


@dataclass(frozen=True, order=True, slots=True)
class PassageFrame(Record):
    """Canonical serialized placement frame for a section passage."""

    origin: tuple[float, float, float]
    run: tuple[float, float, float]
    u: tuple[float, float, float]
    v: tuple[float, float, float]

    def __post_init__(self) -> None:
        origin = cast(tuple[float, float, float], _numbers(self.origin, 3, name="origin"))
        run = cast(tuple[float, float, float], _numbers(self.run, 3, name="run"))
        u = cast(tuple[float, float, float], _numbers(self.u, 3, name="u"))
        v = cast(tuple[float, float, float], _numbers(self.v, 3, name="v"))
        _serialized(origin, 3, name="origin")
        for name, direction in (("run", run), ("u", u), ("v", v)):
            _serialized(direction, 6, name=name)
        for direction in (run, u, v):
            if abs(_dot(direction, direction) - 1.0) > 1e-6:
                raise ValueError("frame directions must be unit length")
        if any(abs(_dot(a, b)) > 2e-6 for a, b in ((run, u), (run, v), (u, v))):
            raise ValueError("frame directions must be orthogonal")
        if max(abs(a - b) for a, b in zip(_cross(run, u), v, strict=True)) > 3e-6:
            raise ValueError("frame must be right handed")
        rounded = tuple(round(abs(value), 6) for value in run)
        peak = max(rounded)
        dominant = next(index for index in (2, 1, 0) if rounded[index] == peak)
        if run[dominant] < -3e-6:
            raise ValueError("frame run direction is not in the canonical gauge")
        normalized_run = _unit(run)
        seeds = ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
        seed = seeds[dominant]
        expected_u = _unit(
            tuple(
                seed[index] - _dot(seed, normalized_run) * normalized_run[index]
                for index in range(3)
            )  # type: ignore[arg-type]
        )
        expected_v = _cross(normalized_run, expected_u)
        if any(
            math.dist(actual, expected) > 3e-6
            for actual, expected in ((u, expected_u), (v, expected_v))
        ):
            raise ValueError("frame in-plane basis is not canonical")
        if abs(_dot(origin, run)) > 8e-4:
            raise ValueError("frame origin must be perpendicular to its run")
        object.__setattr__(self, "origin", origin)
        object.__setattr__(self, "run", run)
        object.__setattr__(self, "u", u)
        object.__setattr__(self, "v", v)


@dataclass(frozen=True, order=True, slots=True)
class PassageSectionVertex(Record):
    point: tuple[float, float]
    bulge: float

    def __post_init__(self) -> None:
        point = _numbers(self.point, 2, name="point")
        _serialized(point, 3, name="point")
        if isinstance(self.bulge, bool) or not isinstance(self.bulge, int | float):
            raise ValueError("bulge must be a finite number")
        bulge = float(self.bulge)
        if not math.isfinite(bulge):
            raise ValueError("bulge must be a finite number")
        _serialized((bulge,), 12, name="bulge")
        object.__setattr__(self, "point", point)
        object.__setattr__(self, "bulge", 0.0 if bulge == 0.0 else bulge)


@dataclass(frozen=True, order=True, slots=True)
class PassageSection(Record):
    boundary: tuple[PassageSectionVertex, ...]

    def __post_init__(self) -> None:
        from b123d_recognisers._sections import PlanarSection, SectionVertex

        if not isinstance(self.boundary, tuple) or not all(
            isinstance(vertex, PassageSectionVertex) for vertex in self.boundary
        ):
            raise ValueError("boundary must contain PassageSectionVertex values")
        try:
            canonical = PlanarSection(
                tuple(SectionVertex(vertex.point, vertex.bulge) for vertex in self.boundary)
            )
        except (TypeError, ValueError) as exc:
            raise ValueError("section boundary is invalid") from exc
        expected = tuple((vertex.point, vertex.bulge) for vertex in canonical.boundary)
        actual = tuple((vertex.point, vertex.bulge) for vertex in self.boundary)
        if actual != expected or math.hypot(*canonical.centroid) > 8e-4:
            raise ValueError("section boundary must be canonical and origin-centred")


@dataclass(frozen=True, order=True, slots=True)
class PassageEnds(Record):
    low_capped: bool
    high_capped: bool

    def __post_init__(self) -> None:
        if type(self.low_capped) is not bool or type(self.high_capped) is not bool:
            raise ValueError("passage end conditions must be booleans")


@dataclass(frozen=True, order=True, slots=True)
class SectionPassage(Record):
    frame: PassageFrame
    run_interval: tuple[float, float]
    section: PassageSection
    ends: PassageEnds

    def __post_init__(self) -> None:
        if not isinstance(self.frame, PassageFrame):
            raise ValueError("frame must be a PassageFrame")
        interval = _numbers(self.run_interval, 2, name="run_interval")
        _serialized(interval, 3, name="run_interval")
        if interval[1] - interval[0] <= 1e-9:
            raise ValueError("run_interval must be increasing")
        if not isinstance(self.section, PassageSection):
            raise ValueError("section must be a PassageSection")
        if not isinstance(self.ends, PassageEnds) or self.ends != PassageEnds(False, False):
            raise ValueError("SectionPassage must be open at both ends")
        object.__setattr__(self, "run_interval", interval)


class PassageCompatibilityError(RuntimeError):
    """The retired attributed legacy Passage API was requested."""


_LEDGER_ERROR = (
    "recognise_passages(..., ledger=...) is unavailable from 0.4.0; "
    "use recognise_section_passages(..., ledger=...)"
)


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

    if ledger is not None:
        raise PassageCompatibilityError(_LEDGER_ERROR)
    graph = FaceGraph(part, face_edges=face_edges)
    return _discover_passages(part, graph, None)


def recognise_section_passages(
    part: Part,
    *,
    face_edges: FaceEdges | None = None,
    ledger: ClaimLedger | EvidenceWriter | None = None,
) -> list[SectionPassage]:
    """Recognise canonical section passages, with optional defining-wall evidence."""

    graph = FaceGraph(part, face_edges=face_edges) if ledger is None else ledger.graph
    return _discover_section_passages(part, graph, None if ledger is None else ledger.sink)


def _discover_section_passages(
    part: Part, graph: FaceGraph, sink: EvidenceSink | None
) -> list[SectionPassage]:
    found: list[tuple[SectionPassage, tuple[FaceNode, ...], SolidRef]] = []
    for proposal in section_ring_proposals(part, graph):
        record = SectionPassage(
            PassageFrame(
                tuple(round(value, 3) for value in proposal.frame.origin),  # type: ignore[arg-type]
                tuple(round(value, 6) for value in proposal.frame.run),  # type: ignore[arg-type]
                tuple(round(value, 6) for value in proposal.frame.u),  # type: ignore[arg-type]
                tuple(round(value, 6) for value in proposal.frame.v),  # type: ignore[arg-type]
            ),
            tuple(round(value, 3) for value in proposal.run_interval),  # type: ignore[arg-type]
            PassageSection(
                tuple(
                    PassageSectionVertex(
                        (round(vertex.point[0], 3), round(vertex.point[1], 3)),
                        round(vertex.bulge, 12),
                    )
                    for vertex in proposal.section.boundary
                )
            ),
            PassageEnds(False, False),
        )
        if _section_projection_displacement(proposal, record) > _SECTION_SERIALIZATION_LIMIT:
            raise ValueError("section passage serialization exceeds the displacement bound")
        if graph.common_valid_solid(proposal.nodes) is not proposal.solid:
            raise ValueError("section passage body authority changed before issuance")
        proposal.body_adapter.validate(proposal.solid, proposal.occurrence)
        found.append((record, proposal.nodes, proposal.solid))
    found.sort(key=lambda pair: (pair[0].frame.run, pair[0].run_interval, pair[0].frame.origin))
    for at, (record, nodes, solid) in enumerate(found):
        for other_record, other_nodes, other_solid in found[at + 1 :]:
            if record == other_record and solid is other_solid:
                same_nodes = len(nodes) == len(other_nodes) and all(
                    any(left is right for right in other_nodes) for left in nodes
                )
                if not same_nodes:
                    raise ValueError("equal section passage proposals compete on one solid")
    if sink is not None:
        for record, nodes, _ in found:
            sink.propose(FamilyId.PASSAGES, record, defining=nodes)
    return [record for record, _, _ in found]


def _section_projection_displacement(
    proposal: SectionRingProposal, record: SectionPassage
) -> float:
    """Maximum source-to-serialized movement over every section vertex at both ends."""

    maximum = 0.0
    for source_vertex, serialized_vertex in zip(
        proposal.section.boundary, record.section.boundary, strict=True
    ):
        for source_t, serialized_t in zip(
            proposal.run_interval, record.run_interval, strict=True
        ):
            source = tuple(
                proposal.frame.origin[index]
                + source_t * proposal.frame.run[index]
                + source_vertex.point[0] * proposal.frame.u[index]
                + source_vertex.point[1] * proposal.frame.v[index]
                for index in range(3)
            )
            serialized = tuple(
                record.frame.origin[index]
                + serialized_t * record.frame.run[index]
                + serialized_vertex.point[0] * record.frame.u[index]
                + serialized_vertex.point[1] * record.frame.v[index]
                for index in range(3)
            )
            maximum = max(
                maximum,
                math.sqrt(
                    sum(
                        (left - right) ** 2
                        for left, right in zip(source, serialized, strict=True)
                    )
                ),
            )
    return maximum


def _legacy_projection(record: SectionPassage) -> Passage | None:
    """Return the exact historical principal line-polygon view when representable."""

    if any(vertex.bulge != 0.0 for vertex in record.section.boundary):
        return None
    axes = {
        (1.0, 0.0, 0.0): ("x", 1, 2),
        (0.0, 1.0, 0.0): ("y", 0, 2),
        (0.0, 0.0, 1.0): ("z", 0, 1),
    }
    try:
        axis, first, second = axes[record.frame.run]
    except KeyError:
        return None
    lo, hi = record.run_interval
    centre = [*record.frame.origin]
    axis_index = "xyz".index(axis)
    centre[axis_index] = 0.5 * (lo + hi)
    section = []
    for vertex in record.section.boundary:
        world = tuple(
            record.frame.origin[index]
            + vertex.point[0] * record.frame.u[index]
            + vertex.point[1] * record.frame.v[index]
            for index in range(3)
        )
        section.append((round(world[first], 3), round(world[second], 3)))
    canonical = _canonical(section)
    if canonical is None:
        return None
    return Passage(
        axis=axis,
        sides=len(canonical),
        length=round(hi - lo, 3),
        at=tuple(round(value, 3) for value in centre),  # type: ignore[arg-type]
        section=canonical,
    )


def _discover_passages(
    part: Part,
    graph: FaceGraph,
    sink: EvidenceSink | None,
) -> list[Passage]:
    if sink is not None:
        raise PassageCompatibilityError(_LEDGER_ERROR)
    found = [
        legacy
        for record in _discover_section_passages(part, graph, None)
        if (legacy := _legacy_projection(record)) is not None
    ]
    found.sort(key=lambda record: (record.axis, record.at))
    return found
