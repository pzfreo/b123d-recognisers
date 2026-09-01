# E5 cavity-enclosure audit

Issue #418 tests the shared-root hypothesis in #415 without changing recognition. The exact
production and audit source is `7db2b2b30901abd4a521e7193045f411d0a2cd4b`; the report covers
the first 500 lexical MFCAD++ test models (469 contain classes 2, 3, 4, 13, 14, 15 or 16).
Labels are read only after candidate construction.

## Geometric rule

Each inner wire seeds the faces adjacent through its exact edge occurrences. A region expands
only over proved concave or smooth graph arcs, never across solids. Identical regions from two
openings are deduplicated while retaining both opening faces. This is an audit approximation,
not recognition or constituent authority.

Authored controls cover blind and through cavities, multiple cavities, intersecting cavities,
separate bodies, a general rigid transform and deterministic report ordering. All five tests
pass. Ruff is clean.

## Full-denominator result

- 6,532/6,661 target faces and 1,288/1,315 same-label component proxies are reached.
- All 1,987 candidate regions are same-solid and none captures a whole body.
- 1,305 regions touch a target class; 1,130 are class-pure target regions.
- 11 regions have tied target-class face counts and remain explicitly ambiguous.
- 79 target components are fragmented and 68 regions merge multiple target components.
- 872 regions have both one target component and one accepted Pocket/Passage occurrence.
- 890 regions have a bidirectionally unique accepted-occurrence association.
- Accepted-occurrence reach is 282/282 Passages, 325/325 Prismatic Pockets and 335/533 Pockets.
  The Pocket denominator also contains family shapes outside these seven cavity classes.
- Runtime is 301.36 seconds.

The high reach does not establish a generic ownership rule. There are 682 non-target-only regions,
including holes and O-rings, 191 mixed-label regions, and material merge/fragmentation. Corpus
class agreement is evaluation evidence, not a production discriminator.

## Decision

The substrate is strong enough to continue only at existing acceptance sites. A follow-on may
retain a bounded region as constituent evidence when the accepted recogniser proof establishes a
unique same-solid occurrence-to-region relationship. It must refuse ambiguous, merged,
fragmented, intersecting and whole-body cases. A later adjacency flood-fill, label-directed
mapping, generic public cavity recogniser, or transfer of ownership to constituent evidence is not
supported by this audit and would conflict with ADRs 0002, 0003, 0004, 0007 and 0010.

The first production slice should remain the two named Pocket consumers (rectangular and
circular-end), with exact accepted-occurrence identity carried through their existing neutral
provenance. Passage detection gaps remain separate work; their 100% accepted-occurrence reach does
not turn missed corpus regions into accepted features.

The report records an aggregate hash over all 500 selected STEP sources and an aggregate hash over
all 68 production Python sources, alongside every evaluated model's source hash.

Machine evidence: [`mfcadpp-cavity-enclosure-audit-7db2b2b.json`](mfcadpp-cavity-enclosure-audit-7db2b2b.json).
