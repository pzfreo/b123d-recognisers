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
