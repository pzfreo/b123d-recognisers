# E5 circular-end pocket gap validation

Issue [#413](https://github.com/pzfreo/b123d-recognisers/issues/413) audits every class-16
circular-end-pocket component proxy in the fixed MFCAD++-500 selection. It changes production only
for an intact blind obround whose two supported opposing ends describe one stubby recess but whose
imported centreline estimates straddle the historical two-decimal grouping boundary.

## Reproduction and authority

The immutable component audits are the
[parent](mfcadpp-class16-circular-end-pocket-audit-parent-ad27678.json) and
[implementation](mfcadpp-class16-circular-end-pocket-audit-9171a74.json) reports. Their SHA-256
digests are respectively `7ee3ace622ca4b58ada6a9e49100ebe35d25a2d222cabebee52825743693ce26`
and `ebe0d7b9b22c4bfb006c2407ef9a8d271d7f13e81a735a16a8f6836e7334e24d`.
Both pin the audit implementation, production source digests, exact lexical selection, and every
selected STEP-file digest.

```console
uv run python tools/audit_mfcadpp_circular_end_pocket_gaps.py \
  /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --class-id 16 --limit 500 \
  --output docs/benchmarks/mfcadpp-class16-circular-end-pocket-audit-COMMIT.json
```

The exact taxonomy-v8 aggregate reports are likewise the
[parent](effectiveness-mfcadpp-500-obround-centerline-parent-9bb925f.json) and
[implementation](effectiveness-mfcadpp-500-obround-centerline-9171a74.json), with SHA-256 digests
`928905f039a83ab2d7675c8f1f414cf3890958f8d64eb5f2703f3b58694baa4b` and
`cc6543b25356389c746b9fee3fb070db5e026adc7c6ebb6594ef5afe48042318`.

## Complete denominator and failure anatomy

The fixed selection contains 195 connected same-label proxies / 973 class-16 faces across 150
models. MFCAD++ has per-face classes but no native feature-instance identity, so these are explicit
component proxies rather than asserted physical occurrences.

On parent production, accepted constituent evidence touches 174 proxies / 667 faces and 21 proxies
/ 86 faces are wholly untouched. The untouched failure anatomy is:

| First failed geometric gate | Proxies | Faces |
| --- | ---: | ---: |
| Fragmented anatomy | 8 | 21 |
| Non-principal side walls | 10 | 50 |
| Not two supported semicircular ends | 1 | 5 |
| Centreline grouping mismatch after all other proofs | 2 | 10 |

Only the last two proxies are intact supported blind obrounds. Models 11124 and 12229 each have two
individually supported semicircular ends, opposed directions, joining principal-axis side walls,
exactly one floor end, and centreline deltas of 0.02826 mm and 0.01892 mm. Both deltas are inside
the existing cap-radius-scaled `_CAP_CLUSTER_FRAC` authority but fell on opposite sides of a
two-decimal centre bucket.

## Production boundary

Legacy rounded centre/radius/depth buckets retain their historical values and insertion order.
The implementation may merge only two singleton legacy buckets when there is exactly one
compatible partner, their axes and rounded radius/depth agree, the directions oppose, their
centreline delta is inside the existing radius-scaled tolerance, and their straight run is no
longer than their width plus that tolerance. Ambiguity preserves the old buckets and fails closed.

The stubby-span condition is architectural, not corpus taxonomy: end-only reconstruction exists
for recesses too short for the normal opposed-wall path. It prevents the widened grouping from
also reconstructing an elongated recess that the wall path already found. The exact imported
regression is model 10060; it retains its two historical Pockets and does not gain the nested third
record produced by the first broad implementation.

Positive and negative authored cases cover a normal stubby pocket, centreline noise on the accepted
and refused sides of the scaled tolerance, an elongated fuzzy pair, split-cap provenance, compound
ownership, and public/direct occurrence parity.

## End-to-end result

After the change, 19 proxies / 76 faces remain untouched, with exactly the same 8/10/1 unsupported
failure categories. Only models 11124 and 12229 change in normalized aggregate rows. Model 10060
and every other model are unchanged. Direct exact-source comparison additionally proves that every
pre-existing Pocket in 12229 retains its byte/value/order projection; one new Pocket is inserted.

| Metric | Parent `9bb925f` | Implementation `9171a74` | Delta |
| --- | ---: | ---: | ---: |
| Physical Pockets | 543 | 545 | +2 |
| Class-16 mapped records | 162 | 164 | +2 |
| Class-16 defining recall | 423/973 (43.47%) | 427/973 (43.88%) | +4 faces |
| Class-16 face coverage | 667/973 (68.55%) | 673/973 (69.17%) | +6 faces |
| Supported/partial face coverage | 8,369/11,244 (74.43%) | 8,375/11,244 (74.48%) | +6 faces |
| All-status face coverage | 9,125/15,170 (60.15%) | 9,131/15,170 (60.19%) | +6 faces |
| Total runtime | 278.06 s | 288.40 s | 1.037x |
| Median model runtime | 0.5240 s | 0.5451 s | 1.040x |

The two added Pocket defining sets also enter the precision denominator of every class mapped to
Pocket; only class 16 gains matching faces. This is expected many-to-many scorer accounting, not a
cross-class recognition change.

## ADR conformance

- ADR 0002: one shared direct/aggregate production path remains deterministic; public records and
  existing serialization values/order are preserved, with two evidence-backed additions only.
- ADR 0003: exact run-local face provenance and reconciliation remain unchanged; no label, traversal
  index, or record-value rematching enters production.
- ADR 0007: the change stays inside the existing private obround seam and introduces no dependency
  inversion or second recogniser.
- ADR 0008: centreline equivalence reuses the existing cap-radius-scaled tolerance. The stubby span
  is a topology/domain boundary, not a dataset-tuned tolerance, and is tested on both outcomes.
- ADRs 0009–0011: family ownership, public evidence, and the principal-axis frame contract do not
  move. Non-principal residuals remain explicitly unsupported.

MFInstSeg was neither inspected nor run for this focused increment. Its aggregate milestone remains
required when the authenticated dataset mount is available.
