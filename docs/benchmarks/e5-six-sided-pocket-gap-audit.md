# E5 untouched six-sided pocket gap audit

Issue [#409](https://github.com/pzfreo/b123d-recognisers/issues/409) tests the largest
remaining unaudited wholly untouched MFCAD++-500 bucket after #403. This is an audit result, not a
recogniser extension. Dataset labels select component proxies to describe; they never enter a
proposal or geometry predicate.

## Authority and method

The immutable report is
[`e5-six-sided-pocket-gap-audit-b93cf26.json`](e5-six-sided-pocket-gap-audit-b93cf26.json).
It records audit commit `b93cf263c85cc1ec9dfcf3048d4d63a74012a10c`, the published MFCAD++
test split, the standard lexical 500-model selection hash, and a hash over every selected model ID
and STEP source hash. MFCAD++ has no native instance IDs; an “instance” here is explicitly a
same-label shared-edge component proxy.

```console
uv run python tools/audit_mfcadpp_prismatic_pocket_gaps.py \
  /path/to/MFCAD++_dataset/step/test \
  --class-id 15 \
  --limit 500 \
  --output /tmp/e5-six-sided-pocket-gap-audit.json
```

For every class-15 proxy, the harness records its exact original face indices and consumes one
completed aggregate inventory to record accepted all-family defining/constituent coverage.
Untouched proxies are then derived from that full denominator and compared with the complete
neutral Pocket proposal roster and complete production `rings()` roster. Its ring probe calls the same
principal-wall, equal-span, cycle, cross-section, void and cap functions as production; it does not
reimplement or relax those predicates.

Authored controls cover a valid blind hexagonal pocket, through and two-cap variants, principal-axis
rotation, source/order hashes, and two equal pockets on separate bodies. The compound control
requires distinct valid-solid authorities rather than permitting cross-body identity collapse.

## Result

Fresh main contains **19 wholly untouched proxies / 104 faces**, correcting the stale pre-#403
estimate of 21 / 113. Every proxy is planar and belongs to one valid solid.

| First unchanged ring result | Proxies | Faces/meaning |
| --- | ---: | --- |
| `not_simple_cycle` | 17 | The label-selected walls do not form one equal-span degree-two ring |
| `not_single_cap` | 2 | Exact six-wall rings, each closed by one cap at both ends |

The two exact-ring proxies contain seven labelled faces each: six walls plus one of the two caps.
Production finds both complete rings and correctly refuses them as inaccessible enclosed cavities.
Accepting either would remove the one-open-end contract rather than improve supported pocket recall.

Two other proxies in one model partially overlap a production triangular ring, but the class-15
labels cover only cap fragments while its three ring walls carry different labels. That is a
taxonomy/component-fragment case, not evidence for joining the two class-15 components or changing
the six-sided recogniser.

The remaining 15 proxies have zero overlap with any production ring. Across all 19, **zero overlap
any neutral Pocket proposal**. Their planar component sizes are 3 faces (4 proxies), 4 (3), 5 (1),
6 (2), and 7 (9). The apparent seven-face shape is therefore not sufficient evidence: seven of
those nine fail cycle closure, while the other two are closed cavities.

## Decision

Close #409 without a production change. There is no intact one-cap ring or unchanged rectangular
Pocket proposal hidden in this bucket. A counterfactual would have to bridge interrupted topology,
join differently labelled regions, or report a two-cap cavity; each violates original adjacency,
one-feature boundary, or tool-accessibility contracts.

This conclusion conforms to ADRs 0002, 0003, 0004, 0007, 0008, 0009, 0010 and 0011:

- no record, defining ownership, constituent membership, reconciliation or public API changes;
- no cross-solid merge, coordinate rematch, durable face identifier or corpus-derived threshold;
- no production recognition rerun inside scoring and no dataset label in a predicate;
- principal-axis and compound controls preserve covariance and body-local identity.

MFCAD++ effectiveness is unchanged by construction, so a redundant before/after baseline is not
published. MFInstSeg was not run or inspected; this audit is not a transfer milestone.
