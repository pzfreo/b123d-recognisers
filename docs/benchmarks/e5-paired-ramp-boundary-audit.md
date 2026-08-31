# E5 paired-ramp boundary audit

Issue [#366](https://github.com/pzfreo/b123d-recognisers/issues/366) tests the next class-9
miss cluster after the subdivided-terminal increment in [#364](https://github.com/pzfreo/b123d-recognisers/issues/364).
The comparison arm bypasses only the historical requirement that both original planar ramps have
exactly four edges. It then executes every other production gate unchanged. Dataset labels select
pairs for audit; they are not inputs to recognition.

## Exact result

The post-#364 lexical MFCAD++-500 selection contains 592 class-9 faces in 171 shared-edge
same-label component proxies. Aggregate recognition matches 138 faces and 44 components, leaving
454 faces unmatched. The original best-pair reconciliation still places 35 wholly unrecalled
components at the ramp-boundary gate.

The exhaustive comparison finds 40 boundary-gated adjacent pairs across 38 components: 36 wholly
unrecalled components and two components already touched by a different accepted occurrence. The
extra wholly unrecalled component has a different later-reaching best pair, which is why the
exhaustive count is 36 rather than the best-pair count of 35. Continuing those 40 pairs through
the unchanged gates gives:

| result after bypassing only the four-edge gate | pairs |
| --- | ---: |
| Recognisable | 18 |
| Top-opening thickness direction | 11 |
| Not exactly two common axis terminals | 10 |
| Incomplete shared run | 1 |

The 18 surviving pairs occur in 18 currently unrecalled components and project 54 distinct
original defining faces. If label-independent production discovery accepts exactly this motif,
the development-selection upper bound is:

- 64 `PairedRampStep` records rather than 46;
- 192/592 defining-face recall (32.43%) rather than 138/592 (23.31%); and
- 62/171 component-proxy recall (36.26%) rather than 44/171 (25.73%).

These are projections, not post-implementation precision or native instance recall. A production
prototype must discover candidates without labels across all 500 models and retain exact
unrelated-family parity.

The projected faces already participate in five Plate, 31 Riser and three FaceLevel accepted
records; face-level claims total five Plate, 32 Riser and three FaceLevel claims. These are
independently owned structural occurrences, not evidence for reconciliation precedence. No
existing paired-ramp occurrence is part of the projected set.

## Geometry and retained exclusions

The surviving motif still consists of two identity-distinct original oblique planar faces. They
remain mirror symmetric, share one concave linear ridge aligned to one principal run, have exactly
one same-solid exterior and one planar internal axis terminal with the required convex/concave
arcs, open through a stock side, and agree exactly with the complete shared run. Only the ramps'
remaining boundary presentation differs from a quadrilateral. No coplanar face reconstruction or
new inferred defining identity is needed.

Bounded examples show the relevant presentation variants:

- model `10098`, faces 5/23 with internal terminal 3, has a six-edge/four-edge pair with only
  straight boundaries and no inner wire in the component;
- model `10344`, faces 2/23 with terminal 4, has two seven-edge ramps in a three-face component
  whose faces carry inner wires but no curved boundary;
- models `11357` and `11415` each have a five-edge/five-edge pair in a component with two
  inner-wire and two curved-boundary faces, while all material, terminal and full-run proofs hold;
- model `10988` demonstrates the retained completeness boundary: its five-edge/five-edge proposal
  reaches the comparison arm but is rejected because the shared ridge does not span the ramps;
- models `10049` and `10096` demonstrate retained ownership and opening boundaries: the former
  lacks exactly two common axis terminals and the latter is a top-opening pocket.

The result supports a focused production child that removes only the four-edge ramp boundary gate.
It does not support multiple coplanar ramp faces, split ridges, changed terminal ownership,
top-opening pockets, asymmetric ramps or missing-bevel cases.

## Artifact and reproduction

The immutable artifact is
[`paired-ramp-boundary-audit-mfcadpp-500-2f4052c.json`](paired-ramp-boundary-audit-mfcadpp-500-2f4052c.json),
SHA-256 `129d4d34c83ceffa162113e66e7c954e55631475dac2b170ad0a8c8fba91080b`, generated at audit
commit `2f4052c` using:

```bash
uv run python tools/audit_mfcadpp_paired_ramp_steps.py \
  /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --limit 500 \
  --output docs/benchmarks/paired-ramp-boundary-audit-mfcadpp-500-2f4052c.json
```

Two exact runs are byte-identical. The selection hash remains
`323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`.
The aggregate exact-source hash is
`1cdff5b52c85478a32c2308c5f8163180d079bc893debd24413d809b14be9331`; it hashes the
ordered model ID and SHA-256 of every selected STEP file, whose embedded comments carry the
MFCAD++ face labels. Each component also retains its model source hash.
The artifact retains every component, matched and unmatched face identity, every ordinary pair
gate, every comparison-arm result, projected defining identity and accepted-family overlap.

## Architecture and decision

ADRs 0002, 0003, 0004, 0007, 0008, 0009 and 0011 were reviewed. This audit changes no production
predicate, record, schema, taxonomy, reconciliation rule, manifest or downstream API. Its
post-#364 gate model now mirrors the explicit planar-terminal contract and no longer reports the
removed terminal edge-count restriction as production behavior.

The recommended production child must use one original planar ramp face as each defining
authority; preserve candidate identity, same-solid ownership and exact original-face provenance;
cover straight subdivision, inner-wire and curved interruption positives; retain the later-gate
negative examples above; include rotation, scale, traversal and STEP round-trip variants; and run
the exact MFCAD++ before/after score vector with the package runtime gate. MFInstSeg was not mounted
or inspected and remains transfer direction rather than geometry evidence.
