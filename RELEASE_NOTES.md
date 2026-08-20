# Release notes

## 0.2.6

- **`feature_census` no longer counts a plate on a shaft whose steps form a turned profile.**
  `build_recognition_result` has always suppressed one there -- a stepped shaft is not a plate --
  and the census did not, so the two entry points reported different answers about the same
  solid. Measured across the 73 corpus parts it happened on exactly one, a real turned screw, and
  **a public count changes for it**: `plate` goes from 1 to 0. No semantic golden moves, because
  no pinned fixture carries the shape.

  The census applies the half of the aggregate's gate it can evaluate. The other half is the
  caller's `rotational` classification, which `feature_census(part)` does not take.

- **New family: `recognise_prismatic_pockets` / `PrismaticPocket`.** A floored recess of any
  planar cross-section, found by walking the closed ring of walls rather than pairing walls that
  share a normal axis. `recognise_pockets` buckets walls by axis and pairs within a bucket, so a
  triangular recess -- whose walls share no axis -- forms no candidate and reaches no gate:
  measured over 600 MFCAD++ models, **94% of triangular-pocket faces never reach a test**, which
  is why that family scored 0% on them and 4% on hexagonal ones.

  The record carries `sides` and the `section` polygon, as `Passage` does, because a triangular
  and a hexagonal pocket of equal depth are otherwise the same record. It is **not** a `Pocket`:
  folding it in would have made `Pocket.width` sometimes a wall-to-wall measurement and sometimes
  a bounding-box extent, changing what an existing field means for every consumer.

  **Neither family subsumes the other.** An obround recess has cylindrical ends and forms no
  closed planar ring, so `recognise_pockets` remains the only path to it -- measured at zero
  rings across the whole *Circular end pocket* class. Where both see the same rectangular recess
  both report it, and `_reconcile.prismatic_pockets_that_are_not_pockets` keeps the `Pocket`.

  Additive: **no existing recorded value changed**. Every golden gained the new family's output
  and nothing was removed or altered.

- **Fixed: a family that walks the graph accepted a ledger built from a different part.**
  `recognise_passages` resolved no face against its graph, so a mispaired one was never refused
  and it reported records describing the *other* solid. Now checked in the shared ring walk, so
  both ring-walking families are covered.

- **The chamfer/angled-step split moved from the recognisers to the reconciler.** Both families
  read the same oblique bevel, and until now each carried a gate phrased in terms of the *other*
  one: `recognise_chamfers` declined a bevel edge-adjacent to a triangular flat, and
  `recognise_angled_steps` required one, through a predicate they shared in
  `_adjacency`. That is an ownership decision, and ADR 0003 puts ownership after
  discovery. Both families now write a claim naming the one face they were established by — the
  bevel, and the slant — and `_reconcile.chamfers_that_are_not_angled_steps` drops a chamfer
  whose face a step already has.

  **Reconciled output is unchanged.** `build_recognition_result` and `feature_census` apply the
  rule and were verified byte-identical over all 72 corpus parts: 19 synthetic goldens, 40
  labelled MFCAD++ models, 10 NIST CTC models and 3 real turned parts.

  **What changes is `recognise_chamfers` called on its own**, which now reports a blind step's
  slant, as it did before `recognise_angled_steps` existed. Over the 40 MFCAD++ models that is 8
  extra records on 8 models — 8 of the 11 angled steps there; the other 3 are turned away as
  spanning wedges, which is the chamfer family's own gate. Every one of the 8 lands on a face
  the corpus labels *Triangular blind step*, and the rule takes back all 8. A caller who
  wants the reconciled answer should use the
  aggregate or the census, which is the same posture `recognise_passages` takes towards a slot's
  void and `recognise_turned_steps` towards a groove's rung. One pinned golden moved: the
  `recognise_chamfers` entry of `angled_blind_step` gained the ramp's slant.

  `recognise_chamfers` and `recognise_angled_steps` gain an optional `ledger=` parameter, in the
  shape `recognise_slots` and `recognise_grooves` already have. No record gains, loses or alters
  a field.

