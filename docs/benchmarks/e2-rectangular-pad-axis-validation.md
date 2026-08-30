# E2 principal-axis rectangular Pad validation

Issue [#331](https://github.com/pzfreo/b123d-recognisers/issues/331) removes the hidden world-Z and
positive-direction dependencies from rectangular Pad recognition. Sharp and complete four-corner
blend routes evaluate all six signed principal directions through one run-owned graph and
effective-surface query. `RaisedPad.axis` and `direction` carry orientation while exact XYZ bounds
remain in the supplied recognition frame.

## Evidence identity

- Behavior commit: `47922507ca2f2f25d490683e2f32d14bdf6163be`; query-sharing and final typing
  commits: `0d2ff885cfd863c35782bc6de1460f77771acbd8` and
  `313258080632877fbe8dd4e8195b41be9e5ad12c`.
- MFCAD++ corpus: published test split, DOI
  [`10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823`](https://doi.org/10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823).
- [Framed effectiveness report](effectiveness-mfcadpp-500-e2-pad-axis-4792250.json), SHA-256
  `05b4e3aabeb33a003a936bcd120721c30058a4a26c8e145e9dae95768355459f`.
- [MFCAD++-500 paired report](pad-axis-performance-mfcadpp-500-3132580.json), SHA-256
  `3cc41c3810af4e8f15ed3a6b8f4bfb731ed439ab225f77df325c58714cb987ff`.
- [NIST/Gramel census paired report](pad-axis-performance-census-3132580.json), SHA-256
  `fa99b6d5697918e16f4e2cd5ae10df80ebeb87d5eb8e5c599b257781e556ac9d`.

MFCAD++ is direct development evidence. No MFInstSeg tree exists at the supplied
`/app/workspaces-codex/datasets/mfinstseg` path or the other checked `/app` dataset mounts in this
runtime, so this increment records no independent transfer claim and does not substitute another
dataset.

## Geometry and refusal proof

Construction-authored tests cover sharp and completely corner-blended pads in positive and
negative X, Y and Z, in-plane rotation, arbitrary rigid motion through framed recognition, equal
records on separate bodies and STEP round trips. Each Candidate owns exactly the original terminal
and four wall faces; material-side evidence is independently certified on the terminal face.

Full-span steps, pockets, polygonal and perforated tops, detached prisms, staircase geometry,
incomplete or competing blend chains, cross-solid support and internally oblique islands remain
refused or separately classified. When one physical island yields overlapping axis readings, the
unique shortest attachment span wins; a tied minimum refuses without an XYZ-order preference.

## Effectiveness and runtime result

The framed first-500 MFCAD++ report evaluated all 500 selected models with zero invalid or empty
models. Rectangular Pads increased from the earlier framed audit's 6 records to 28 while every
other aggregate family count remained unchanged. Direct inspection of the changed labelled Stock
sentinels confirmed complete residual rectangular islands; the overlap is a single-label corpus
taxonomy limitation, not incomplete geometric projection.

| Workload | Models | Z-only Pads | Principal-axis Pads | Added | Other outputs equal | Legacy retained | Enabled/disabled total |
| --- | ---: | ---: | ---: | ---: | --- | --- | ---: |
| MFCAD++ first 500 | 500 | 2 | 28 | 26 | yes | yes | 1.0341 |
| NIST/Gramel census | 13 | 0 | 0 | 0 | yes | yes | 1.0200 |

The isolated MFCAD++ arms took 242.41 s and 250.67 s; paired median delta was 0.0159 s per model.
The isolated census arms took 186.00 s and 189.72 s; paired median delta was 0.3218 s. Both are
inside the E2 1.10 total-time budget. Alternating arm order limits systematic warm-cache bias.

The final local fast tier passes 2,320 tests. The exhaustive tier passed 383 unrelated slow tests;
its sole installed-wheel typing failure was fixed and the complete wheel runtime/typing test then
passed narrowly. Ruff and mypy pass. One independent contract review and a focused post-refactor
conformance check both concluded clean.

## ADR conformance

- ADR 0002/0003: direct and aggregate paths share one discovery implementation; schema version 2
  is explicit and one physical occurrence is issued once.
- ADR 0004: caches are solid- and run-owned; the existing material certificate remains the sole
  acceptance authority and accepted evidence still names exactly five original faces.
- ADR 0007/0008/0009: the family owns its filter, module seam and existing tolerance policy.
- ADR 0011: axis, direction, bounds, evidence and the framed working part share one local coordinate
  system; no alternate representative is probed.
