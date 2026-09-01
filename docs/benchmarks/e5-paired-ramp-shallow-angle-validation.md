# E5 paired-ramp shallow-angle validation

Issue [#89](https://github.com/pzfreo/b123d-recognisers/issues/89) closes a presentation-angle
gap in the existing `PairedRampStep` family. The shared Chamfer reader deliberately rejects a
shallow draft-like plane as aligned. A paired through-step does not depend on Chamfer semantics:
its two original planes must still prove mirror symmetry, one complete concave ridge, one convex
stock-envelope terminal, one concave internal planar terminal, a side opening, exact run span and
one valid solid.

## Contract

The family-local ramp read accepts a planar face only when its normal has exactly one zero
component within the existing dimensionless smooth-direction tolerance. Exact principal planes
have two zero components and remain excluded; free-axis planes have none and remain excluded.
There is no minimum ramp angle and no corpus-derived threshold. Every downstream acceptance and
evidence proof is unchanged, and Chamfer continues to apply its own draft-angle exclusion.

Authored tests cover a shallow pair rejected by the Chamfer reader, the exact-principal boundary,
both sides of the existing direction tolerance, the existing free-axis refusal, X/Y/Z covariance,
translation, scale, traversal, STEP, material-side, terminal, ridge, split-face and compound
ownership contracts.

## MFCAD++ development result

The exact lexical 500-model reports are
[`effectiveness-mfcadpp-500-paired-shallow-parent-a74344f.json`](effectiveness-mfcadpp-500-paired-shallow-parent-a74344f.json)
(SHA-256 `d7f55a33040c71a29caf99a2b163377e71d9b901c53d40e7011c6c6f4e875264`)
and
[`effectiveness-mfcadpp-500-paired-shallow-4b612d0.json`](effectiveness-mfcadpp-500-paired-shallow-4b612d0.json)
(SHA-256 `bd98e9b89a4d63dab98c37a3432705e2f91b538ce8078b55eee61e44dfc6cf03`).
They use taxonomy v9 hash
`e97995053d2db6089442a3b87868117ff9114f74a0c8ab15896cd343ef80fe51`,
the same published lexical selection hash
`323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`,
raw recognition, Python 3.12.14, build123d 0.11.1 and OCP 7.9.3.1.

| Measure | Parent | Candidate |
| --- | ---: | ---: |
| `PairedRampStep` occurrences | 64 | 90 |
| class-9 matched / mapped defining faces | 192 / 192 | 270 / 270 |
| class-9 defining recall | 192 / 592 (32.43%) | 270 / 592 (45.61%) |
| class-9 face coverage | 392 / 592 (66.22%) | 440 / 592 (74.32%) |
| evaluated / invalid / empty models | 500 / 0 / 0 | 500 / 0 / 0 |
| descriptive total runtime | 313.74 s | 275.60 s |

Label-independent discovery adds 26 occurrences across 25 models. All 78 new defining faces map
to class 9; existing physical records, mapped records, reconciliation drops, mismatch counts and
all non-class-9 score fields are unchanged after excluding timing and the new paired-ramp values.
MFCAD++ labels measure the result but do not participate in the ramp read or any acceptance gate.
Runtime is recorded for completeness but is not treated as a performance result: the functional
epic deliberately defers optimization and these sequential process runs are not a controlled
paired benchmark.

MFInstSeg was not inspected or run for this increment. Its aggregate result selected the broad
through-step priority only; no transfer-model anatomy shaped this contract.

## Architecture

ADRs 0002, 0003, 0004, 0007, 0008, 0009 and 0011 were reviewed before implementation. The change
keeps one writer-enabled family core, exact original-face evidence, one valid-solid authority and
unchanged reconciliation. The family-local read follows ADR 0009: Chamfer's family-specific angle
policy is not promoted to a neutral filter for another physical family. Final-diff conformance and
one bounded independent contract review are required before merge.
