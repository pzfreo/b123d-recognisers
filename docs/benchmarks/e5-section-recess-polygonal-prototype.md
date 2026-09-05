# E5 free-frame polygonal SectionRecess prototype

Date: 2026-09-04  
Branch source before the measured working-tree change: `0c160cc`  
Dataset: complete published MFCAD++ test split (2,500 selected; seven known invalid STEP files)

## Question

Does the unified `SectionRecess` contract and a coordinate-free intact-floor proof recover the
large polygonal-pocket residual, or is the earlier free-in-plane result specific to obround
pockets?

## Contract result

The contract is general. Authored triangular, rectangular and hexagonal pockets project through
the same free frame, run interval, closed line profile, end conditions, classification and indexed
evidence as the obround prototype. Tests cover arbitrary rigid presentation, STEP round-trip,
through-cut and boss rejection, and equal features on separate bodies.

The experiment also corrected a conservative serialization bound. A rounded `(u, v)` coordinate
error is one Euclidean vector; treating its orthogonal components as two collinear full-size errors
caused valid translated oriented sections to be refused. The corrected Frobenius-norm bound remains
conservative and retains the existing 0.002 world-displacement ceiling.

## Largest-family transfer result

The first complete overlay targeted class 15, **6-sided pocket**, because it is the largest
polygonal pocket family. Candidate geometry was built before labels were read.

| Measure | Result |
| --- | ---: |
| evaluated / selected models | 2,493 / 2,500 |
| prototype occurrences | 664 |
| prototype defining-face purity | 3,984 / 3,984 = 1.000 |
| prototype constituent-face purity | 4,648 / 4,648 = 1.000 |
| baseline defining recall | 4,242 / 5,707 = 0.7433 |
| combined defining recall | 4,296 / 5,707 = 0.7528 |
| baseline face coverage | 5,319 / 5,707 = 0.9320 |
| combined face coverage | 5,368 / 5,707 = 0.9406 |
| net new covered faces | 49 |

## Decision

Keep the unified contract and the free-frame floor proof: both are truthful and the proof is a
high-purity substrate. Do not claim that orientation covariance recovers the estimated aggregate
polygonal residual. For the largest family it mostly duplicates existing principal-axis
recognition and adds only 49 faces.

The next high-value hypothesis is treatment-aware cavity propagation. The residual is not chiefly
an inability to serialize an oriented polygon; it is an inability to retain a pocket occurrence
when chamfers, blends, split supports or intersections interrupt the intact floor/wall/mouth
template. That work must seed and walk observed cavity topology while using this same
`SectionRecess` value; it must not introduce another polygonal schema or weaken the intact proof.

MFInstSeg was not read, run or inspected.
