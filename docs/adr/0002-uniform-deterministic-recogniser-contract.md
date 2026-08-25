# ADR 0002 — Uniform deterministic recogniser contract

- **Status:** Accepted
- **Date:** 2026-08-15
- **Decider:** Paul Fremantle

## Context

Recognition functions historically differed in naming, signatures, return shapes, dependency
handling and serialization. Draftwright ADR 0013 established and mechanically tested a uniform
contract before extraction.

## Decision

A base recogniser has this shape:

```python
recognise_<feature>(part, *, <tuning>, <injected evidence>) -> list[RecordType]
```

A derived recogniser is a pure function of records already produced:

```python
recognise_hole_patterns(holes) -> list[PatternRecord]
```

Every public recognition record is a typed frozen dataclass, contains only serialisable geometry
values, and provides a stable dictionary projection. Empty means confidently absent within the
recogniser's documented supported domain; ambiguity or unsupported topology is diagnostic output,
not an empty-list alias.

Recognisers are deterministic with respect to equivalent input geometry and configured tolerance.
They do not call sibling recognisers. The orchestration layer computes reusable evidence once and
injects it, preventing duplicate work and divergent feature universes.

Public spelling uses British `recognise_`. Low-level substrates may use precise non-recogniser
verbs such as `analyse_cylinders` because they return evidence rather than accepted features.

## Required guards

- Signature and return-annotation tests enumerate every public `recognise_*` function.
- Returned records are frozen and JSON-serialisable without build123d/OCP objects.
- Permuting kernel traversal order does not alter deterministic record ordering.
- A mutation test proves each injected dependency is used rather than recomputed.

## Consequences

The contract favours predictable composition over one-off convenience. An aggregate that appears
too small for a list must receive a self-contained record, not a special return shape.

## Amendment (0.2.6, epic 0002)

**The declared shape has no slot for a write-only sidecar, and seven recognisers now take one.**

`recognise_slots`, `recognise_pockets`, `recognise_passages`, `recognise_grooves`,
`recognise_turned_steps`, `recognise_chamfers` and `recognise_angled_steps` accept
``ledger: ClaimLedger | None = None``. It is neither tuning nor injected evidence: nothing is read
from it, and the recogniser writes into it. It is the only mutable parameter in the contract, and
a parameter kind used seven times should be named rather than left to resemble the two it is not.

The shape is therefore:

```python
recognise_<feature>(part, *, <tuning>, <injected evidence>, <claim sidecar>) -> list[RecordType]
```

with three properties that keep it inside this record's determinism guarantee rather than beside
it:

- **Write-only during discovery.** A recogniser appends and never reads back, so no family's
  output can depend on which families ran first. This is what keeps the sidecar compatible with
  ADR 0003's separation of discovery from reconciliation, and it is why the parameter is not
  "injected evidence" -- evidence flows in, claims flow out.
- **Passing it changes nothing about the return value.** Each family's claim tests assert this
  directly, calling with and without a ledger and comparing.
- **A mispaired ledger is refused, not silently ignored.** `FaceGraph.require_node` raises rather
  than resolving nothing, because an empty ledger reads downstream as "this family claims nothing"
  rather than as "you paired the wrong graph".

## Required guards, added

- A recogniser offering the sidecar returns the same records with and without it.
- Its claims name the faces the record was **established by** -- asserted against the geometry
  those faces have, not against a captured count.
- A ledger built from a different part is refused.

## F5 defining-attribution migration

Newly migrated attribution uses one private writer-enabled core while the supported public wrapper
invokes the same core without a writer. Across those independent calls parity means record type,
value, order and `to_dict()`, not Python identity. Within the writer-enabled run each Candidate must
retain the exact returned record occurrence; equal-valued occurrences remain identity-distinct.

`recognise_flats` is the first family using this shape without adding a public sidecar parameter.
Its private core completes discovery, sizing, sorting and every original-face/common-solid binding
before publishing any Candidate. The public wrapper calls that core without a sink and retains its
exact signature and byte/value/order behaviour. The owning planar face is defining; the matched
cylinder and an optional opposed flat contribute sizing as consulted context.

