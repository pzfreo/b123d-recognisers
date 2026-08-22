# ADR 0007 — Internal recogniser module seams

- **Status:** Accepted
- **Date:** 2026-08-16
- **Review:** `b123d-recognisers` issue #21

## Context

`_features.py` combines the cylinder face scan, hole/boss interpretation, and pure pattern
geometry. `slots.py` likewise combines wall/floor scanning, slot/pocket/channel interpretation,
and pure pattern geometry. The runtime orchestrator already computes cylinder and feature
inventories once and injects them into consumers, but those file boundaries conceal that flow and
make changes to one family appear coupled to the others.

The split must be mechanical. ADR 0001's standalone geometry-only boundary and ADR 0002's
single-inventory recogniser contract remain authoritative. In particular, moving code must not add
a scan, change a record, reorder a result, or create another public import path.

## Dependency graph before the move

The two oversized modules currently contain these acyclic logical layers:

```text
_features.py
  cylinder substrate: analyse_cylinders -> full_cylinders
  hole/boss layer:    cylinder substrate -> recognise_holes / recognise_bosses
  pattern layer:      HoleRecord -> shared 2-D pattern geometry -> recognise_hole_patterns

slots.py
  wall/floor core:    one planar/cylindrical face inventory and candidate geometry
  recess layer:       wall/floor core -> recognise_slots / recognise_pockets / recognise_channels
  pattern layer:      Slot/Pocket records -> shared 2-D pattern geometry
```

`result.py` owns orchestration and is the only place that creates the shared cylinder inventory.
The pocket/slot pattern code currently imports generic pattern helpers lazily from `_features.py`;
that reverse-looking dependency is the seam to remove.

## Decision

Use private implementation modules and retain `_features.py` and `slots.py` as compatibility
facades. The post-move graph is:

```text
_geometry / _record / _typing
          |
          +--> _cylinder_substrate
          |          |
          |          +--> _hole_features
          |
          +--> _pattern_geometry
                     |       |
                     |       +--> _hole_patterns
                     |       +--> _recess_patterns
                     |
          +--> _recess_faces --> _recess_reduce --> _recess_obround
                                            |             |
                                            +------+------+
                                                   v
                                            _recess_core --> _recess_features

_features.py  --> _cylinder_substrate + _hole_features + _hole_patterns
slots.py      --> _recess_features + _recess_patterns
```

`_pattern_geometry` is record-agnostic and performs no topology scan. `_cylinder_substrate`
performs the sole cylinder-face inventory scan. The recess group performs the shared wall/floor
candidate work used by the three recess recognisers, in four layers -- see the amendment below. Family modules interpret injected/shared
evidence; they do not call sibling recognisers.

All new modules are private. Existing root imports, facade imports, object identity, signatures,
record serialization, and `__module__` values remain compatible. The compatibility facades contain
re-exports only; they are not second implementations.

## Enforced boundaries

Architecture tests derive the package import graph and reject cycles, any Draftwright import, and
any unreviewed public module. They also assert the allowed internal dependency edges and facade/root
symbol identity. Orchestration tests continue to count the cylinder substrate once, while exact
goldens, determinism tests, benchmarks, and installed-archive audits protect behavior and artifacts.

## Consequences

- A hole/boss change no longer shares a file with generic pattern allocation, and a recess-family
  change no longer shares a file with its pure pattern interpretation.
- Shared geometry stays shared: neither recogniser families nor their pattern modules duplicate a
  topology scan.
- The installed wheel gains private implementation files but no public module or symbol. This is an
  internal patch-level change; it does not alter the capability manifest or recognition policy.

## Amendment (0.2.6, issue #127 item D)

`_recess_core` reached 1,200 lines carrying four responsibilities, which is the maintenance
hotspot this record's own consequences section was meant to prevent. It is now four modules,
split by responsibility rather than by family, because the three recess families share almost
everything below their candidate predicates and share nothing above them:

| Module | Owns |
| --- | --- |
| `_recess_faces` | the face read, the candidate end/floor probes, and the coincidence bands |
| `_recess_reduce` | merging, collapsing and body-scoping candidates into features |
| `_recess_obround` | cylindrical end caps, and the slots and pockets recovered from them |
| `_recess_core` | what a slot, a pocket and a channel each are, given those three |

The layering is strict and downward, and the architecture tests assert it edge by edge rather
than merely rejecting cycles. That is the property the split was for: a predicate belonging to
one family cannot quietly become substrate for the other two without the import map saying so.

No public symbol, signature, record value or `__module__` changed, and the split is verified
byte-identical over the whole corpus. It remains an internal patch-level change, exactly as
this record's consequences describe.

## Amendment (edge-anchored Pocket evidence)

`_profile_regions` is a lower factual geometry layer, not an open-profile family: it normalizes
direct coplanar graph regions and derives their actual sewn boundary, bounds, shared edges, and
uniform AAG relation. `_recess_core` may consume those facts when a family predicate needs to
prove a logical planar region, just as the curved-profile recognisers do. Feature meaning remains
above that seam: `_profile_regions` does not know what a Pocket or any other public record is.

The import map therefore permits `_recess_core -> _profile_regions`. The reverse edge remains
forbidden, and discovery/reconciliation ownership is unchanged.
