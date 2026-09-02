# E5 — Planar Passage termination validation

## Geometry and contract

Issue #453 separates a passage's run from the presentation of its exterior stock faces. A simple
cycle of original planar walls must prove one unique common straight junction direction. Two
complete convex inner-wire mouths then prove the same transverse line polygon, one valid solid,
and two non-crossing planar termination equations. The clipped prism and thin exterior slabs must
be empty. No dataset label, world axis, angular threshold, opening-face identity, or post-Candidate
adjacency search participates in acceptance.

ADR 0016 records schema v2. `run_interval` contains the two centroid-line intersections and
`PassageEnds.low_gradient` / `high_gradient` describe the exact end planes in section coordinates.
Flat passages retain zero gradients. Four-decimal intrinsic section points keep steep planes
inside the existing `0.002 mm` whole-occurrence displacement bound; this is serialization
precision, not a wider recognition tolerance. The greater precision also removes a former
`23.999 mm` rounding artefact from the authored `24 mm` oriented-slot golden; that downstream
projection and its rounding-error bound now consume schema-v2 precision explicitly.

Authored tests cover two distinct wedge geometries for each of triangular, rectangular and
six-sided passages, exact gradients and sections, rigid transformation, translation, scale, STEP
round-trip, presentation reversal, compound multiplicity, defining/constituent evidence, legacy
projection refusal, crossing planes, curved sections, caps, obstruction, taper, branching and
same-solid ownership. The final diff conforms to ADRs 0002, 0003, 0007, 0008, 0009, 0010, 0011,
0014 and 0016: neutral construction remains in `_section_passages`; `passages` remains the only
public record and Candidate issuer; and opening faces remain consulted context.

## First-500 development evidence

Against the preceding wire-order result on the identical lexical selection, Passage records rise
from 353 to 413. Every added defining-face claim belongs to MFCAD++ Passage classes 2, 3 or 4.
Six-sided coverage rises from 0.6714 to 0.7620 and defining recall from 0.6228 to 0.7193;
triangular coverage rises from 0.6392 to 0.7335; rectangular coverage rises from 0.7939 to 0.8487.

The label-blind rejection audit constructs regions before reading labels. Accepted fallback reach
is 355 six-sided faces, while the former opposed-opening gate falls to 9 faces. The remaining
larger buckets are planar mouth seeding (34 faces) and noncongruent mouths (72); neither is folded
into this rule.

Machine evidence:
[`mfcadpp-passage-rejection-census-500-c813b35.json`](mfcadpp-passage-rejection-census-500-c813b35.json),
SHA-256 `7bc498345221a98d761e21961ad4cfca39616f8040f1a37575ba5b99eb0832e6`.

## Full MFCAD++ result

The merge-candidate comparison evaluates 2,493 valid models and preserves the same seven known
invalid-file dispositions as the parent.

| Measure | Wire-order parent | Planar ends | Change |
| --- | ---: | ---: | ---: |
| physical Passage records | 1,775 | 2,062 | +287 |
| triangular mapped records | 626 | 740 | +114 |
| rectangular mapped records | 560 | 637 | +77 |
| six-sided mapped records | 613 | 711 | +98 |
| triangular face coverage | 0.6869 | 0.7896 | +0.1027 |
| triangular defining recall | 0.6237 | 0.7336 | +0.1099 |
| rectangular face coverage | 0.8085 | 0.8501 | +0.0415 |
| rectangular defining recall | 0.5593 | 0.6305 | +0.0712 |
| six-sided face coverage | 0.6418 | 0.7254 | +0.0835 |
| six-sided defining recall | 0.6023 | 0.6921 | +0.0898 |
| taxonomy-mismatched defining faces | 15,525 | 15,506 | -19 |
| all-family unmapped records | 14,681 | 14,669 | -12 |

Machine evidence:
[`effectiveness-mfcadpp-2500-planar-ends-c813b35.json`](effectiveness-mfcadpp-2500-planar-ends-c813b35.json),
SHA-256 `3e1dd81094bd00366d83810dbb6f88f00b12b4c75ab25757341a3f1da60f030e`.

## Next priority

This closes the high-value nonparallel-termination hypothesis without weakening the residual
gates. The next effectiveness increment should be #368: reuse bounded-region traversal to publish
complete constituent evidence for already-detected pockets. That addresses the measured
membership gap across four pocket families; the remaining Passage audit buckets require different
geometry and are smaller than that cross-family opportunity.
