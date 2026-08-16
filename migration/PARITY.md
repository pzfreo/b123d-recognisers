# Draftwright migration parity

The initial standalone implementation is an atomic extraction from Draftwright commit
`3fe20b0f71a71deced06b310943dd44cc66e355e` (2026-08-15). Through `0.2.0`–`0.2.2` there were no intentional
feature-policy differences.

**From `0.2.3` there is one, and it is deliberate.** It is carried on a patch release at the
maintainer's direction rather than the minor release semver would imply; on a `0.x` line the
distinction is a project convention, and this records which convention was chosen. [ADR 0008](../docs/adr/0008-length-tolerance-policy.md)
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

## Intentional divergence from the capture

| Release | What differs | Extent |
| --- | --- | --- |
| 0.2.3 | `RiserEvidence.tol` records the tolerance the scan actually resolved for that part, rather than the former fixed `0.5`. | 33 values across 5 fixtures. **No geometry field moves** — not one coordinate, span, diameter, count or classification differs from the capture. |

That field exists to report how the evidence was produced, so it moves precisely because the
production changed; a record still carrying `0.5` would now be misreporting. The rest of the corpus
is bit-identical to the Draftwright capture, which is the claim worth keeping and the reason the
divergence is stated as a table rather than a re-capture.

`RiserEvidence.tol` also loses its default. Its whole purpose is to record a scanned value, so
there is no honest default to fall back on; direct constructors must now pass it.

The compatibility normalization below (dominant-axis tie-break) predates this and is unrelated.

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