## 0.2.5

Adds a recogniser family, and with it corrects a defect that family's absence was causing.
`recognise_chamfers` was reporting the slanted walls of steps and passages as chamfers: measured
per face over 120 MFCAD++ models its precision was 44%, and on nine of the ten models carrying an
angled step, the step's slant was the **only** chamfer reported while the genuine chamfers on the
same part were rejected. Anyone consuming chamfer records on prismatic parts should take this.

The distinction between the two is deliberately **not** size. Every part-relative and
neighbour-relative ratio measured — leg against part extent, truncation of each neighbour, strip
aspect, area against neighbour — overlaps between the two populations, so any threshold would have
been fitted to one corpus. A chamfer runs the full length of the edge it breaks; an angled step
stops, and a triangular flat closes the blind end. That test is topological and mentions nothing
outside the feature, so it holds at any scale — `tests/test_scale_invariance.py` proves it across
0.05x-100x.

- **New family: `recognise_angled_steps` / `AngledStep`.** A wedge taken out of an edge — one
  oblique planar wall stopping part-way along it, closed by an axis-aligned triangular flat.
  100% precision and 70% instance recall over 120 MFCAD++ models. `length` is the field a
  `Chamfer` has no analogue for: a chamfer spans its whole edge, so its extent is not a chosen
  dimension. Ends whose triangle is subdivided into four or more edges by a neighbouring feature
  are not recognised, which accounts for about half the recall gap and is documented rather than
  worked around.
- **`recognise_chamfers` declines a bevel with a triangular blind end.** Precision 44% to 78% with
  every real chamfer kept. This is a recognition-behaviour change: a part with an angled step
  loses a chamfer record and gains an angled-step record. No pinned golden moved.
