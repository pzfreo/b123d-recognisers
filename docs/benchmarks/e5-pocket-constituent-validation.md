# E5 Pocket complete constituent validation

Issue #420 publishes complete bounded interior membership for accepted rectangular and circular-end
`Pocket` occurrences. Labels are evaluation-only; production selects exact inner-wire regions from
the same run's topology before Candidate issuance.

## Authority

- Parent: `a82b656d77db6351f966afcc72b129c23ace760d`
- Child: `b2e2203f1e2f7cf82fe70c255a68abf288108646`
- Workload: first 500 lexical MFCAD++ test IDs
- Selection hash: `323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`
- Selected-source hash: `1cdff5b52c85478a32c2308c5f8163180d079bc893debd24413d809b14be9331`
- Taxonomy: `effectiveness-taxonomy-v3.json`

Canonical reports:

- `effectiveness-mfcadpp-500-pocket-constituent-parent-a82b656.json`
  (`ce7a36d82ca8be9966b0e3e2f1c3023c2cad4bc858e1c186d66c653b3960e527`)
- `effectiveness-mfcadpp-500-pocket-constituent-b2e2203.json`
  (`a9857e9634506c32054b9deb3da74005c03f1252a304d0ca6d0f37a50335e5fe`)
- `mfcadpp-pocket-region-association-b2e2203.json`
  (`8ada4f8c54c3cfc1bcb7d5d34e8d20ba1a89ba62af31df60767a2124e2655b26`)

## Result

| Class | Parent coverage | Child coverage | Added covered faces | Defining recall |
| --- | ---: | ---: | ---: | ---: |
| 14, Pocket | 670/907 (73.87%) | 827/907 (91.18%) | 157 | unchanged, 404/907 |
| 16, circular-end Pocket | 673/973 (69.17%) | 851/973 (87.46%) | 178 | unchanged, 427/973 |

Across the full report, 137 models and 164 model/class rows change. Every change is exclusively an
increase in `covered_faces`. Physical and mapped records, defining precision/recall, reconciliation
drops, taxonomy mismatches, predicate observations and unsupported diagnostics are identical.
Some added physical Pocket faces carry other dataset labels, so smaller coverage increases also
appear in classes 0, 2, 3, 4, 6, 12, 15 and 18; this is scorer-visible overlap, not a production
classification decision.

The focused audit constructs regions without labels and reports 1,987 same-solid regions, zero
whole-body regions, 872 unique bidirectional accepted associations, 79 fragmented components, 68
merged-component regions, 191 mixed-label regions and 11 tied target-class regions. Those ambiguous
categories are measured rather than resolved from labels.

Runtime changed from 327.01 s to 336.72 s total (+2.97%), with median 0.615 s to 0.641 s and p95
1.177 s to 1.231 s. This is accepted as a bounded cost for complete physical membership; records and
recognition decisions remain unchanged.

## Authored controls

The Pocket attribution suite covers exact rectangular, elongated and stubby circular-end interiors;
split floors; multiple and coincident bodies; a nearby unrelated hole loop; foreign graph identity;
principal-axis and rigid transforms; reversed face traversal; direct/writer parity; and atomic
publication failures. Architecture tests roster the new exact arc reader. ADR 0002 records the
neutral proposal contract and ADR 0010 preserves the prohibition on later public adjacency search.
