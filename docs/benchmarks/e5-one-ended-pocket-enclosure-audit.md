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

The immutable report is
[`mfcadpp-one-ended-pocket-audit-f06a470.json`](mfcadpp-one-ended-pocket-audit-f06a470.json),
SHA-256 `4599d22fa8886df47de38f7b4ccec99b1d1d646a09a18e02833238e410e83232`. It
records audit source `f06a470307035dfb2a3787478ff40969e628cdca`, on top of the #455 merge,
the published dataset identity, all 2,500 selected model/source hashes, and the exact seven-invalid
policy shared with the effectiveness runner. All seven IDs and the expected
`Hole cylindrical evidence does not prove one valid solid` reason match.

```console
uv run python tools/audit_mfcadpp_one_ended_pockets.py \
  /path/to/MFCAD++_dataset/step/test \
  --limit 2500 --workers 4 --allow-invalid \
  --output /tmp/mfcadpp-one-ended-pocket-audit.json
```

Across 2,493 valid models, the audit evaluates 10,108 cavity regions. The exact rule accepts 647;
every accepted region is class-15-pure. They reach 4,529 class-15 faces, but once again **zero are
new** relative to accepted aggregate constituent evidence.

| First result | All regions | Regions touching class 15 |
| --- | ---: | ---: |
| accepted geometry, already covered | 647 | 647 |
| bounded-prism/floor proof failed | 39 | 36 |
| effective boundary was not six-sided | 2,288 | 71 |
| mouth was not an all-line polygon | 2,994 | 43 |
| no unique mouth | 3,923 | 0 |
| no unique floor plane | 217 | 0 |

Four workers complete the run in 541.60 seconds. This is audit-cycle latency, not a production
recogniser performance result.

## Decision

Close #456 without a production recogniser change. The full development denominator confirms the
decision slice: the exact one-ended architecture is geometrically coherent but adds no downstream
coverage, so shipping it would violate Epic #290's consumer-with-substrate rule. The
remaining class-15 misses require interrupted/chamfered membership or different feature semantics,
not relaxation of a constant-section six-sided Pocket.

This conforms to ADRs 0002, 0003, 0004, 0007, 0008, 0009, 0010, 0011 and the Passage decisions:
there is no public record, Candidate, evidence, ownership, reconciliation, schema or tolerance
change; no label participates in geometry; and no post-acceptance adjacency traversal becomes
recognition authority. MFInstSeg was not run or inspected because this is not a transfer milestone.

The negative result retires the complete-mouth template rather than the broader Pocket priority.
Issue #460 follows with a different geometric hypothesis: interruption-tolerant propagation from
an inner-loop seed across one same-solid physical cavity, with explicit termination and branching
refusals. That work measures newly detected occurrences separately from wider membership on
existing occurrences; rectangular Pocket membership remains a distinct residual because its
aggregate transfer miss is predominantly partial rather than undetected. Passage improvements may
resume after this higher-value Pocket test, but are no longer the immediate conclusion of this
audit.
