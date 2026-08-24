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
implementation begins. `F5-FLATS-H1` is bucket 20 and is `sealed_unrevealed`; it is excluded from
ordinary `unselected` scans and requires the exact allocation acknowledgement. The scanner keeps
`all` closed while named sealed allocations exist, so generic holdout authority cannot reveal one.
Repository chronology records no earlier unselected scan, which is an attestation about recorded
runs rather than a claim that external access was impossible. A later authorised family issue owns
the one reveal and the transition to consumed regression evidence.

The two draws are disjoint. Development outcomes may be inspected. Holdout outcomes stay sealed
until a semantic child has two independent pre-reveal accepts; after reveal they become regression
evidence and cannot be fitted. Buckets 20–999 are outside both draws. This keeps each draw near one
percent without depending on class, topology, recognition result, or archive traversal order.
The scanner refuses both `--selection holdout` and `--selection all` unless the authorised caller
also supplies the explicit `--reveal-holdout` acknowledgement.

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
