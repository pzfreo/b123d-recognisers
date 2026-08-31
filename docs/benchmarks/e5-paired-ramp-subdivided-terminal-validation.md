# E5 paired-ramp subdivided-terminal validation

Issue [#364](https://github.com/pzfreo/b123d-recognisers/issues/364) implements the focused motif
identified by the complete [paired-ramp miss audit](e5-paired-ramp-miss-audit.md). It removes only
the internal planar terminal's historical 3/5-edge boundary-count gate. Every material, side-
opening, mirror-pair, principal-run, complete-ridge, same-solid, terminal-arc and full-run proof
remains unchanged.

## Geometry and authored evidence

One original planar face remains the internal terminal authority and defining face. Its exact
concave arcs to both original four-edge ramps are still required. Extra straight boundary
segments, inner wires and circular interruptions are B-Rep presentation or independent-feature
facts; they do not merge terminals, traverse coplanar regions, change material ownership, or
weaken the complete shared-run proof.

Authored tests cover a straight subdivision, drilled circular interruption, two independent pairs
on one solid, and one native plus one interrupted pair on the same solid. Each occurrence retains
its own two ramps and terminal as three identity-distinct defining faces. Existing principal-axis,
translation, traversal, scale, open-shell, cross-solid, blind-groove, top-opening pocket,
asymmetry, rib/wedge, incomplete direction/terminal/arc/span and downstream dimension-projection
tests remain green.

## Exact MFCAD++-500 result

The exact taxonomy-v4 report is
[`effectiveness-mfcadpp-500-paired-terminal-905ddef.json`](effectiveness-mfcadpp-500-paired-terminal-905ddef.json),
SHA-256 `3a6703c14e355ab36e61a105244b2623489916b1fe9a400ba118150c4879cc7a`, generated at
implementation commit `905ddef` using:

```bash
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version published-test-split \
  --limit 500 \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v4.json \
  --output docs/benchmarks/effectiveness-mfcadpp-500-paired-terminal-905ddef.json
```

Compared with the exact pre-change taxonomy-v4 report:

- 500/500 models load and evaluate, with zero invalid and zero empty inventories;
- accepted `PairedRampStep` records increase from 21 to 46 across 24 changed models;
- class-9 defining-face precision remains 138/138 (100%); recall improves from 63/592
  (10.64%) to 138/592 (23.31%);
- the non-native component-proxy recall reproduced by the audit improves from 21/171 to 44/171;
- the audit projection is met exactly: 25 new records and 75 new class-9 defining faces, including
  two new records in model `12060` and one residual record beside the existing record in `11014`;
- every other physical-family record count is equal, as are reconciliation drops, diagnostics,
  predicate observations, total taxonomy mismatches and every non-class-9 per-class row;
- total runtime is 261.272 seconds versus 251.121 seconds (ratio 1.0404), within the 1.10 package
  gate. Timing is descriptive because the runs were not interleaved.

No off-class defining face is introduced. Existing Pad, Plate, Riser and FaceLevel records remain
present; no new reconciliation precedence is required. MFInstSeg was unavailable and no individual
transfer model was inspected. Its supplied aggregate paired-ramp direction remains a milestone
prompt rather than implementation evidence.

## Architecture and compatibility

ADRs 0002, 0003, 0004, 0007, 0008, 0009 and 0011 were reviewed before implementation. The public
`PairedRampStep` schema, serialization, ordering, family ID, aggregate field, manifest, installed
typing and concrete `2 × angle` plus run-length downstream projection are unchanged. The final diff
must receive one independent exact-head contract review and all required hosted gates before merge.
