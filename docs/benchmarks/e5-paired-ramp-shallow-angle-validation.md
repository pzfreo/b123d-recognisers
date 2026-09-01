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

The exact lexical 500-model parent/candidate reports use taxonomy v9 and the same published test
selection. The final immutable filenames and hashes are recorded after final-head regeneration.

| Measure | Parent | Candidate |
| --- | ---: | ---: |
| `PairedRampStep` occurrences | 64 | 90 |
| class-9 matched / mapped defining faces | 192 / 192 | 270 / 270 |
| class-9 defining recall | 192 / 592 (32.43%) | 270 / 592 (45.61%) |
| class-9 face coverage | 392 / 592 (66.22%) | 440 / 592 (74.32%) |
| evaluated / invalid / empty models | 500 / 0 / 0 | 500 / 0 / 0 |
| total runtime | 313.74 s | 320.08 s (1.020x) |

Label-independent discovery adds 26 occurrences across 25 models. All 78 new defining faces map
to class 9; existing physical records, mapped records, reconciliation drops, mismatch counts and
all non-class-9 score fields are unchanged after excluding timing and the new paired-ramp values.
MFCAD++ labels measure the result but do not participate in the ramp read or any acceptance gate.

MFInstSeg was not inspected or run for this increment. Its aggregate result selected the broad
through-step priority only; no transfer-model anatomy shaped this contract.

## Architecture

ADRs 0002, 0003, 0004, 0007, 0008, 0009 and 0011 were reviewed before implementation. The change
keeps one writer-enabled family core, exact original-face evidence, one valid-solid authority and
unchanged reconciliation. The family-local read follows ADR 0009: Chamfer's family-specific angle
policy is not promoted to a neutral filter for another physical family. Final-diff conformance and
one bounded independent contract review are required before merge.
