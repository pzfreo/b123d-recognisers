# Fragmented circular-end Pocket assessment

Issue: #474

Baseline: `f0fdacd`

Source report: `mfcadpp-circular-end-pocket-refusals-f0fdacd.json`

SHA-256: `17ad9b84c3df8d0dd29919fc429c5de1829f0c64e0ea17a74d58461044458427`

## Decision

Do not add a fragmented-obround `Pocket` rule under the current record contract. A revised query,
prompted by aggregate-only MFInstSeg evidence, shows that MFCAD++ does contain many complete
two-cylinder/three-plane proxies, but almost all already reach the production Pocket proposal.
The corpus contains only four untouched principal-axis declines / 20 faces. That is too small and
too interrupted to stand in for the materially larger transfer residual.

No MFInstSeg model was inspected. Owner-supplied aggregate MFInstSeg results establish priority
and expose this corpus mismatch only; they do not supply geometry rules.

## Revised refusal-conditioned evidence

The original assessment asked only whether the 53 untouched `fragmented_anatomy` proxies retained
the complete local template. That negative result remains correct, but it did not justify the
broader inference that MFCAD++ could not describe obround refusal anatomy. The format-v2 audit now
examines every class-16 component after the aggregate Candidate inventory has been built, then
selects the 776 proxies containing exactly two cylindrical and three planar faces.

| current outcome or first failed gate | proxies | untouched proxies |
| --- | ---: | ---: |
| Current Pocket proposal | 682 | 0 |
| Non-principal side walls | 71 | 57 |
| Not two supported semicircular ends | 20 | 3 |
| Incompatible end pair | 2 | 0 |
| Centreline grouping mismatch | 1 | 1 |

The 94 declines contain 470 faces, but 90 of them are either non-principal or already touched by
accepted evidence. All 20 `not_two_semicircular_ends` proxies have one accepted end and one
cylinder whose bounds do not establish exactly one diameter extent. Only three are untouched. The
one centreline mismatch adds five faces. This answers the revised question: MFCAD++ can
characterise the refusal, but it has almost no principal-axis untouched population on which to
derive and measure the transfer correction.

## Original fragmented-residual evidence

The full 2,500-model selection still contains 53 untouched connected class-16 component proxies /
166 faces at `fragmented_anatomy`. Decomposing the report's geometric probe fields gives:

| condition | component proxies |
| --- | ---: |
| missing the required two cylindrical ends | 41 |
| missing the required three planar members | 43 |
| missing at least one of those requirements | 53 |
| zero or one cylindrical end | 37 |
| retaining two individually supported semicircular ends | 1 |

Thus every fragmented proxy lacks an essential part of the bounded obround proof. This is not a
failure to join split coplanar or coaxial patches: `_obround_ends` already inventories and groups
original patches across the whole source solid, independently of dataset components, and the
audit found zero overlap between any untouched proxy and an existing Pocket proposal.

## Architectural boundary and next evidence

The existing `Pocket` record promises a complete width, overall length, centreline, longitudinal
bounds, depth interval and opening direction. A cavity with one end erased by an intersection does
not geometrically establish that closed footprint. The three untouched partial-end cases confirm
this directly: the accepted cylinder meets both parallel side walls smoothly, while the clipped
cylinder meets only one; the missing boundary was removed by an intersection. Extending that
cylinder into a closed `Pocket` footprint would invent geometry.

A future implementation must therefore use a truthful open/interrupted curved-profile record and
separately justify its ownership, or use another inspectable open/real evidence source containing a
material population. Silently relaxing the semicircle ratio would conflict with ADRs 0002, 0003,
0004, 0008 and 0010.

This result does not claim that circular-end recognition is complete or that the MFInstSeg transfer
gap is spurious. Aggregate MFInstSeg evidence reports the two-cylinder/three-plane anatomy much
more often than the untouched MFCAD++ slice. No individual MFInstSeg model was inspected. The
mismatch is recorded as a limitation of the development corpus, not used as authority for a
production predicate.

## Reproduction

```console
uv run python tools/audit_mfcadpp_circular_end_pocket_gaps.py \
  /path/to/MFCAD++_dataset/step/test \
  --class-id 16 --limit 2500 --allow-invalid \
  --output /tmp/mfcadpp-circular-end-pocket-refusals.json
```

The report pins all 2,500 selected source hashes, the known invalid-model policy, production-source
hashes, exact per-component evidence, and every numerator reported above.
