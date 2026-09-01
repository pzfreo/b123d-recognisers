# E5 triangular-passage gap audit

Issue [#401](https://github.com/pzfreo/b123d-recognisers/issues/401) audits the next-largest
wholly untouched MFCAD++-500 class bucket after the six-sided-passage audit. It reuses the same
source-pinned production-proof harness and changes no recognition behavior.

## Reproduction

The immutable report is
[`effectiveness-mfcadpp-500-triangular-passage-gap-9f31f51.json`](effectiveness-mfcadpp-500-triangular-passage-gap-9f31f51.json).
It pins audit implementation commit `9f31f51`, the production `_section_passages.py` SHA-256,
the 500 lexical model IDs, and every selected STEP-file hash. Generate it with:

```console
uv run python tools/audit_mfcadpp_section_passage_gaps.py \
  /path/to/MFCAD++_dataset/step/test \
  --class-id 2 \
  --limit 500 \
  --output docs/benchmarks/effectiveness-mfcadpp-500-triangular-passage-gap-9f31f51.json
```

As in #398, connected same-label faces are component proxies because MFCAD++ has no native
feature-instance IDs. Labels select the audit population only. The probe applies unchanged
production helpers to one proxy as diagnostic anatomy; real global `section_ring_proposals`
overlap and accepted evidence are recorded independently.

## Result

The fixed selection contains 668 class-2 faces in 201 proxies across 153 models. Accepted
all-family evidence fully covers 103 components; Passage evidence fully covers 96. Exactly 96
components overlap a globally discovered production section-ring proposal.

The 63 wholly untouched proxies contain 212 faces. None overlaps a real production proposal and
none passes the unchanged proof sequence:

| First failed diagnostic proof | Components | Faces |
| --- | ---: | ---: |
| Simple closed cycle | 56 | 174 |
| Equal full-run intervals | 4 | 14 |
| Every component face is an eligible planar wall | 3 | 24 |
| **Total** | **63** | **212** |

Fifty cycle failures contain exactly three planar faces. Thirty-one retain only one of three
required full-span junctions and nineteen retain two, so none forms the degree-two closed cycle
required by an intact triangular passage. The other six cycle failures have four planar faces.
The span failures have three or four faces but no junction at which both incident walls retain the
complete run. The wall-eligibility failures have 6–10 labelled planes but only 2–3 walls
perpendicular to their best run.

Authored triangular controls demonstrate that the harness and production recogniser do accept an
intact arbitrary-axis triangle and reach the final material/open-end refusal for a capped
triangular void. The zero result is therefore not a missing triangle shape or world-axis rule.

## Decision

Close this audit without a production child. The untouched class-2 population is shortened,
interrupted, or multi-region geometry, not an intact triangular section excluded by one
presentation gate. Reconstructing its missing junctions would replace original adjacency and
complete-span evidence with an inference from dataset labels.

This retains the same ADR 0002/0003/0004/0007/0008/0009/0010 boundaries reviewed for #398: no new
record or reconciliation authority, no inferred graph identity, no unexplained tolerance, and no
corpus-driven constituent membership. Any future intersected-passage capability needs its own
consumer-backed semantics and authored adversaries. MFInstSeg was not used or inspected.
