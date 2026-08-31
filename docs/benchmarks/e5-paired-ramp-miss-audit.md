# E5 paired-ramp miss audit

Issue [#362](https://github.com/pzfreo/b123d-recognisers/issues/362) reconciles every
MFCAD++ class-9 component proxy against the current `PairedRampStep` contract. The audit identifies
one focused next increment: retain every existing material, opening, symmetry, ridge, terminal and
run proof, but replace the internal terminal's historical 3/5-edge shape gate with the already
proved single planar terminal and exact arc relations.

## Exact reconciliation

The lexical MFCAD++-500 selection contains 592 class-9 faces in 171 non-native shared-edge
same-label component proxies. Current aggregate output matches 63 defining faces in 21 components,
leaving 529 unmatched faces. Of those, 514 are in 150 wholly unrecalled components; the remaining
15 are residual faces inside two partially recalled components. The artifact retains matched and
unmatched face identities and every pair-gate outcome for all 171 components.

The audit mirrors the production predicate gate by gate and assigns each unrecalled component to
the furthest explicit gate reached:

| first failed gate | components | labelled faces |
| --- | ---: | ---: |
| No adjacent bevel pair | 47 | 140 |
| Fragmented ramp boundary | 35 | 132 |
| Top-opening thickness direction | 33 | 105 |
| Subdivided internal terminal | 23 | 96 |
| Missing one linear shared ridge | 10 | 30 |
| Asymmetric ramps | 1 | 8 |
| Not one exterior and one internal terminal | 1 | 3 |

The top-opening cases remain the deliberate triangular-pocket precision boundary. Missing bevels,
fragmented ramps, multiple ridges and asymmetry require different geometric proofs and are not
folded into the recommendation.

## Recommended motif

All 24 components containing a terminal-only proposal have:

- exactly two adjacent mirror-symmetric oblique planar ramps with four edges each;
- one complete linear concave shared ridge along one principal run;
- one same-solid exterior terminal convex to both ramps and one internal terminal concave to both;
- a side opening rather than an opening along the stock's unique thickness direction; and
- exact full-run agreement between both ramps and the shared ridge.

Only the internal planar terminal's boundary count differs: 6–16 edges rather than the historical
3 or 5. The 24 components contain 25 independently proved ramp pairs; model `12060` contains two
pairs in one connected labelled component, and one additional pair occurs among the residual faces
of partially recalled model `11014`. Their projected defining sets contain 75 distinct
class-9 faces. If a production prototype accepts exactly these pairs, the development-selection
upper bound is therefore:

- 46 records rather than 21;
- 138/592 defining-face recall rather than 63/592;
- 44/171 component-proxy recall rather than 21/171; and
- 75/75 newly projected defining-face agreement before whole-corpus candidate discovery.

These are audit projections, not claimed post-implementation precision or native instance recall.
The implementation must run ordinary label-independent discovery across all 500 models; off-class
candidates decide whether the relaxation is safe.

## Bounded representative inspection

Face indices are zero-based imported-face positions.

- Model `10092`, pair 22/23 and terminal 7: the internal terminal has seven straight edges. Its
  additional convex neighbours are stock and class-6 edge-slot faces; both class-9 ramp arcs remain
  concave. This is straight B-Rep subdivision, not a different ramp cross-section.
- Model `10347`, pair 21/25 and terminal 22: the internal terminal has eight straight plus two
  circular edges and two wires. The extra boundaries meet two class-21 cylinders convexly; the
  two ramp arcs remain concave. This is a drilled interruption of the terminal plane.
- Model `12060` proves multiplicity: pair 2/14 uses seven-edge terminal 4, while pair 23/24 uses
  eleven-edge two-wire terminal 22. Both retain distinct complete ridges and terminal authorities
  inside one six-face class component, so component identity must not collapse record identity.
- Model `11014` proves partial-component accounting: one pair is already accepted, while distinct
  residual faces 10/11/20 form another full-run pair stopped only by its terminal boundary. The
  artifact retains both rather than treating one touched component as completely recalled.

Across the projected defining faces there are no accepted Chamfer overlaps. Exact overlaps are
four Pad records on five faces, three Plate records on three faces, 30 Riser records/faces and
seven FaceLevel records/faces. These are existing structural or independently owned occurrences;
a follow-on must preserve them unless exact candidate identity and ADR-0003 evidence justify a
separate reconciliation decision.

## Artifact and reproduction

The machine artifact is
[`paired-ramp-step-miss-audit-mfcadpp-500-ddc1ac6.json`](paired-ramp-step-miss-audit-mfcadpp-500-ddc1ac6.json),
SHA-256 `cad5f9cce995700ad5154bbb0a341d227fa35c75a573fe0475a0f9bfe371f88b`, generated at audit
commit `ddc1ac6` using:

```bash
uv run python tools/audit_mfcadpp_paired_ramp_steps.py \
  /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --limit 500 \
  --output docs/benchmarks/paired-ramp-step-miss-audit-mfcadpp-500-ddc1ac6.json
```

The artifact records the dataset version, exact lexical selection hash
`323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`, every component,
explicit descriptor clusters, gate counts, accepted overlap evidence and deterministic samples.
Two exact runs are required to be byte-identical before merge. MFInstSeg was not mounted or
inspected; its supplied aggregate direction is not used as geometry evidence.

## Architecture and follow-on boundary

ADRs 0002, 0003, 0004, 0007, 0008, 0009 and 0011 were reviewed. This audit adds only tooling,
authored tests and immutable evidence. It changes no record, recogniser, threshold, mapping,
candidate, reconciliation rule, manifest or downstream API.

A focused implementation should remove only the internal terminal edge-count restriction while
retaining the unique planar terminal, exact concave/convex arcs, same-solid proof, side-opening
classification and complete shared run. Required authored evidence includes straight subdivision,
an inner wire, a drilled circular interruption, the two-occurrence connected case, rotations,
scale, traversal and STEP round-trip, plus refusals for a missing/split terminal, incomplete ridge,
blind groove, top-opening pocket, rib/roof, cross-solid pair and changed terminal arc. It must
rerun full aggregate precision/recall, all existing-family parity, performance, installed/public
contracts and the existing downstream dimension projection. Close without implementation if any
off-class candidate survives those unchanged proofs.
