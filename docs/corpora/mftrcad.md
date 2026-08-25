# MFTRCAD external evidence contract

MFTRCAD is a large synthetic feature-recognition corpus. It is useful here for locating
interaction and representation gaps; it is not an oracle for this package's feature names or
reconciliation policy. The dataset remains external and no model is redistributed by this
repository.

## Provenance and licence

The audited artifact is Kaggle dataset `xmy2000/mftrcad`, dataset id `4762595`, version 1,
created 2024-04-09. Kaggle reports the dataset licence as MIT, 2,380,602,881 compressed bytes and
41,721,064,518 expanded bytes. The corresponding generator is
[`xmy2000/MFTReNet`](https://github.com/xmy2000/MFTReNet); the source audit used commit
`3ae17a43dde22e4f27c5d7df179838d92551c28c`, whose repository licence is also MIT.

Those facts permit an external audit; they are not a decision to vendor 42 GB of generated data.
Any future vendored subset needs its own provenance and redistribution review.

## File and identity contract

One complete model is the triple:

- `steps/<model_id>_result.step`;
- `labels/<model_id>_result.json`, containing `cls`, `seg`, and `bottom`;
- `labels/<model_id>_result_rel.json`, containing `relation`.

`cls` maps zero-based OCCT face-list positions to semantic labels. `seg` lists the faces in each
generated feature instance; an entry can legitimately be empty after feature interaction and
STEP remapping. Relationships name instance positions, not faces. The generator reloads STEP and
builds the label map with pythonOCC `TopologyExplorer`, which follows raw OCCT `TopExp_Explorer`
order. The scanner imports the same STEP and proves build123d's face sequence is `IsSame` at every
position to an independent raw `TopExp_Explorer` walk. It also requires contiguous canonical face
ids, exact `bottom` coverage and an agreeing imported face count before joining Candidate evidence
to a label. It never uses a label to accept or reject a Candidate. A wrapper/kernel traversal drift
therefore refuses attribution rather than silently permuting labels.

The generator says it checks BRep validity, manifoldness, closure and unique coedges before writing
a sample. The scanner independently checks imported BRep validity and single-solid scope; it does
not reimplement the generator's manifold and unique-coedge algorithms. The published archive is
nevertheless incomplete or internally inconsistent. In the fixed development draw, one selected
STEP has no annotation pair, four complete triples repeat an instance id in a relationship, and
two imported BReps fail OCCT validity. The scanner refuses these conditions by default.
`--record-invalid` may retain a deterministic error in an audit report, but malformed models do
not contribute evidence. STEP import exceptions are also retained in that explicit mode rather
than aborting the remainder of the selected audit; unexpected scanner or recognition exceptions
still fail the run.

## Taxonomy

MFTRCAD labels 0–23 are generated machining-feature names; 24–26 are plane, cylinder and cone
surface classes. The complete numeric mapping is executable in `tools/mftrcad_audit.py`.
`PACKAGE_FAMILIES_BY_LABEL` is deliberately many-to-many where package contracts overlap and
empty where there is no corresponding supported family. In particular:

- triangular, rectangular and six-sided passages compare with `passages`;
- through-slot variants compare with `slots`;
- rectangular and polygonal pockets compare with `pockets` and/or `prismatic_pockets`;
- triangular blind steps compare with `angled_steps`;
- rounds and the corpus's circular blind step compare with `fillets`;
- through-step classes 8–10 currently have no package family;
- plane, cylinder and cone labels are substrate, not feature records.

This mapping only reports alignment of defining faces. A mismatch may be a taxonomy difference,
an interaction, incomplete package ownership evidence, or a recogniser defect. It is never a
reconciliation rule or a score optimized by a predicate.

The seven relationship kinds accepted from version 1 are `superpose_on`, `transition`,
`general_paratactic`, `line_array`, `circle_array`, `mirror`, and `intersecting`. They identify
useful development populations. They do not imply Candidate ownership.

## Deterministic development and holdout draws

The checked-in [selection manifest](mftrcad-selection.json) fixes membership before recognition:

```text
bucket = uint64_be(sha256("b123d-recognisers:mftrcad:v1" + NUL + model_id)[0:8]) mod 1000
development = buckets 0..9
holdout     = buckets 10..19
```

Named semantic-family allocations are carved out of the remaining partition before their
implementation begins. `F5-FLATS-H1` is bucket 20 and is now `consumed`; it remains excluded from
ordinary `unselected` scans and requires the exact allocation acknowledgement. The scanner keeps
`all` closed whenever named allocations exist, including consumed allocations; exact named
selection remains mandatory and generic holdout authority cannot reveal one.
`F5-FILLETS-H1` is bucket 21 and is now `consumed`; it was designated without opening the external
archive or inspecting bucket-21 membership or outcomes, then revealed once only after #201's frozen
exact-head implementation had two independent accepts and all mechanical gates. It remains excluded
from `unselected`, requires its exact acknowledgement, and cannot be reused as sealed evidence.
`F5-COUNTERSINKS-H1` is bucket 22 and is now `consumed`. It was designated for #205 without opening
the archive, then revealed exactly once after the frozen implementation passed two independent
accepts and all mechanical gates. The selection contained 36 model triples (108 files), but the
audit aborted when model `20240116_231044_6899` imported as an invalid B-rep, before a complete
report or Countersinks attribution result existed. The allocation is therefore inconclusive and
cannot be rerun, replaced, reused, or fitted. No alternate scanner mode was attempted.
`F5-BOSSES-H1` is bucket 23 and is now `consumed`. It was designated for #209 without opening the
archive, then revealed exactly once after the frozen implementation passed two independent accepts
and all mechanical gates. The selection contained 32 model triples (96 files), but the audit
aborted when model `20240124_001736_209` imported as an invalid B-rep, before a complete report or
Bosses attribution result existed. The allocation is therefore inconclusive and cannot be rerun,
replaced, reused, or fitted. No alternate scanner mode was attempted.
`F5-DOUBLE-D-BORES-H1` is bucket 24 and is now `consumed`. It was designated for #213 without
opening the archive or inspecting bucket-24 membership, geometry, annotations, or outcomes, then
selected exactly once at accepted PR #215 head `80def7f`. No model matched the allocation, so the
scanner stopped before STEP import, annotation reading, recognition or complete report creation.
The zero-population draw is permanently inconclusive and is not regression evidence. It cannot be
rerun, replaced, reused or fitted; no alternate selection or scanner mode was attempted.
`F5-POLYGONAL-BOSSES-H1` bucket 25 is now `consumed`. It was selected exactly once at accepted
PR #223 head `ff3ce83`: 22 complete models, 66 selected files, 599 faces and zero invalid models.
The completed scanner report contained zero physical, accepted or attributed Polygonal Boss
Candidates. It is therefore negative regression evidence only and supplies no positive ownership
or side-versus-cap claim. The selected-artifact SHA-256 is
`caf1f57ccc142697d10a8d74527ad08c4bdfa3e7a34dfab71518dda32f739eb4`; the report SHA-256 was
`43aa6950f0f8781972ad1ba8c1c3a36ec4d6c89c65e227826915d96b137e2a28`. No retry, alternate
selection or fitting was performed, and the temporary extracted selection/report were deleted.
`F5-PADS-H1` bucket 26 is now `consumed`. It was selected exactly once at accepted PR #224 head
`f8322bd`: 24 complete models, 72 selected files, 572 faces and zero invalid models. The completed
report contained four physical, four accepted and four attributed Pad Candidates, with 20 claimed
face occurrences. This proves zero reconciliation loss and an average of five defining occurrences
per Candidate, not a per-Candidate cardinality vector; the generic scanner did not independently
reconstruct the top-versus-wall roles, maximal-base choice or tier context. The selected-artifact SHA-256 is
`20a25c12b9da60142c60526cf20fcd1e1435b7a2b0c2f9dae4d665e38561c611`; the report SHA-256 was
`3d63840c836ae9925f2903c8f338c8b8a2d17a4e44f7c7692f3e048741396e1f`. No selected-scan rerun
after corpus access, alternate selection or fitting was performed, and the temporary extracted
selection/report were deleted.
`F5-HOLES-H1` bucket 27 is now `consumed`. It was selected once at accepted pre-reveal PR #227
head `2ddf17e`, after 1,568 full tests, static/package/performance/CI gates and two independent
exact-head accepts. The deterministic selection contained 35 model triples (105 files). The
scanner stopped while validating annotations because
`20240124_001736_4786_result_rel.json` repeats an instance id in `relation[0]`, before that model's
STEP import or recognition. The overall audit produced no complete report, so no aggregate Hole
counts or attribution outcomes are available or claimable. The temporary selection/report were deleted;
no retry, alternate mode, replacement or fitting followed. The allocation is permanently
inconclusive and is not regression evidence. The Wave 1 allocations were designated by neutral
#216 without outcome access; authority remains exact and non-transferable.
`F5-CHANNELS-H1` bucket 28 was selected exactly once at accepted pre-reveal PR #230 head
`bdbe3cc`. The deterministic selection contained 28 model triples (84 files; selected-artifact
SHA-256 `b9995ccd4acb273b2e1a2d81942bb848c838d3b65d8a51b75461bf4288b73319`). Annotation
validation stopped because `20240125_003844_2492_result_rel.json` repeats an instance id in
`relation[0]`, before that model's STEP import or recognition. The overall audit produced no
complete report, so no aggregate Channel counts or attribution outcomes are available or
claimable. The temporary selection was deleted; no retry, alternate mode, replacement or fitting
followed. The allocation is permanently consumed and inconclusive, not regression evidence.
`F5-PLATES-H1` bucket 29 was selected exactly once at accepted pre-reveal PR #231 head
`b1bdcf3`. The deterministic selection contained 39 model triples (117 files; selected-artifact
SHA-256 `e5b57ca085664bba044379d8f2aca8c7f7807f201f22a8bbdab507d26735fa89`). Annotation
validation stopped because `20240124_001736_5206_result_rel.json` repeats an instance id in
`relation[0]`, before that model's STEP import or recognition. The overall audit produced no
complete report, so no aggregate Plate counts or attribution outcomes are available or claimable.
The temporary selection was deleted; no retry, alternate mode, replacement or fitting followed.
The allocation is permanently consumed and inconclusive, not regression evidence. The ordinary
`unselected` complement was then buckets 30..999.
`F5-POLYGONAL-STOCK-H1` bucket 30 was selected exactly once at accepted pre-reveal PR #237 head
`e884768`. The deterministic selection contained 37 model triples (111 files; selected-artifact
SHA-256 `9b987707e0307f8dcdd9cce2daffa2113c482e1c1069479ba58b3b31ed7f725e`). Annotation
validation stopped because `20240116_231044_1243_result_rel.json` was not a JSON object, before
that model's STEP import or recognition. The overall audit produced no complete report, so no
aggregate Polygonal Stock counts or attribution outcomes are available or claimable. The temporary
selection was deleted; no retry, alternate mode, replacement or fitting followed. The allocation
is permanently consumed and inconclusive, not regression evidence. The ordinary `unselected`
complement was then buckets 31..999.
`F5-SLOTS-H1` and `F5-POCKETS-H1` were independently designated at buckets 31 and 32 for #235 and
#236. Their neutral combined designation changed only the allocation policy, tests and
documentation: no archive, allocation membership, annotations, geometry or outcomes were opened.
Each selection requires only its own exact acknowledgement; neither acknowledgement authorizes the
other selection or any earlier allocation. An authorized zero, abort, invalid or completed reveal
consumes only that family's allocation without retry, replacement or fitting. The ordinary
`unselected` complement was then buckets 33..999.
At accepted PR #246 head `d4343ad`, after two independent exact-head accepts and all current-head
CI, coverage and focused gates, the one authorized `f5_slots_h1` selection with acknowledgement
`F5-SLOTS-H1` found zero models. Discovery stopped before annotation reading, STEP import or
recognition, so no report, artifact digest, counts or Slot attribution outcomes exist. The temporary
output directory was deleted; no retry, alternate root/allocation, replacement or fitting followed.
Bucket 31 is permanently consumed and inconclusive, not regression evidence.
At accepted pre-reveal PR #248 head `e20400c59b0381e03ca30eb9e6ab400689eea4dc`, after two independent exact-head accepts and all
current-head quality, package, performance, CI and coverage gates, one authorized Pocket attempt
created temporary root `/tmp/mftrcad-pocket32.UdUMnL`. The requested archive extraction could not
start because this host had no `unzip` command. The scanner was nevertheless invoked exactly once
with selection `f5_pockets_h1` and acknowledgement `F5-POCKETS-H1`; it rejected the still-empty
root because `steps/` and `labels/` were absent. No archive content was extracted or accessed, and
discovery never reached membership, annotations, STEP import, recognition, report construction,
digest, count or outcome collection. The temporary root was deleted. No retry, alternate extraction
tool/root/allocation, replacement or fitting followed. Bucket 32 is permanently consumed and
inconclusive, not regression evidence. Buckets 34 and 35 remain independently sealed; the ordinary
`unselected` complement remains buckets 36..999.
`F5-REPEATING-RADIAL-PROFILES-H1`, `F5-STEP-LEVELS-H1` and `F5-RISERS-H1` were independently
designated at buckets 33, 34 and 35 for #239, #240 and #241. Their combined neutral
designation changed only allocation policy, tests and documentation: no archive membership,
annotation, geometry, recognition result or outcome was inspected. Each token requires its own
exact acknowledgement and cannot authorize either sibling or any earlier allocation. An
authorized zero, abort, invalid or completed reveal consumes only that allocation without retry,
replacement or fitting. The ordinary `unselected` complement is now buckets 36..999.
At accepted PR #245 head `6ccbedc`, after two independent exact-head accepts and every local,
package, performance, CI and coverage gate, the one authorized
`f5_repeating_radial_profiles_h1` selection with acknowledgement
`F5-REPEATING-RADIAL-PROFILES-H1` found zero models. Discovery stopped before annotation reading,
STEP import or recognition, so no report, artifact digest, counts or attribution outcomes exist.
The temporary output directory was deleted; no retry, alternate root/allocation, replacement or
fitting followed. Bucket 33 is permanently consumed and inconclusive, not regression evidence.
Buckets 34 and 35 remain independently `sealed_unrevealed`.
Repository chronology recorded no earlier unselected scan, which is an attestation about recorded
runs rather than a claim that external access was impossible. Each authorised family issue owned
its one reveal and transition to a permanently consumed allocation. Completed reveals become
regression evidence; an aborted reveal remains consumed and inconclusive. The authorised F5c reveal at
PR #199 head `8796a86` contained 23 complete models and 69 files with no invalid models. It produced
10 Flat proposals, 10 accepted Flats and 10 attributed Flats. The selected-artifact digest was
`a2e045e3d6eb2b1ecd454fcbd12c04aaf5a4fb1ad85519891d8bcc48cd86356b`; this summary is regression
evidence, not a taxonomy-derived acceptance rule. The completed report contains 10 claimed Flat
faces, so nonempty-evidence arithmetic proves one defining face per attributed Candidate. The
scanner did not independently reconstruct the planar owner, stock cylinder or opposition geometry;
those exact role semantics remain established by the frozen development adversary matrix, not H1.

The authorised F5d reveal at PR #203 head `71be0b0` contained 21 complete models and 63 files with
no invalid models. It produced 6 Fillet proposals, 6 accepted Fillets and 6 attributed Fillets
across four models. The selected-artifact digest was
`6323bd2af053ada35952e8e7af4172a7da14bc0ec04ec4b3ec5b7b1275206f5a`. Six claimed
Fillet faces prove one defining face per Candidate by nonempty-evidence arithmetic. The generic
scanner did not reconstruct analytic owner/trim or turned-context geometry; exact role correctness
remains development-matrix evidence rather than an H1 claim.

The completed Flat and Fillet draws are disjoint. Development outcomes may be inspected. Holdout
outcomes stay sealed until a semantic child has two independent pre-reveal accepts. A completed
reveal becomes regression evidence; an aborted reveal remains consumed and inconclusive. Neither
may be fitted. Buckets 36–999 remain unselected; buckets 20 through 35 are the named Flat, Fillet,
Countersink, Boss, Double-D, Polygonal Boss, Pad, Hole, Channel, Plate, Polygonal Stock, Slot,
Pocket, Repeating Radial Profile, Step Level and Riser allocations. This keeps
each draw near one percent without depending on class, topology, recognition result, or archive
traversal order.
The scanner requires explicit authority for `--selection holdout` and keeps `--selection all`
closed; each named allocation accepts only its own exact acknowledgement.

The version-1 archive contains 301 STEP entries selected for development. Three hundred have both
annotation files; one (`20240125_003844_9903`) has neither and is recorded as an upstream archive
defect. Of the complete triples, 294 pass the annotation, topology and STEP-identity audit; four
are refused for repeated relationship members and two for invalid imported BReps. The compact checked-in
[`development baseline`](mftrcad-development-baseline.json) records the annotation, relationship,
physical-proposal, disposition, accepted-Candidate, defining-evidence and contested-ownership
totals. Its digest binds the 901 selected files actually audited to relative paths and bytes. The
holdout membership count and contents were not inspected during F0.

## Reproducing the audit

Download MFTRCAD version 1 separately and point the scanner at a root containing `steps/` and
`labels/`:

```bash
uv run python tools/mftrcad_audit.py /external/mftrcad \
  --selection development --record-invalid \
  --check-baseline docs/corpora/mftrcad-development-baseline.json \
  --json mftrcad-development-baseline.json
```

The command fails if the regenerated compact report differs from the committed baseline. Omit
`--check-baseline` and add `--json mftrcad-development.json` to retain the deterministic full
per-model report. That report separates annotation populations, relationship groups, all
physical proposals, dispositions, accepted Candidates, non-empty defining evidence, claimed
labels, touched instances, and contested proposal versus accepted ownership. Recognition joins use
original same-run `FaceNode` identity from the terminal frozen evidence index; rounded record
values and face traversal ids never act as Candidate identity.

MFTRCAD and the existing MFCAD++ fixtures are synthetic evidence. NIST CTC and the vendored turned
parts are reported separately as real-part evidence. No combined percentage is meaningful.
