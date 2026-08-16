# Draftwright migration parity

The initial standalone implementation is an atomic extraction from Draftwright commit
`3fe20b0f71a71deced06b310943dd44cc66e355e` (2026-08-15). Through `0.2.0`–`0.2.2` there were no intentional
feature-policy differences.

**`0.2.3` introduced one and `0.2.4` withdrew it**; see below. The line remains free of
intentional feature-policy differences. [ADR 0008](../docs/adr/0008-length-tolerance-policy.md)
replaces the recognisers' absolute millimetre gates with gates proportional to the geometry they
judge, because an absolute gate answers differently for the same feature modelled at another size.
The pinned goldens are no longer a byte-for-byte capture of the Draftwright baseline; they are this
package's own reviewed baseline, and the divergence from the capture is recorded below rather than
left implicit.

One compatibility normalization is explicit: when two or more direction components differ by no
more than `1e-12`, dominant-axis routing deterministically prefers Z, then Y. OCCT perturbs an exact
45° diagonal by a final bit in opposite directions on Windows and Unix, so Draftwright's prior
unqualified `max()` could route equivalent geometry to different inventories. The stable tie-break
matches the pinned golden result and changes only that previously platform-dependent case.

## Divergence, and its withdrawal

`0.2.3` diverged from the capture in one field: `RiserEvidence.tol` reported the tolerance its
scan resolved rather than a fixed `0.5`. `0.2.4` withdrew the change that caused it, so **every
`expected.json` is byte-identical to the Draftwright capture again** and the parity claim above
holds without qualification.

The withdrawal was not cosmetic. Scaling minimum-evidence thresholds to the part lost records on
six real parts in nineteen places with no compensating gain; see ADR 0008 on why a threshold is
not a tolerance.

The pinned corpus is bit-identical to the capture, which is what this page certifies. Behaviour on
*arbitrary* geometry is not identical to `0.2.2`, and deliberately so: `0.2.x` also replaced
grid-cell grouping of coplanar faces with grouping by distance, so a pair of faces closer together
than the tolerance is now one level rather than two. That difference is visible on real parts
outside the corpus and is a defect being fixed, not parity being lost.

## Evidence

- `migration/source-baseline.json` identifies every extracted source blob, the limited shared
  geometry-helper boundary, provenance, and the copyright owner's Apache-2.0 relicensing grant.
- Seventeen synthetic fixtures exercise every public `recognise_*` family with positive evidence,
  all shared substrates, both aggregate classification modes, and `feature_census`.
- Each fixture's `expected.json` was captured from the clean pinned Draftwright worktree. Package
  tests compare standalone output to those immutable semantic goldens after stable canonicalization.
- The traversal-order fixture constructs equivalent topology through different operation orders;
  both Draftwright capture and standalone tests require identical canonical output.
- Ported tests cover record immutability/serialization, signatures, dependency injection, aggregate
  orchestration, and historical edge regressions independently of the golden corpus.
- Wheel tests verify all runtime modules, `py.typed`, and licence notices, then import the installed
  wheel from outside the repository.

The goldens intentionally compare semantic record projections rather than STEP bytes, OCCT object
identity, or Python representations. Environment paths and build123d/OCP objects are rejected by
the corpus guards.

## Performance

`tools/benchmark_recognition.py` runs complete semantic snapshots for four representative fixtures:
patterns, prismatic edge treatments, plate/level features, and turned features. A sequential local
seven-run comparison on the migration environment produced:

| Implementation | Median seconds |
| --- | ---: |
| Pinned Draftwright | 1.9913 |
| Standalone package | 1.7326 |

The package median was 0.870× the pinned baseline (13.0% faster); therefore the extraction shows no
material regression. Raw samples and reproduction commands are in `performance-baseline.json`.
Timing is recorded as review evidence rather than a brittle wall-clock CI assertion; the existing
fillet adjacency regression uses a deterministic algorithmic-operation bound in CI.
