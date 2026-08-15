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

