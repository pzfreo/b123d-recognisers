# E2 Plate in-plane-roll covariance validation

Issue [#329](https://github.com/pzfreo/b123d-recognisers/issues/329) removes the
coordinate-envelope bias from Plate large-area eligibility without changing the public record,
principal-normal scope, material-side pairing, thickness gate, defining-face provenance or
reconciliation.

## Geometric authority

For a principal-normal slab, `min_area_frac` is now applied to the smallest exact body bounding
rectangle obtained by rolling the body around that normal. Candidate orientations come only from
transverse planar faces that support the body's vertex envelope. Concave/internal walls cannot
establish an envelope direction. Numerically duplicate imported normals are canonicalised at
`1e-9` degree resolution; axes with no correctly ordered thin opposed span do not construct an
oriented envelope. If a body has no transverse planar support direction, the legacy coordinate
envelope remains the fail-compatible fallback and no covariance claim is made for that
non-prismatic case.

This is corpus-independent: a minimum enclosing rectangle is invariant to the coordinate roll used
to express the same cross-section. The operation rotates only a temporary denominator shape.
Acceptance and published evidence continue to use the original shape and faces.

Before production changed, the immutable 500-model authority measurement at `6237b86` compared
four alternatives. The coordinate bbox produced 233 Plates; signed planar boundary area changed 70
models (176 Plates), largest principal group introduced 62 (295 Plates), and mean material section
introduced 168 (401 Plates). The selected oriented envelope changed exactly model `10649` and
retained all 233 existing Plates (234 total). See
[`plate-area-authority-measurement-mfcadpp-500-6237b86.json`](plate-area-authority-measurement-mfcadpp-500-6237b86.json),
SHA-256 `938b28813e05d5c68f84f327ef8cca1dd321d9062bfedb303e4b47ddb9ed4c60`.

## Exact MFCAD++ effectiveness comparison

Both runs use the published MFCAD++ test split, lexical first 500 unique model IDs, framed
recognition, selection SHA-256
`323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`, and taxonomy v2 SHA-256
`67f092a2aa8d08be94e9be409c1fb338350626c7f4d1398c2f78be3123977f3b`.

| measure | parent `6237b86` | implementation `10fa5f6` | delta |
| --- | ---: | ---: | ---: |
| loaded / evaluated | 500 / 500 | 500 / 500 | 0 |
| invalid / empty | 0 / 0 | 0 / 0 | 0 |
| physical Plate records | 233 | 234 | +1 |
| class-21 defining-face precision | 234/234 (1.0000) | 234/234 (1.0000) | 0 |
| class-21 defining-face recall | 234/354 (0.6610) | 234/354 (0.6610) | 0 |
| taxonomy-mismatch defining faces | 1,132 | 1,133 | +1 |
| median runtime | 0.4934 s | 0.5260 s | +0.0326 s |
| p95 runtime | 0.9435 s | 0.9975 s | +0.0539 s |
| corpus runtime | 261.80 s | 277.04 s | +15.25 s |

Reports:

- [`effectiveness-mfcadpp-500-plate-roll-parent-6237b86.json`](effectiveness-mfcadpp-500-plate-roll-parent-6237b86.json),
  SHA-256 `e0c639969dda0624063e448132c8dc0d4dc7ec89e0991cb1ba25a3d9ef718340`.
- [`effectiveness-mfcadpp-500-plate-roll-10fa5f6.json`](effectiveness-mfcadpp-500-plate-roll-10fa5f6.json),
  SHA-256 `70bcc5d690f2a37b7869dbc393b3b3057e3886ef5a4052f372213b40072a5fd9`.

The sole Plate delta is `10649.step`. Its physical defining groups remain 565.865609 and
261.266960 square units. The raw coordinate cross-area was 615.112347 (threshold 246.044939), while
the rolled framed coordinate envelope was 970.260549 (threshold 388.104219). The intrinsic
oriented envelope restores the same physical decision. Its defining faces carry dataset classes
20, 24 and 10 rather than Plate class 21, so the new record is honestly reported as one taxonomy
mismatch. It is covariance diagnosis evidence, not a claim that the dataset labels prove a true
Plate. Every other physical-family count is identical.

## Paired output and performance gates

The paired benchmark alternates execution order and replaces only the Plate denominator in its
legacy arm. At exact implementation commit `10fa5f6`, every non-Plate aggregate output is equal and
every legacy Plate is retained.

| workload | legacy Plates | oriented Plates | introductions | oriented / legacy runtime |
| --- | ---: | ---: | ---: | ---: |
| NIST/Gramel census (13) | 14 | 14 | 0 | 1.0104 |
| MFCAD++ lexical 500 | 233 | 234 | 1 | 1.0488 |

Both ratios pass the 1.10 budget. Reports:

- [`plate-area-authority-performance-census-10fa5f6.json`](plate-area-authority-performance-census-10fa5f6.json),
  SHA-256 `ef57338a3a3f2437a38d7b1b5c4a41993a0c3328c6c44c40b86eb58cf1515b47`.
- [`plate-area-authority-performance-mfcadpp-500-10fa5f6.json`](plate-area-authority-performance-mfcadpp-500-10fa5f6.json),
  SHA-256 `d8fed71c3c05b238da17acc796b20c00df7aa479d4eeb556eef575fb6b9dbf44`.

## Contract verification

Authored tests cover signed X/Y/Z Plate normals; 17, 37 and 73 degree in-plane rolls; strict
before/tie/after area boundaries at both 0 and 37 degrees; small internal faces; multi-slab air
gaps; compound body locality and order; arbitrary rigid framing; STEP round-trip; original-face
attribution; aggregate reconciliation; and the paired comparator. The refreshed golden rigid-motion
sweep retains three additional Plate occurrences and changes no reclassification count.

Local results at the implementation commits were 2,341 fast tests, 384 exhaustive tests with only
the deliberately refreshed rigid-motion evidence initially stale, then 71 focused Plate/evidence
tests after the performance refinement, plus clean Ruff, mypy and installed-wheel typing. One
independent contract review and one focused adversarial review found no implementation defect; both
requested only the final artifacts recorded here. The adversarial review independently swept
positive and negative rolls through ±179 degrees on X/Y/Z and verified strict tie refusal.

Final-diff review against ADRs 0002, 0007, 0008, 0009 and 0011 confirms that record identity and
rounding, module ownership, dimensional authorities, candidate provenance, one-invocation aggregate
publication, framing scope and fail-closed behavior remain intact. The relevant ADRs describe the
new denominator and its prismatic-domain boundary.

MFInstSeg was not inspected for this child and no transfer claim is made; its unavailable baseline
remains tracked by #293.

## Reproduction

```bash
uv run python tools/run_effectiveness_baseline.py mfcadpp \
  /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version "MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823" \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v2.json \
  --limit 500 --recognition-frame framed --output REPORT.json

uv run python tools/benchmark_plate_area_authority.py census --output CENSUS.json
uv run python tools/benchmark_plate_area_authority.py mfcadpp \
  --root /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --limit 500 --output MFCADPP.json
```
