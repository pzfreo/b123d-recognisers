# E5 rectangular-passage gap audit

Issue [#411](https://github.com/pzfreo/b123d-recognisers/issues/411) audits the largest
remaining unaudited wholly untouched MFCAD++-500 class bucket after #409. It reuses the
source-pinned production-proof harness and changes no recognition behavior.

## Reproduction

The immutable report is
[`effectiveness-mfcadpp-500-rectangular-passage-gap-da86c7f.json`](effectiveness-mfcadpp-500-rectangular-passage-gap-da86c7f.json).
It pins audit implementation commit `da86c7fe1f83d71cedc7782b92ca50ba4d049321`, the production
`_section_passages.py` SHA-256, the 500 lexical model IDs, and every selected STEP-file hash.
Generate it with:

```console
uv run python tools/audit_mfcadpp_section_passage_gaps.py \
  /path/to/MFCAD++_dataset/step/test \
  --class-id 3 \
  --limit 500 \
  --output docs/benchmarks/effectiveness-mfcadpp-500-rectangular-passage-gap-da86c7f.json
```

MFCAD++ supplies per-face classes but no native feature-instance identity. Connected same-label
faces are therefore component proxies, not asserted physical occurrences. Labels select the
population only. The probe applies unchanged production helpers to each proxy as diagnostic
anatomy; real global `section_ring_proposals` overlap and accepted defining/constituent evidence
are recorded independently.

Authored controls prove that an intact rectangular through passage reaches the exact production
proposal, a capped rectangular void reaches only the material/open-end refusal, a principal-axis
rotation preserves the decision, and equal passages on separate bodies retain distinct
valid-solid ownership. Triangle and six-sided controls remain alongside them.

## Result

The fixed selection contains 912 class-3 faces in 191 proxies across 149 models. Accepted
all-family constituent evidence touches 165 proxies, fully covers 108, and covers 658 faces.
Passage evidence touches 92 proxies, fully covers 89, and covers 397 faces. There are 94
components with at least one real production section-ring proposal overlap.

The 26 wholly untouched proxies contain 107 faces across 18 models. None overlaps a production
proposal and none passes the unchanged proof sequence. Every one fails simple-cycle closure:

| Proxy anatomy | Proxies | Full-span junction pairs |
| --- | ---: | ---: |
| Four planar faces, four geometric junction pairs | 17 | 2 |
| Four planar faces, four geometric junction pairs | 5 | 3 |
| Four planar faces, only three geometric junction pairs | 1 | 3 |
| Five planar faces, six geometric junction pairs | 3 | 2 |
| **Total** | **26** | — |

An intact rectangular ring requires all four walls to form one degree-two cycle at a common full
run. The 23 four-face proxies retain only two or three full-span junctions; the three five-face
proxies retain two. One missed population also has an oblique run, so the shared failure is not a
world-axis restriction.

## Decision

Close #411 without a production change. The residual class-3 bucket contains rectangularly
labelled wall fragments interrupted by other topology, not an intact through passage rejected by
one presentation gate. Accepting them would require reconstructing missing full-span junctions,
splitting or joining label regions, or replacing original adjacency with a corpus-derived
rectangle inference.

This preserves ADRs 0002, 0003, 0004, 0007, 0008, 0009, 0010, and 0011:

- no record, discovery predicate, reconciliation, public evidence, or frame contract changes;
- no coordinate rematching, inferred graph identity, cross-solid merge, or new tolerance;
- no dataset label enters production discovery or widens constituent membership; and
- the transformed and compound controls preserve covariance and body-local identity.

MFCAD++ effectiveness is unchanged by construction, so no redundant before/after aggregate report
is published. MFInstSeg was neither run nor inspected; this audit is not a transfer milestone.
