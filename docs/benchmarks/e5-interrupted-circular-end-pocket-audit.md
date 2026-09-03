# E5 interrupted circular-end Pocket audit

Issue [#470](https://github.com/pzfreo/b123d-recognisers/issues/470) tests whether the polygonal
partial-mouth recovery has a useful curved-boundary analogue for residual Circular end Pocket
coverage. This is a diagnosis-only result: it changes neither recognition nor public records.

## Authored controls

Sharp and completely chamfered or filleted blind obround Pockets remain positive controls. Two
additional constructions interrupt only a bounded straight portion of the obround mouth with a
chamfer or rolling fillet. Both are already recognised once, retain their 10 by 16 by 6 dimensions,
and attach more than the defining walls and floor as constituent evidence. A through obround is
not a Pocket. Unequal-radius rounded ends do not authorize obround extension; the independently
proved rectangular core may still be reported at its honest 10 by 12 dimensions. Oblique and
fragmented probes retain their existing first-failure classifications, and equal Pockets on
separate bodies retain distinct owners.

These controls refute the broad hypothesis that ordinary entry treatments explain the missing
Circular end Pocket occurrences. They do not prove that every fragmented or interacting curved
cavity is supported.

## Full MFCAD++ development evidence

The immutable report is
[`mfcadpp-circular-end-pocket-audit-299f203.json`](mfcadpp-circular-end-pocket-audit-299f203.json),
SHA-256 `e86601d93249c4dd55e863394e47f96aef6fab66665776ed3c864580d060818a`.
It pins production commit `299f2032f0dbea4b3e17c49f7535dbf5630b4407`, production-source hashes,
the published dataset identity, lexical selection and every selected source hash.

```console
uv run python tools/audit_mfcadpp_circular_end_pocket_gaps.py \
  /path/to/MFCAD++_dataset/step/test \
  --class-id 16 --limit 2500 --allow-invalid \
  --output /tmp/mfcadpp-circular-end-pocket-audit.json
```

The selection contains 706 models with class 16. Model 22386 is the only one of the seven
documented corpus-invalid models in that class-bearing workload and produces the exact expected
`Hole cylindrical evidence does not prove one valid solid` refusal. The remaining 705 models
contain 922 connected same-label component proxies / 4,536 class-16 faces. MFCAD++ supplies face
classes rather than native feature-instance identity, so these remain explicitly component
proxies.

Accepted constituent evidence reaches 808 proxies / 4,065 faces. The 114 wholly untouched proxies
contain 471 faces:

| First failed geometric gate | Proxies | Faces |
| --- | ---: | ---: |
| Non-principal side walls | 57 | 285 |
| Fragmented anatomy | 53 | 166 |
| Not two supported semicircular ends | 3 | 15 |
| Centreline grouping mismatch | 1 | 5 |

No untouched proxy overlaps an existing Pocket proposal. In particular, the audit exposes no
separate treatment-mouth gate that could support a general curved analogue of the polygonal
recovery. Non-principal geometry is outside the raw principal-axis recogniser contract and belongs
through explicit framing. Fragmented anatomy is not one invariant: it includes topology that no
longer proves exactly two caps, two joining principal walls and one floor, and therefore cannot be
widened as a group.

## Decision and transfer interpretation

Close #470 without a production recogniser change. A treatment-specific patch would duplicate
behavior already demonstrated by authored controls and would not address the measured full-corpus
residual. The five-face centreline case is too small to displace the higher-value Pocket work, and
the non-principal and fragmented buckets need different contracts rather than relaxed obround
tolerances.

The user-provided aggregate MFInstSeg comparison reports 2,024 residual Circular end Pocket faces,
substantially more than the 471 untouched MFCAD++ faces. No individual MFInstSeg model was opened.
That mismatch is transfer evidence that MFCAD++ does not reproduce the dominant residual
distribution for this family; it is not authority to infer geometry from the holdout. The next
priority returns to #460's deeper split, branched, shared and intersected Pocket investigation,
which also addresses the much larger overall Pocket residual.

## ADR conformance

ADRs 0002, 0003, 0004, 0007, 0008, 0009, 0010, 0011 and 0013 remain unchanged. Geometry is built
before labels are read; labels only measure accepted evidence and first refusal gates. Exact
run-local topology, one-solid ownership, existing obround tolerances, Candidate issuance,
reconciliation, public evidence and schema are untouched. The audit does not create a second
recogniser, consume sibling-family Candidates, publish adjacency, or infer membership after
acceptance. MFInstSeg was neither inspected nor rerun.
