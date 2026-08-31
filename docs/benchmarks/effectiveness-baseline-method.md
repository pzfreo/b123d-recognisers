# Recognition effectiveness baseline method

This is the reproducible evidence contract for Epic 0005 E0 ([#293](https://github.com/pzfreo/b123d-recognisers/issues/293)).
It measures the shipped aggregate recogniser against external annotations without making those
annotations recognition policy.

## Evidence authority

Each model is imported once and passed once through the package's frozen `InventoryProduct`.
Counts come from accepted physical candidates; defining-face comparisons come from the evidence
owned by those candidates; reconciliation drops come from final dispositions; supported residuals
come from the existing bounded diagnostics. The scorer never calls individual recognisers and does
not reconstruct candidate ownership from public record coordinates.

This follows ADR 0003's one-inventory and reconciliation authority and ADR 0004's distinction
between geometric evidence and corpus labels. A matching label is comparison evidence, not
permission to change ownership, tolerance, or public semantics.

Historical reports through E5d use
[`effectiveness-taxonomy-v1.json`](effectiveness-taxonomy-v1.json). E5f and later reports use
[`effectiveness-taxonomy-v2.json`](effectiveness-taxonomy-v2.json), which moves MFCAD++ class 21
from the former Fillet proxy to the dedicated Circular Blind Step family. Reports after the
class-7 scope audit use [`effectiveness-taxonomy-v3.json`](effectiveness-taxonomy-v3.json), which
marks MFCAD++/MFInstSeg `Circular through slot` unsupported: the audited corpus geometry is an exact
semicylindrical groove, outside the shipped two-opposed-wall `Slot` contract. Reports after the
rectangular class-6 audit use [`effectiveness-taxonomy-v4.json`](effectiveness-taxonomy-v4.json),
which marks `Rectangular through slot` partially supported: the corpus class mixes a dominant
open-ended three-wall edge slot with closed, free-axis and intersected variants, rather than one
geometry covered by the enclosed `Slot` record. Every published class is `supported`, `partial`,
`unsupported`, or `incomparable`; `Stock` is incomparable. A supported or partial class names all
package families that can legitimately report that geometry. This is deliberately many-to-many:
for example, a rectangular ring can be proposed by both Pocket and Prismatic Pocket machinery,
while aggregate reconciliation decides which occurrence survives.

`partial` preserves honest matched evidence and denominators when a corpus class contains a
geometrically supported subset but its label also covers materially different shapes outside the
mapped family contract. It qualifies interpretation; it does not turn out-of-contract faces into
false negatives or authorize a production predicate. Reports retain the full class numerator and
denominator so readers can see the mixed-class agreement rather than erasing genuine matches.

## Metrics and denominators

Every ratio is stored as `{numerator, denominator, value}`. `value` is `null`, not zero, when the
denominator is zero.

- **Physical records** count accepted candidates by stable package family ID.
- **Mapped dataset-class records** assign an accepted occurrence to the supported class that owns
  the largest number of its defining faces. A tie is `ambiguous`; no matching defining face is
  `unmapped`. This is a comparison projection and does not rename the package record.
- **Defining-face recall** is supported-class labelled faces claimed by a mapped accepted family
  divided by all faces carrying that class label.
- **Face coverage** is class-labelled faces present in the defining evidence of any accepted
  physical candidate, regardless of which family owns that candidate, divided by all faces
  carrying the class label. It reports whether accepted recognition touches a labelled face; it
  does not transfer ownership to the labelled class. Coverage must be read beside defining-face
  precision and recall: claiming every face would maximize coverage without producing truthful
  recognition.
- **Defining-face precision** uses the same matched faces over every defining face claimed by a
  family mapped to that class. A family mapped to several corpus classes therefore has a separate
  one-vs-class denominator for each; it is not a composite accuracy score.
- **Instance recall** is supported truth instances touched by at least one defining face of a
  mapped accepted candidate divided by supported truth instances. It measures detection, not exact
  instance localization. MFCAD++ has no instance relation, so its denominator is zero; MFInstSeg
  supplies the relation.
- **Taxonomy mismatch** counts defining-face occurrences whose supported label does not map to the
  accepted candidate family. Incomparable and unsupported labels do not become false positives.
- **Empty models**, reconciliation drops, bounded unsupported diagnostics, predicate observations,
  and runtime remain separate fields. They are not folded into accuracy.

MFCAD++ and MFInstSeg assign one semantic label per face. Shared and stock-contact faces can make a
correct multi-face occurrence look impure. The report preserves that mismatch instead of letting
the dataset overrule the reconciler.

Defining-face recall has a structural ceiling below 1.0 for classes whose annotations include
faces that the package deliberately does not consume as defining evidence. For example, opposed-
wall recess recognition defines an occurrence by its walls rather than claiming its floor, and
the class-11 O-ring audit in #360 found labelled geometry truthfully owned by Fillet. Face coverage
exposes accepted cross-family claims in this gap; it does not replace defining-face recall or
erase genuinely untouched faces. Constituent evidence, where a record can publish non-defining
members without claiming ownership, is a separate contract tracked by #368 and is not inferred by
this scorer.

## Dataset adapters

### MFCAD++ development evidence

The adapter reads the published integer class from each STEP `ADVANCED_FACE` name. It then requires
the imported face count to match exactly. Selection is unique model ID in lexical order. The local
development archive used for E0 is expected at:

```text
/app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test
```

Run the deterministic first 500 test models:

```bash
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version published-test-split \
  --limit 500 \
  --output docs/benchmarks/effectiveness-mfcadpp-500-0.5.0.json
```

The frozen result and interpretation are in the
[`0.5.0 MFCAD++ baseline`](effectiveness-mfcadpp-500-0.5.0.md).

MFCAD++ is open development evidence. Models and labels may be inspected to diagnose omissions.
The report remains a false-negative detector and regression baseline, not an independent transfer
estimate.

### MFInstSeg transfer evidence

The adapter expects the original published layout:

```text
DATASET_ROOT/steps/MODEL_ID.step
DATASET_ROOT/labels/MODEL_ID.json
PARTITION_ROOT/{train,val,test}.txt
```

It validates exact face keys, semantic/bottom lengths, binary bottom labels, a symmetric square
instance matrix, disjoint equivalence classes, within-instance semantic consistency, duplicate
test rows, and IDs appearing in more than one split. Duplicate or cross-split IDs are disclosed
and excluded before lexical selection.

MFInstSeg is distributed through authenticated sources and is not present in this workspace. Do
not replace it with MFCAD++ or generated fixtures. After the original files and the upstream
partition directory are mounted, run:

```bash
uv run python tools/run_effectiveness_baseline.py \
  mfinstseg /absolute/path/to/MFInstSeg \
  --partition-root /absolute/path/to/AAGNet/MFInstseg_partition \
  --dataset-version published-original \
  --limit 500 \
  --output docs/benchmarks/effectiveness-mfinstseg-500-0.5.0.json
```

Do not inspect individual MFInstSeg model geometry during baseline creation. If later work inspects
one, record its ID and affected class; that class is no longer described as independent transfer
evidence for the milestone.

## Failure and immutability policy

Missing roots, malformed labels, unknown classes, face-count mismatch, import failure, non-finite
runtime, or a malformed taxonomy fail closed. By default, any invalid selected model prevents an
output file. `--allow-invalid` exists only when a written benchmark policy names the expected
invalid cases; the report then preserves each invalid model and reason.

Effectiveness report format version 2 adds per-class `covered_faces` evidence and the derived
`face_coverage` ratio. Historical version-1 reports remain immutable rather than being rewritten.
Reports are canonical JSON with sorted model IDs, exact package commit/version, runtime
environment, selection hash, taxonomy hash, per-model source hash, exact counts, and runtime
distribution. Never rewrite a historical report after changing scorer logic. Produce a new report
and explain which denominator changed.

## Separate non-corpus arms

The corpus report does not absorb the package's other evidence:

- semantic goldens: `uv run pytest -q tests/test_golden_parity.py`;
- real parts: `uv run pytest -q tests/test_nist_ctc_corpus.py tests/test_turned_real_part.py`;
- performance: the two commands in
  [`recognition-budget.md`](recognition-budget.md#running-it), compared on the same machine.

Keeping these arms separate prevents synthetic label agreement from masquerading as downstream or
real-part effectiveness.
