# MFCAD++-500 through-step miss audit

**Issue:** #306  
**Production baseline:** `04d6e9d`  
**Audit implementation:** `2322328be2064447749375d56328c4a5766d1bb2`
**Dataset role:** open development evidence  
**Corpus version:** MFCAD++ published test split; DOI
`10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823`
**MFInstSeg:** not used or inspected

## Result

The first rectangular through-step increment recalls 39 of 181 non-native shared-edge class-8
component proxies and 78 of 415 labelled faces. The audit reconciles the remaining 142 components
and 337 faces exactly.

One corpus-independent motif accounts for 53 of the 142 unrecalled components (37.32%) and 106 of
the 337 unrecalled faces (31.45%):

- exactly two orthogonal principal planar wall faces;
- one concave join spanning the complete inferred run;
- both walls span the source solid along that run;
- two terminal planes close the material at the run ends;
- the inferred rectangular envelope reaches the stock boundary;
- the complete inferred removed prism contains exactly zero material; and
- one or both wall boundaries are interrupted rather than pristine four-run rectangles.

The interruptions are ordinary B-rep consequences of other geometry: extra straight boundary
segments, inner wires, and curved edges from holes or adjacent features. They do not weaken the
empty-prism, complete-seam, terminal, or material proofs.

If a subsequent recogniser increment accepts this motif without losing precision, the measured
upper bound is 92/181 component-proxy recall (50.83%) and 184/415 defining-face recall (44.34%).
Those are projections from the audit, not claimed post-implementation results.

## Evidence and denominators

| Measure | Recalled | Unrecalled | Total |
| --- | ---: | ---: | ---: |
| Class-8 labelled faces | 78 | 337 | 415 |
| Shared-edge same-class component proxies | 39 | 142 | 181 |

MFCAD++ does not provide publisher instance labels in this adapter. “Component” therefore means a
connected component of same-class original faces under shared-edge adjacency. The report does not
promote that proxy to native instance recall.

The machine artifact is
[`through-step-miss-audit-mfcadpp-500-2322328.json`](through-step-miss-audit-mfcadpp-500-2322328.json).
It records all 142 unrecalled components, 55 exact descriptor clusters, the broader explicit motif,
and deterministic samples from each cluster. Its selection hash
`323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df` matches the E5b
canonical 500-model selection.

## Method

The tool imports each selected STEP file, executes the ordinary aggregate inventory once, and
selects class-8 faces only for comparison. For each unrecalled shared-edge component it records:

- face count and analytic surface kinds;
- principal-plane orientation multiplicities and non-principal planar faces;
- internal and boundary convexity/concavity;
- pristine rectangular outer boundaries, inner wires, and curved boundary edges;
- inferred run axis and source-solid span;
- terminal-plane count; and
- the first failed production gate, including the exact empty-prism result where the geometry
  establishes a candidate prism.

Exact clusters use explicit descriptor tuples. Their grouping key omits world-axis names and raw
external-neighbour counts because those describe rigid presentation and surrounding-part
complexity rather than the feature motif. The broader boundary-interruption motif is also an
explicit conjunction of recorded descriptors; it is not a fitted cluster or learned similarity.

Two identical canonical runs of the final tool produced byte-identical JSON with SHA-256
`5819b5e196bc8f895248c983f35cdf60691bb950afa428f37d30c7e520eb8ec1`.

## Bounded manual validation

The first three deterministic samples of the largest exact cluster were inspected:

- model `10308`, faces 6 and 8: one six-edge straight planar wall and one four-edge rectangular
  wall;
- model `10363`, faces 2 and 3: one four-edge wall and one six-edge straight planar wall; and
- model `10465`, faces 1 and 15: one four-edge wall and one six-edge straight planar wall.

All three have one concave wall join and retain the full-run, two-terminal, and empty-prism proofs.
Inspection was limited to these deterministic samples; MFInstSeg was not inspected.

## Recommendation

Open one focused recogniser increment for **interruption-tolerant two-wall through steps**. Preserve
every current acceptance proof and replace only the requirement that both wall regions have a
pristine four-run rectangular boundary. The authored contract should require the wall planes and
their inferred envelope, complete concave seam, source-solid span, both terminals, absence of a
third co-spanning concave wall, and exact empty prism.

Required authored adversaries include material ribs in the inferred prism, incomplete seams,
missing terminals, non-envelope walls, third walls, non-planar/tapered walls, and interruptions
that change the concave seam itself. Positive cases should cover an inner wire, a convex straight
notch, a curved hole interruption, rotations, scale, STEP round-trip, face splits, and traversal
order. The increment should rerun the canonical precision/recall and paired performance evidence;
it should be closed without implementation if the relaxed boundary proof cannot retain precision.

The next-largest exact cluster is only 13 components, so implementing smaller variants before this
motif would not be evidence-led.

## Architecture review

ADRs 0001, 0002, 0004, 0007, 0008, and 0011 were reviewed before the audit. This increment changes
only repository tooling, tests, and immutable benchmark evidence. It adds no public API, record,
production dependency, recogniser threshold, frame policy, or candidate/evidence authority.

## Reproduction

```console
uv run python tools/audit_mfcadpp_through_steps.py \
  /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --limit 500 \
  --output docs/benchmarks/through-step-miss-audit-mfcadpp-500-2322328.json
```

The path is environmental; the lexical selection rule and selected-ID hash are recorded in the
artifact. Corpus files are not vendored.
