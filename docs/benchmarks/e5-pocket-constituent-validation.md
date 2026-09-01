# E5 Pocket complete constituent validation

Issue #420 publishes complete bounded interior membership for accepted rectangular and circular-end
`Pocket` occurrences. Labels are evaluation-only; production selects exact inner-wire regions from
the same run's topology before Candidate issuance.

## Authority

- Parent: `a82b656d77db6351f966afcc72b129c23ace760d`
- Child: `bdbe467c72d0a2062c0d89dec7000f5e6bb19386`
- Workload: first 500 lexical MFCAD++ test IDs
- Selection hash: `323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`
- Selected-source hash: `1cdff5b52c85478a32c2308c5f8163180d079bc893debd24413d809b14be9331`
- Taxonomy: `effectiveness-taxonomy-v3.json`

Canonical reports:

- `effectiveness-mfcadpp-500-pocket-constituent-parent-a82b656.json`
  (`5625aa8f626dbf0d006cc173e9761551b9594ecd1e49429804372bb6ed039fd5`)
- `effectiveness-mfcadpp-500-pocket-constituent-bdbe467.json`
  (`fe49943303ade5e875730300c42a618e68f9060b00800d92756999a0e9489ef5`)
- `mfcadpp-pocket-region-association-bdbe467.json`
  (`586a766bb776a57245aa521cb020ca428cc79b980b64f6a711f14f7563008715`)

## Result

| Class | Parent coverage | Child coverage | Added covered faces | Defining recall |
| --- | ---: | ---: | ---: | ---: |
| 14, Pocket | 670/907 (73.87%) | 815/907 (89.86%) | 145 | unchanged, 404/907 |
| 16, circular-end Pocket | 673/973 (69.17%) | 827/973 (84.99%) | 154 | unchanged, 427/973 |

Across the full report, 123 models and 136 model/class rows change. Every change is exclusively an
increase in `covered_faces`. Physical and mapped records, defining precision/recall, reconciliation
drops, taxonomy mismatches, predicate observations and unsupported diagnostics are identical.
Some added physical Pocket faces carry other dataset labels, so smaller coverage increases also
appear in classes 0, 3, 6, 12, 15 and 18; this is scorer-visible overlap, not a production
classification decision.

The focused audit constructs regions without labels and reports 1,987 same-solid regions, zero
whole-body regions, 890 unique bidirectional accepted associations, 79 fragmented components, 68
merged-component regions, 191 mixed-label regions and 11 tied target-class regions. Those ambiguous
categories are measured rather than resolved from labels.

In an isolated simultaneous parent/child run, runtime changed from 327.29 s to 339.57 s total
(+3.75%), with median 0.606 s to 0.636 s and p95 effectively flat at 1.196 s to 1.199 s. This is
accepted as a bounded cost for complete physical membership; records and recognition decisions
remain unchanged.

## Authored controls

The Pocket attribution suite covers exact rectangular, elongated and stubby circular-end interiors;
split floors; multiple and coincident bodies; disjoint and intersecting hole loops; foreign graph identity;
principal-axis and rigid transforms; reversed face traversal; direct/writer parity; and atomic
publication failures. Architecture tests roster the new exact arc reader. ADR 0002 records the
neutral proposal contract and ADR 0010 preserves the prohibition on later public adjacency search.
