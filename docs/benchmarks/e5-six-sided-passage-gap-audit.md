# E5 six-sided-passage gap audit

Issue [#398](https://github.com/pzfreo/b123d-recognisers/issues/398) audits the largest
remaining wholly untouched MFCAD++-500 class bucket after paired-ramp recognition landed. It is
an evidence result, not a production recognition change.

## Reproduction

The immutable report is
[`effectiveness-mfcadpp-500-section-passage-gap-9949949.json`](effectiveness-mfcadpp-500-section-passage-gap-9949949.json).
It pins audit implementation commit `9949949`, the production `_section_passages.py` SHA-256,
the 500 lexical model IDs, and every selected STEP-file hash. Generate it with:

```console
uv run python tools/audit_mfcadpp_section_passage_gaps.py \
  /path/to/MFCAD++_dataset/step/test \
  --class-id 4 \
  --limit 500 \
  --output docs/benchmarks/effectiveness-mfcadpp-500-section-passage-gap-9949949.json
```

MFCAD++ supplies per-face classes but no native feature-instance identity. The audit therefore
uses connected same-label original faces as **component proxies**. Labels select geometry to
describe; they do not participate in discovery, topology proofs, material tests, or acceptance.

For each proxy, the audit applies the unchanged production section-ring helpers as a diagnostic
counterfactual and separately records overlap with proposals discovered globally by the real
production entry point. A failed component probe is anatomy, not a claim that all labelled faces
ought to form one public occurrence. Accepted defining and constituent evidence is reported
separately and overlap is not treated as semantic ownership.

## Result

The fixed selection contains 1,336 class-4 faces in 200 component proxies across 147 models.
Accepted all-family evidence fully covers 100 components and Passage evidence fully covers 94.
There are 95 components with at least one real production section-ring proposal overlap.

The 79 wholly untouched proxies contain 562 faces. None overlaps a production section-ring
proposal and none passes the unchanged proof sequence:

| First failed diagnostic proof | Components | Faces |
| --- | ---: | ---: |
| Simple closed cycle | 71 | 471 |
| Equal full-run intervals | 4 | 30 |
| Every component face is an eligible planar wall | 4 | 61 |
| **Total** | **79** | **562** |

Of the 71 cycle failures, 46 are six-plane proxies. Forty-two of those already lose at least
two of the six required full-span junctions; the remaining four also fail degree-two closure.
The other 25 cycle failures contain 2–10 planar fragments. The four wall-eligibility failures
contain 12–18 labelled planes but only 4–6 walls perpendicular to their best available run.

Model `10007` is representative rather than exceptional: its labelled six-wall region has four
walls spanning the full run and two walls terminating at an intersecting feature. Joining those
short walls to manufacture a cycle would discard original adjacency and complete-span evidence.
The wider population also contains fragmented and multi-region label proxies, so “six planar
faces” is not a sufficient physical contract.

## Decision

Close this audit without a production child. The residual bucket is not an intact free-axis
six-sided passage hidden behind one presentation gate. Every wholly untouched proxy would require
reconstructing missing section boundaries, splitting a label component into an inferred subset,
or accepting unequal physical spans. None of those operations is justified by existing original
topology, one-body ownership, and two-open-end evidence.

That conclusion preserves ADR 0004's graph-owned identity and original topology, ADR 0008's
explicit tolerance authority, ADR 0009's recogniser-local filtering, and ADR 0010's prohibition on
inventing wider constituent membership from adjacency or corpus labels. A future interrupted-
passage feature needs a consumer-backed semantic contract for intersections and explicit authored
positive and adversarial geometry; it must not start by weakening `SectionPassage` to fit class 4.

The next #369 target should be selected from the refreshed untouched-component census rather than
continuing into this heterogeneous group. MFInstSeg was not used or inspected for this audit.
