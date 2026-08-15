# Draftwright migration parity

The initial standalone implementation is an atomic extraction from Draftwright commit
`3fe20b0f71a71deced06b310943dd44cc66e355e` (2026-08-15). There are no intentional recognition
behavior differences.

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
