# E5 one-ended Pocket enclosure audit

Issue [#456](https://github.com/pzfreo/b123d-recognisers/issues/456) tests whether the two-ended
Passage enclosure proof has a truthful one-ended analogue for residual six-sided Pockets. This is
an audit result, not recognition authority. Candidate geometry is complete before MFCAD++ labels
are read; labels only measure the resulting regions.

## Geometric question

The probe requires one complete convex inner mouth, six cyclic straight geometric sides, one
parallel terminating floor, one valid solid, an empty constant-section prism from mouth to floor,
exterior void immediately outside the mouth, and material immediately behind the floor. It
collapses only exactly co-directed subdivisions of an otherwise linear mouth boundary under the
shared dimensionless smooth-direction tolerance. A kink remains a separate side.

This is deliberately stronger than an inner-wire flood fill. A topology-only prototype admitted
six target-touching chamfer/intersection regions and one non-target mixed-feature region. The
empty-prism and closed-floor proof rejects all seven: their complete mouth section encounters
material or fails to terminate in material. Accepting them would call an interrupted section a
constant-section Pocket.

Authored controls cover a blind hexagonal Pocket, through and enclosed voids, a floor breach,
triangular and rectangular exclusions, rigid covariance, separate-body ownership, exact collinear
subdivision and a nearby kink. The audit runner preserves lexical output across one or multiple
process workers; the runtime field is intentionally measured rather than canonical.

## First-500 decision slice

The lexical 500-model MFCAD++ development slice contains 2,068 candidate cavity regions. The exact
one-ended proof accepts 130 regions; all 130 touch only class-15 faces. They reach 910 class-15
faces, but every reached face already has accepted constituent evidence from the aggregate
recogniser. **The counterfactual production gain is 0 new class-15 faces.**

| First result | Regions touching class 15 |
| --- | ---: |
| accepted geometry, already covered | 130 |
| bounded-prism/floor proof failed | 6 |
| effective boundary was not six-sided | 14 |
| mouth was not an all-line polygon | 11 |

The collinear-run experiment is informative but not an acceptance widening. Four raw eight-edge
mouths reduce to six geometric runs, but each is one of the interrupted regions rejected by the
physical prism proof. Conversely, raw six-edge rectangular and triangular mouths reduce to four
geometric runs and remain correctly outside the six-sided family.

## Full development result

The merge-candidate full-corpus result and immutable machine report will be recorded here after the
audit source is committed on top of the Passage merge.

## Decision

Unless the full development denominator contradicts the decision slice, close #456 without a
production recogniser change. The exact one-ended architecture is geometrically coherent but adds
no downstream coverage; shipping it would violate Epic #290's consumer-with-substrate rule. The
remaining class-15 misses require interrupted/chamfered membership or different feature semantics,
not relaxation of a constant-section six-sided Pocket.

This conforms to ADRs 0002, 0003, 0004, 0007, 0008, 0009, 0010, 0011 and the Passage decisions:
there is no public record, Candidate, evidence, ownership, reconciliation, schema or tolerance
change; no label participates in geometry; and no post-acceptance adjacency traversal becomes
recognition authority. MFInstSeg was not run or inspected because this is not a transfer milestone.

After a negative decision, the next effectiveness audit returns to the residual Passage refusal
buckets. The first-500 census favours the 34 class-4 faces behind planar-mouth seeding over the
72-face mouth-congruence bucket: four seed-failure regions are class-pure, while none of the
congruence failures are, so the former presents the cleaner corpus-independent hypothesis despite
the smaller raw count.
