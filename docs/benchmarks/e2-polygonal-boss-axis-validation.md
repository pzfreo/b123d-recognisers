# E2 principal-axis Polygonal Boss validation

Issue [#332](https://github.com/pzfreo/b123d-recognisers/issues/332) removes the hidden Z-axis and
positive-direction dependencies from attached regular-hexagonal boss recognition. Discovery checks
X, Y and Z against one run-owned graph. Both terminal boundaries must agree on one signed
attachment direction; `base` and `top` remain ascending coordinates along the reported axis.

## Evidence identity

- Behavior commit: `06c3a04b83a213bcc4363f10b7a7a8e9aae96c29`; review/evidence fix commit:
  `b78d28c3b15513550d64f126d3ab5c7b7f517659`.
- MFCAD++ corpus: published test split, DOI
  [`10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823`](https://doi.org/10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823).
- Selection: first 500 STEP model IDs, lexical ascending; newline-delimited selected-ID SHA-256
  `999c02bd6a9f1b407f24b5f7078107f5224334f2c5b8d5c4c4749310e41e3821`.
- [MFCAD++-500 paired report](polygonal-boss-axis-performance-mfcadpp-500-06c3a04.json),
  SHA-256 `5269d666cad13bf9aa3384f0b1304d675e24be63844106d74b504a11fa644218`.
- [NIST/Gramel paired report](polygonal-boss-axis-performance-census-06c3a04.json),
  SHA-256 `30257bf17c431be0b0d45cc1f1be860f9783770fb5ca98345a710d995a3c0572`.

MFCAD++ is open development evidence. It has no publisher instance relation and this selection
contains no Polygonal Boss accepted by either arm, so it supplies runtime and cross-family
regression evidence—not a boss-recall denominator. No MFInstSeg tree exists at the supplied
`/app/workspaces-codex/datasets/mfinstseg` path or the other checked `/app` dataset paths in this
runtime; this child therefore makes no independent-transfer claim.

## Geometry and parameter proof

Construction-authored tests cover positive and negative X/Y and positive Z extrusion, in-plane
rotation, arbitrary caller-space rigid motion through the framed aggregate, equal occurrences on
distinct bodies, mixed principal axes, reversed face traversal and STEP round trips. Every emitted
record is checked independently against its six original defining faces: ordered flat directions
equal their outward normals, physical flat centres equal source-face centres, and the centres lie
in the reported transverse plane. A/F, height, side count and the exact local axis/centre/bounds
survive the supported transforms.

The principal-axis aggregate emits one candidate for one physical boss and preserves exact
six-face ownership. Sharp and complete corner-blended controls agree in all signed principal
orientations. Whole stock, inward recess, detached prism, irregular hexagon, octagon, circular
boss, incomplete ring, ambiguous cap and cross-solid controls remain refused or independently
owned. No tolerance, public field or reconciliation rule changed.

## Corpus and runtime result

| Workload | Models | Z-only bosses | Principal-axis bosses | Other outputs equal | Legacy retained | Enabled/disabled total |
| --- | ---: | ---: | ---: | --- | --- | ---: |
| MFCAD++ first 500 | 500 | 0 | 0 | yes | yes | 1.0167 |
| NIST/Gramel census | 13 | 1 | 1 | yes | yes | 1.0405 |

The MFCAD++ arms took 219.02 s and 222.67 s; their paired median delta was 0.0054 s per model. The
real-part arms took 178.27 s and 185.49 s; their paired median delta was 0.0804 s. Both ratios remain
below the E2 1.10 package budget. The runs overlapped repository validation for part of their
execution, so absolute wall times are descriptive; enabled/disabled order alternated per model and
the paired ratio is the comparison used here.

The final focused public/provenance/STEP/installed-wheel set passes 156 tests. Before the two
review-requested signed/framed cases were added, the repository fast lane passed 2,289 tests and
the exhaustive lane passed all 384 slow tests; the exact post-review subset passes 15/15.

## ADR conformance

- ADR 0002/0003: direct and aggregate paths share one discovery implementation and aggregate
  authority; one physical occurrence is issued once.
- ADR 0004/0007: each candidate retains exactly six original defining side faces through the
  existing family-owned writer seam.
- ADR 0008/0009: no tolerance moved and signed cap semantics remain recognizer policy.
- ADR 0011: the existing orientation-bearing record represents the selected local principal axis;
  the framed result remains paired with the exact working shape, and framing does not become the
  default.
