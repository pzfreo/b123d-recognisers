# Fragmented circular-end Pocket assessment

Issue: #474  
Baseline: `8426e7d` (`0.4.15.dev0`)  
Source report: `mfcadpp-circular-end-pocket-audit-299f203.json`

## Decision

Do not add a fragmented-obround `Pocket` rule under the current record contract. The open
MFCAD++ residual does not contain a complete, label-independent obround footprint from which the
existing `Pocket` dimensions can be proved. Recognition remains fail-closed and the active work
moves to the larger polygonal Pocket detection queue.

No MFInstSeg model was inspected. Owner-supplied aggregate MFInstSeg results establish priority
only: Circular end Pocket remains a large transfer residual. They do not supply geometry rules.

## Evidence

The existing full 2,500-model MFCAD++ audit reports 53 untouched connected class-16 component
proxies / 166 faces at `fragmented_anatomy`. Decomposing its recorded, pre-existing geometric
probe fields gives:

| condition | component proxies |
| --- | ---: |
| missing the required two cylindrical ends | 41 |
| missing the required three planar members | 43 |
| missing at least one of those requirements | 53 |
| zero or one cylindrical end | 37 |
| retaining two individually supported semicircular ends | 1 |

Thus every proxy lacks an essential part of the bounded obround proof. This is not a failure to
join split coplanar or coaxial patches: `_obround_ends` already inventories and groups original
patches across the whole source solid, independently of dataset components, and the source audit
found zero overlap between any untouched proxy and an existing Pocket proposal.

A read-only topology inspection of representative dominant shapes (`10746`, `11314`, `1254`,
`1302`, and `14966`) confirms the interpretation. The class-16 region is terminated or divided by
faces belonging to another physical feature; common forms retain one curved end, a floor fragment,
or a branched chain of several cylinders but not one closed two-ended obround. Across all 53
proxies, 15 directly border another class-13/14/15 Pocket-family component. The remainder commonly
border other machining classes or stock faces. These labels describe the audit population only;
they are not used as recognition predicates.

## Architectural boundary

The existing `Pocket` record promises a complete width, overall length, centreline, longitudinal
bounds, depth interval and opening direction. A cavity with one end erased by an intersection does
not geometrically establish those values. Recovering it would require either inferred historical
design intent or a new partial/intersected-feature schema and ownership contract. Neither is a
local recognition fix, and silently fabricating the absent endpoint would conflict with ADRs 0002,
0003, 0004, 0008 and 0010.

This negative result does not claim that circular-end recognition is complete. The source audit
also records 285 non-principal faces, but those require an explicit oriented-record decision and
remain separate. The result only refutes split-patch reduction as a safe explanation for the 166
fragmented-anatomy faces.

## Reproduction

The exact source counts are obtained without rerunning recognition:

```console
jq '[.components[] | select(.untouched and
  .probe.first_failed_gate == "fragmented_anatomy")] |
  {proxies: length,
   faces: (map(.face_count) | add),
   missing_cylinder_pair: (map(select(.probe.cylinder_faces != 2)) | length),
   missing_three_planes: (map(select(.probe.planar_faces != 3)) | length),
   incomplete: (map(select(.probe.cylinder_faces != 2 or .probe.planar_faces != 3)) | length),
   supported_pair: (map(select(.probe.individually_supported_ends == 2)) | length)}'
  docs/benchmarks/mfcadpp-circular-end-pocket-audit-299f203.json
```
