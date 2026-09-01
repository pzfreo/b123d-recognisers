# E5 paired-ramp boundary validation

Issue [#371](https://github.com/pzfreo/b123d-recognisers/issues/371) implements the bounded
geometry established by the source-pinned [#366 audit](e5-paired-ramp-boundary-audit.md).
Production discovery removes only the requirement that both original planar ramps have exactly
four edges. Every geometric proof after that presentation gate remains unchanged.

## Geometry contract

An accepted occurrence still requires two identity-distinct original oblique planar faces that
are mirror symmetric in one principal cross-section. They share exactly one concave linear ridge,
the ridge and both ramps cover the same complete run, and exactly two common same-solid planar
axis terminals supply one convex exterior opening and one concave internal terminal. The opening
must remain through a stock side rather than its unique thickness direction.

Boundary subdivisions, independent inner wires and curved interruptions are now presentation
facts. Discovery does not merge or traverse multiple coplanar ramp faces, reconstruct a split
ridge, relax terminal ownership, or add a tolerance.

Authored regressions cover straight subdivisions on one and both ramps, a circular ramp inner
wire, two independently owned occurrences, principal-axis rotations, translation, scale, profile
traversal and STEP round-trip. Existing and extended adversaries retain asymmetric, incomplete or
multiple-ridge, terminal, top-opening, open-shell, cross-solid and nonprincipal refusals.

## Exact MFCAD++-500 result

The immutable raw-frame report is
[`effectiveness-mfcadpp-500-paired-ramp-bd6bcc7.json`](effectiveness-mfcadpp-500-paired-ramp-bd6bcc7.json).
It uses taxonomy v8 and the same lexical 500-model selection hash
`323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df` as the baseline.

| class-9 measure | baseline | implementation |
| --- | ---: | ---: |
| `PairedRampStep` records | 46 | 64 |
| defining-face precision | 138/138 (100%) | 192/192 (100%) |
| defining-face recall | 138/592 (23.31%) | 192/592 (32.43%) |
| exact all-family face coverage | 376/592 (63.51%) | 392/592 (66.22%) |

Exactly 18 models gain one record: `10098`, `10317`, `10344`, `10727`, `10881`, `11131`,
`11190`, `11252`, `11357`, `11415`, `11555`, `11948`, `12024`, `12102`, `12214`, `12324`,
`12554`, and `12667`. This exactly realizes the audit projection. All 500 rows are identical
after removing runtime and class-9/`paired-ramp-steps` fields. There are zero invalid and zero
empty models; taxonomy mismatch remains 3,195 defining faces.

The implementation report takes 308.58 seconds against 324.75 seconds for the immediately
preceding exact v8 baseline on the same shared host, a 0.9502 ratio. This is descriptive timing,
not evidence of a speed-up, and is below the 1.10 regression gate.

## Architecture review

ADRs 0002, 0003, 0004, 0007, 0008, 0009 and 0011 apply. The change preserves the frozen record,
deterministic ordering, one aggregate candidate lifecycle, original graph-node provenance,
same-solid ownership, fail-closed publication and principal-frame covariance. It changes no
schema, reconciliation rule, taxonomy or public function. No threshold is added or weakened;
the family-owned edge-count gate is removed because it measured B-Rep presentation rather than
the geometric contract. MFInstSeg is not a per-family gate and no individual transfer model was
inspected.