`recognise_fillets` follows the same private-core shape without adding a public sidecar. Its
writer-enabled aggregate call and writer-free public call preserve every existing keyword and
record value/order. The core completes both cylinder and torus discovery, final sorting and all
owner-face/common-solid validation before publishing. Each Candidate retains the exact returned
record occurrence and only its original curved blend face as defining evidence.

`recognise_countersinks` uses the same shape. On valid closed-solid inputs, its geometry-only
public facade and private writer-enabled core preserve record type, value, order and `to_dict()`;
each same-run Candidate retains exact returned-record identity. Open or ambiguous topology may
remain publicly recognised for compatibility while aggregate evidence refuses before publication.

`recognise_bosses` follows without introducing a canonical sort: its private core preserves the
existing `_segments(external)` emission order in both writer-free and writer-enabled calls. Each
same-run Candidate is identity-bound to that returned occurrence and contains the complete
graph-deduplicated set of original external cylinder faces in its producing segment. Every pending
set binds to one valid solid before the first publication; end-classification faces remain transient
consulted context. Equal-valued Boss records from distinct valid bodies remain distinct occurrences.

`recognise_double_d_bores` likewise delegates to one private optional-writer core without changing
its public signature or geometry-only behavior. On valid issuable solids, writer-free and aggregate
runs preserve record type, value and current sorted order; each aggregate Candidate is identity-bound
to the exact returned occurrence. The defining set contains every original planar/cylindrical
lateral wall patch in the proven constant Double-D extrusion. Extremal stock planes, opening wires,
per-solid extrema and the empty-prism boolean remain consulted throughness/serialization facts.
## Amendment (Polygonal Boss attribution, issue #218)

`recognise_polygonal_bosses` remains the public writer-free facade over one private discovery
core.  Writer-free and aggregate calls share the same records, stable ordering and serialization;
aggregate Candidates retain the exact returned record occurrences rather than rematching equal
values.  A Polygonal Boss owns exactly the six original vertical side faces in its accepted ring.
Terminal, support and transition caps remain consulted geometry and are never defining evidence.
`PolygonalStock` remains a separate public record and attribution family.

`recognise_rectangular_pads` follows the same private-core contract. Its public facade remains
geometry-only and preserves the existing per-solid value deduplication and global record sort. Each
issuable occurrence owns exactly five pairwise-distinct original faces: the accepted +Z top and the
unique maximal-base x0, x1, y0 and y1 wall-role faces. Tier regions, stock extrema and unselected
wall/top candidates remain consulted. Equal values with conflicting ordered role identities refuse
aggregate publication rather than being rematched by value.

## Amendment (Hole attribution, issue #220)

`recognise_holes` follows the private optional-writer contract. A completed Hole occurrence owns
the complete graph-deduplicated set of original internal cylindrical patches that establish its
bore, selected near-side counterbore/spotface lands, and any blind deep-extension span. End planes,
drill-point cones, shoulder transitions, skipped grooves, crossing faces and far-side steps remain
consulted. A nested countersink is an identity-linked completed COUNTERSINKS predecessor: its cone
remains defining only for that predecessor and is never copied into HOLES evidence.

## Amendment (Channel attribution, issue #225)

An aggregate Channel owns exactly the two original planar side walls that establish its width:
the geometrically low inward-facing wall followed by the geometrically high inward-facing wall.
Floors, caps, envelope ends, curved interruptions and other wall pairs remain consulted. Discovery
carries these wall identities through the existing per-solid exact-value reduction and global
geometry sort; competing wall pairs for one value refuse aggregate publication rather than being
rematched from the rounded record.

## Amendment (Plate attribution, issue #228)

An aggregate Plate owns the complete original low-negative and high-positive planar face clusters
whose adjacent events establish its record. Every cluster member remains defining because its area
and centroid contribute to admission or the weighted `u`/`v` projection. Other groups, bbox facts
and TURNED_STEPS records remain consulted. Whole-part grouping that mixes bodies raises the private
`_PlateAttributionError` before issuance or family completion; public geometry-only output remains
unchanged for that bounded unsupported case.
