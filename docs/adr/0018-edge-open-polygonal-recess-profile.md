# ADR 0018 — Preserve an edge-open polygonal recess as an open profile

- **Status:** Accepted
- **Date:** 2026-09-03
- **Issue:** #476

## Context

A blind prismatic recess can meet an exterior stock face along one side of its cross-section.
Its surviving planar walls form an open chain from one point on that exterior face to another;
the axial run is still bounded by one floor and one tool-accessible mouth. MFCAD++ class 15
contains this geometry, and a bounded prototype found four such proxies / 27 faces in the first
500 lexical development models.

Closing the two chain endpoints by intersecting their supporting planes produces a polygon that
extends outside the source body. In representative model `10550`, the reconstructed axial prism
is empty but only 95.1% of its nominal floor footprint is material-backed. Publishing that value
as `PrismaticPocket.section` would claim an absent wall, an absent floor region and a closed
cross-section that the part does not contain.

`PassageSection` cannot truthfully carry this profile. Its contract requires a canonical,
origin-centred closed boundary. The rectangular analogue, `RectangularBlindSlot`, records the
three physical walls of its U-section rather than inventing a fourth wall.

## Decision

Add a sibling physical family and immutable record for an edge-open prismatic recess. It does not
extend or weaken `PrismaticPocket`.

The public profile contains:

- an ordered open chain of the exact section vertices at the physical planar wall junctions;
- both exact endpoints where the chain meets one planar exterior opening face; and
- an explicit opening gap naming those endpoints, identified as absent wall rather than as a
  geometric segment between them.

The opening gap is serialized even though its endpoints repeat the chain endpoints. That
redundancy makes the semantic distinction machine-readable: consumers must not infer that the
last-to-first span is another wall or even a straight boundary. Construction validates that the
opening endpoints equal the chain endpoints in the declared direction.

The occurrence additionally carries the principal run axis, floor-to-mouth interval and axial
opening sign in the supplied recognition frame. Section coordinates remain in the two other axes,
as for `PrismaticPocket`; they are not translated to a fictional closed-profile centroid.

Recognition requires one valid solid, one nonbranching chain of at least three original planar
wall supports, exactly one planar exterior opening face joining its endpoints, one exact floor,
one axial mouth, an empty physical sweep and complete material backing behind the exact surviving
floor face. The exterior face and opening gap are consulted context. Original wall supports
are defining evidence; the exact walls and floor are constituent evidence. No inferred closing
corner, closing segment, exterior air, graph node or durable face identity enters the public
record.

The open chain has one deterministic orientation. Compare the serialized forward and reversed
chains, with the opening direction reversed correspondingly, and retain the lexicographically
smaller representation. Equivalent traversal, STEP presentation and rigid framing therefore do
not change the record.

## Refusals

Recognition refuses multiple lateral openings, curved or nonplanar openings, branches, missing or
parallel endpoint supports, self-intersecting chains, multiple floors or axial mouths, through or
enclosed regions, floor breaches, whole-body capture, ambiguous shared cavities and cross-solid
walks. It does not infer historical design intent beyond the observed physical open profile.

## Consequences

Consumers can distinguish a closed prismatic pocket from a laterally open recess without probing
faces or treating a synthetic edge as material. Draftwright may initially report the new family
as an explicit unsupported requirement; consuming it later requires a new IR mapping, not a
change to existing `PrismaticPocket` handling.

The family receives its own registry identity, result field, evidence contract, capability entry
and taxonomy mapping. Existing record schemas and outputs remain unchanged. Corpus face coverage
may map the family to a dataset Pocket class, but family-specific occurrence counts remain
separate so taxonomy agreement cannot hide the physical distinction.

ADRs 0002, 0003, 0004, 0007, 0008, 0009, 0010 and 0011 remain in force.