- **Chamfered grooves are read as one groove.** A conical lead-in between two cylindrical bands is
  matched by its rims rather than split into separate features (#60).
- **Countersink radii are read from the surface adaptor**, not `Face.radius`, correcting sizes on
  interrupted and cross-bored geometry (#74).
- **A census is about 14% faster.** `Face.edges()` is the suite's most expensive derived query and
  every recogniser was asking it of the same faces; one `FaceEdges` memo is now shared across a
  run. The new family costs roughly 11% of a census back, so the net gain is smaller than 14% —
  both figures are measured against their own baselines rather than combined into one.

`FaceEdges`, `AngledStep` and `recognise_angled_steps` are new public names.
Strict semver would make that a minor version; this project ships 0.2.x patches and says so here
instead. No existing record gains, loses or alters a field.


## 0.2.4

Corrects a regression in 0.2.3. Every pinned golden is byte-identical to the original Draftwright
capture again, and every count 0.2.3 changed on real parts is restored — verified against the NIST
MBE PMI complex test cases, not only the synthetic corpus. Anyone on 0.2.3 should take this.

Output is **not** identical to 0.2.2 in every case, and the exception is deliberate. On
`nist_ftc_09` the level recogniser reports fifteen levels where 0.2.2 reported sixteen, because
0.2.2 split a pair of faces **0.475 mm apart under a 0.5 mm tolerance** into separate levels — a
consequence of grouping by grid cell rather than by distance, fixed independently of the tolerance
work. Two faces closer together than the tolerance are one level. A 0.635 mm gap on the same part
is still correctly two.

- **Minimum-evidence thresholds are absolute again.** 0.2.3 scaled them to the part, which made a
  feature's existence depend on what surrounds it: the same 1 mm chamfer was recognised on an
  80 mm plate and absent on a 200 mm one. Six NIST MBE PMI parts lost records in nineteen places
  and gained in none. Affects the `chamfers` minimum leg, `fillets.min_radius`, `plates` slab
  thickness, `pads` footprint, `polygonal_bosses` height and `flats` minimum depth.
- **The recess merge band is absolute again.** Scaling it to the whole solid merged pockets and
  slots that a smaller plate kept distinct, and simultaneously raised the minimum separation of
  two slot ends — losing records in both directions at once.
- **`RiserEvidence.tol` reports `0.5` again**, so the goldens match the capture.
- [ADR 0008](docs/adr/0008-length-tolerance-policy.md) now distinguishes a **tolerance** ("are
  these two things the same?", which scales with what it compares) from a **minimum-evidence
  threshold** ("is this big enough to be a feature?", which must not). Whether a small feature on
  a large part is worth dimensioning is consumer policy under ADR 0001, and recognition should not
  answer it silently.
- Genuinely feature-relative tolerances from 0.2.3 are kept: diameter matching in `countersinks`,
  `grooves` and the cylinder stack, and the recess cap radii. Those compare two measurements of
  one feature and do scale with it.
- The `grooves` step-depth and width margins are absolute again. Found by auditing every
  remaining proportional gate rather than from a report: the NIST parts are prismatic and have no
  grooves, so nothing downstream would have surfaced it. A 2 mm groove was recognised on 15 mm bar
  and lost on 100 mm.
- The `flats` chord gates are absolute again too. They were missed on the first pass and caught
  by the real parts: `ctc_05` reported four flats on 0.2.2, none on 0.2.3, and two on the partial
  fix. Verified against all five NIST complex test cases, every reported count restored.
- `tests/test_large_part_small_features.py` pins the property with parts larger than the fixture
  corpus carrying features smaller than it implies — the combination the 30–180 mm fixtures never
  covered. `tests/test_nist_ctc_corpus.py` pins the reported baseline against the real parts, and
  skips unless `B123D_NIST_STEP_DIR` points at them, since `migration/PARITY.md` commits the
  project to comparing record projections rather than committing STEP bytes.

## 0.2.3

Recognition-behaviour release. Every gate that compares a length now scales with the geometry it
judges, so the same feature is recognised the same way whatever size it is modelled at. Records,
signatures and record schemas are unchanged; the capability manifest differs from 0.2.2 only by the
package version it embeds.

- **Length tolerances are proportional** ([ADR 0008](docs/adr/0008-length-tolerance-policy.md)).
  Every golden fixture now recognises identically from 0.05x to 100x, across every recogniser
  family; previously six of seventeen changed. Of the roughly 39 constants the review counted, 18
  were not lengths at all — ratios, direction cosines, angles, counts, epsilons — and three model a
  physical constant (an edge break does not grow with the shaft) and stay absolute, bounded so they
  cannot swallow a small feature.
- **`tol=` accepts `None`** on `recognise_plates`, `recognise_chamfers`,
  `recognise_rectangular_pads`, `recognise_polygonal_bosses`, `recognise_polygonal_stock`,
  `recognise_face_levels` and `recognise_risers`, as does `min_radius=` on `recognise_fillets` and
  `boundary_margin=` on `step_ladder_for_z_span`. `None` derives the value from the part. **An
  explicit float keeps its literal millimetre meaning**, so a caller who has calibrated against
  their own geometry is unaffected.
- **`RiserEvidence.tol` reports the tolerance its scan resolved** rather than a fixed `0.5`. This is
  the only record value that moves — 33 values across 5 fixtures, and no geometry field moves at
  all. The field keeps its default, so direct construction is unchanged. Recorded as the first
  intentional divergence from the Draftwright capture in `migration/PARITY.md`.
- **Coplanar faces group by distance, not by grid cell.** `round(coord / tol) * tol` merged faces
  0.24 mm apart while splitting faces 0.02 mm apart, and put a multiple of `tol` into `Plate.lo`
  and `.hi` — so a 3.7 mm slab reported a thickness of 3.5 mm. Both fixed.
- **An area gate no longer turns on a floating-point tie.** A face whose area sat exactly on the
  40% threshold was admitted or refused according to rounding, which made one fixture gain a plate
  at 5x and 10x and nowhere else.
- Proven across STEP export and re-import: all seventeen fixtures reproduce their pinned records
  exactly. Geometry arriving as B-splines remains an explicit whole-package exclusion; see
  [`docs/capabilities.md`](docs/capabilities.md).

## 0.2.2

- Decomposes the cylinder, hole/boss, pattern, and recess implementations along private,
  architecture-tested seams. Existing public imports, object identities, record module paths,
  deterministic ordering, shared-inventory behavior, capability declarations, and canonical
  semantic goldens are unchanged.

## 0.2.1

Compatibility-safe boundary and delivery-workflow patch release. Recognition output and canonical
semantic goldens are unchanged.

- Adds `RecognitionResult.step_ladder_for_z_span(z_min, z_max, *, boundary_margin=0.6)` as the
  build123d-free aggregate projection boundary. The margin is in model length units and its strict
  end behavior, validation, determinism, and JSON-safe output are tested. The old
  `step_ladder(BoundBox)` call is deprecated since 0.2.1 but remains throughout 0.2.x and will be
  removed no earlier than 1.0.0. Existing recognition semantics and goldens are unchanged.
- Adds a single-job Draftwright downstream canary for package pull requests and weekly consumer-
  drift checks. It records the resolved consumer commit, package commit/version, capability digest,
  and wall time while reusing the candidate-wheel contract harness rather than duplicating either
  repository's platform matrix. Package branches now launch that platform matrix only through the
  pull request instead of duplicating it for both branch-push and PR events, and superseded PR runs
  are cancelled. Recognition behavior and canonical goldens are unchanged.

## 0.2.0

Additive production-hardening release with no recognition-policy changes.

- Adds a deterministic, versioned capability manifest covering every public recogniser and
  record, with independent runtime/schema/evidence validation and installed-wheel parity.
- Exposes supported Python and command-line manifest queries so consumers can fail closed on
  unknown capability families without reading package internals.
- Makes the shipped `py.typed` contract enforceable, aligns public capability prose with proven
  behavior, and makes package rationale self-contained for standalone readers.
- Bounds complete hole-grid candidate work, strengthens branch-sensitive coverage to an enforced
  91.4% floor, and publishes Linux coverage through Codecov.

All canonical semantic goldens remain unchanged. Draftwright consumes this release through its
separately owned downstream capability declaration.

## 0.1.0

First stable release of the standalone Apache-2.0 recognition package.

- Promotes `0.1.0a1` after the packaged cutover merged in Draftwright PR #1168
  (`d659e7a6`), with the duplicate embedded recogniser implementation removed.
- Retains the 17 pinned semantic golden fixtures, public-inventory/serialization contracts, and
  cross-platform Python 3.10/3.12/3.14 matrix; this release contains no new recognition behaviour.
- Uses the reviewed TestPyPI-first Trusted Publishing path to promote one exact wheel and sdist
  to PyPI without rebuilding between indexes.

The complete migration, provenance, and performance evidence remains in
[`migration/PARITY.md`](migration/PARITY.md).

## 0.1.0a1

First prerelease of the standalone Apache-2.0 recognition package extracted from Draftwright.

- Includes every recogniser, shared geometry substrate, aggregate result, and feature census from
  Draftwright commit `3fe20b0f71a71deced06b310943dd44cc66e355e`.
- Matches all 17 pinned semantic golden fixtures and preserves the ADR 0002 public contract.
- Normalizes an exact dominant-axis numerical tie to the pinned result across Windows, macOS, and
  Linux; no feature-policy changes are included.
- Ships typed Python sources plus `LICENSE`, `NOTICE`, and `THIRD_PARTY_NOTICES.md`.

The complete migration and performance evidence is in [`migration/PARITY.md`](migration/PARITY.md).
