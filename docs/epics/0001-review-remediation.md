# Epic 0001 — Codebase review remediation

**Status:** proposed
**Owner:** @pzfreo
**Opened:** 2026-08-16
**Baseline:** `33c539b` (v0.2.2) — 252 tests, 92.31% branch coverage, ruff and mypy clean

A review of the package at 0.2.2 found the engineering discipline strong and the release machinery
well ahead of the version number. This epic tracks the seven things it found wrong, most severe
first.

| # | Finding | Severity | Behaviour change | Effort |
|---|---|---|---|---|
| 1 | No test imports a STEP file | High | no | M |
| 2 | Absolute mm tolerances, applied inconsistently | High | **yes** | M |
| 3 | Tests pin prose and implementation detail | Medium | no | S |
| 4 | Coverage thinnest where the geometry is hardest | Medium | no | M |
| 5 | Unnamed numeric literals ([#42](https://github.com/pzfreo/b123d-recognisers/issues/42)) | Medium | no | S |
| 6 | Long functions, partial return annotations | Low | no | M |
| 7 | Stray text in `census.py` docstring | Trivial | no | XS |

**One PR per finding**, except #2, which measurement split into three (see below). They are
otherwise independent and can land in any order. Only #2 changes recognition behaviour and needs a
minor release; everything else is a patch.

---

## 1 — No test imports a STEP file

`branch: agent/step-round-trip-goldens` · behaviour-neutral

Zero `.step`/`.stp` files in the repo and zero `import_step` calls in `tests/`. All 17 goldens are
clean build123d CSG solids. Imported STEP topology differs in ways the recognisers depend on: sewn
shells with split faces, seam edges, tolerant edges, and B-spline surfaces that are analytically
cylindrical but not typed as `Cylinder`. The README's opening claim — recovering features from
imported STEP — is currently *unproven, not disproven*.

- [x] Round-trip harness: export each fixture to STEP, re-import, run recognition
- [x] Assert the re-imported part yields the same canonical records as the constructed part
- [x] Fix what it exposes, or document the gap in `docs/capabilities.md` as an explicit exclusion
- [x] No STEP bytes committed — written to `tmp_path`, consistent with `migration/PARITY.md`

**Resolved. The result was not what the review predicted, in both directions.**

All seventeen fixtures round-trip through STEP with byte-identical canonical records. The review
expected drift from split faces, seam edges and tolerant edges; passing through a STEP file turns
out not to disturb analytic geometry at all. That half of the finding was overstated.

The underlying hazard is real but sits elsewhere. When the same solid reaches recognition with its
faces typed `GeomAbs_BSplineSurface` — geometrically identical, analytically untyped, which is what
a NURBS-only export delivers — **every recogniser returns zero**. Not degraded: a hole, a boss, a
plate and a chamfer all vanish together, because classification is by surface type throughout.

That is now an explicit whole-package exclusion in `docs/capabilities.md`, held by a test written
as a contrast against the analytic result so that adding support fails it. Supporting B-spline
faces means fitting analytic surfaces and bounding the residual — a recognition-behaviour change
with its own evidence requirements, not part of this epic.

## 2 — Absolute millimetre tolerances

**behaviour change** · target 0.3.0 · policy in
[ADR 0008](../adr/0008-length-tolerance-policy.md)

~39 length constants are fixed millimetres: `_MERGE_TOL = 0.5`, `_HOLE_DIA_TOL = 0.2`,
`_CHORD_MIN = 0.05`, `STEP_LADDER_BOUNDARY_MARGIN = 0.6`. A 2 mm micro-part and a 2 m weldment get
the same absolute gates, and a model authored in inches silently changes classification.

**The plan below was rewritten after measurement.** Two of its premises were wrong. The fixtures'
extents span 30–180 mm, so no reference scale reproduces today's behaviour everywhere and
"goldens byte-identical by construction" is unachievable. And classifying the sites individually
found **18 of the ~39 are not lengths at all** — ratios, unit-vector dot products, angles, counts,
epsilons — while `turned`'s absolute edge-break allowance is physically correct and must *not*
scale. This is per-site judgement, not one uniform pass. ADR 0008 records the classification of
every site.

### 2a — Policy and helpers · `agent/tolerance-policy-foundation` · behaviour-neutral

- [x] ADR 0008: one tolerance form `rel * nominal + floor`; nominal is the smallest geometry that
      determines the comparison; dimensionless gates and record rounding never scale; an absolute
      term is legal only when a comment names the physical constant it encodes
- [x] `_geometry.length_tol(nominal, *, rel, floor)` and `_geometry.part_scale(bbox)`
- [x] Every site classified in the ADR: 18 not lengths · 5 already scaled · 2 deliberately
      absolute · 17 feature-relative to convert · 13 part-relative to convert
- [x] `_pattern_tol` and the three inline `part_scale` spellings adopt the helpers — goldens
      byte-identical

### 2b — Feature-relative lengths · `agent/feature-relative-tolerances` · behaviour change

The 17 sites that already hold a diameter, radius or width at the comparison: `flats`,
`countersinks`, `grooves`, `_cylinder_substrate`, `_recess_core`'s cap tolerances.

- [x] Convert each to `length_tol(nominal, rel=…)` over a documented reference size
- [x] `tests/test_scale_invariance.py` rebuilds every fixture at 0.05×/5×/100× and asserts the
      converted families are invariant, with the unconverted ones named in an exclusion list 2c
      deletes from
- [x] **Goldens byte-identical.** No cell moved, so there was nothing to review under ADR 0002 —
      the conversion is a strict improvement off-scale and a no-op at reference scale
- [x] `turned._OD_SPAN_PAD` reclassified as deliberately absolute — converting it bridged a
      groove; see ADR 0008

### 2c — Part-relative lengths and the public surface · behaviour change · target 0.3.0

- [x] **[#46](https://github.com/pzfreo/b123d-recognisers/issues/46), landed first:** replaced
      the `round(coord / tol) * tol` grouping in `levels` and `plates` with bounded clustering
      by distance. Goldens byte-identical; `traversal_order` became scale-invariant
- [x] **Broke the exact tie in the area gates.** `chamfers_fillets_and_flats` has a face whose
      area is *exactly* `min_area_frac` of the cross-section, so `a >= thresh` was decided by
      rounding: `-1.7e-13` at 1x, exactly `0.0` at 5x and 10x, `-9.3e-10` at 100x. Grid phase
      was not the cause. `_geometry.clears_threshold` resolves it the same way at every scale
- [x] `tol: float | None = None` on `recognise_plates`, `recognise_chamfers`,
      `recognise_rectangular_pads`, `recognise_polygonal_bosses`, `recognise_polygonal_stock`,
      `recognise_face_levels`, `recognise_risers`, and `min_radius` on `recognise_fillets`.
      `None` resolves to `rel * part_scale`; an explicit float keeps its literal meaning
- [x] `RiserEvidence.tol` reports the resolved value and loses its default — 33 golden values
      across 5 fixtures move, **and no geometry field moves at all**. Recorded as the first
      intentional divergence in `migration/PARITY.md`
- [x] Capability manifest regenerated: one line, `RiserEvidence.tol` now required. The manifest
      records record schemas, not signatures — the earlier claim that defaults were in it was
      wrong
- [x] `STEP_LADDER_BOUNDARY_MARGIN` reclassified as deliberately absolute and capped at a
      quarter of the span; ADR 0006 amended. Deriving it broke that ADR's own regression
- [x] `NOT_YET_SCALE_FREE` reduced from four kinds to one
- [x] **`_recess_core`'s `_MERGE_TOL`, `_FLOOR_TOL` and corner-notch `tol`** — the split the
      epic reserved. A `scale` threaded through the eight helpers that never receive the part;
      the five that hold a part or `part_ext` derive it themselves. Goldens byte-identical
- [x] **`NOT_YET_SCALE_FREE` is empty.** Every fixture recognises identically from 0.05x to
      100x, across every family
- [ ] Release note; `0.3.0a1` for the Draftwright canary, then `0.3.0` — **requires explicit
      approval, publishing is outside the loop's remit**

## 3 — Tests that pin prose and implementation detail

`branch: agent/loosen-brittle-assertions` · behaviour-neutral

`test_architecture.py` asserts the exact internal module import-graph edge set and literal
`__annotations__` strings such as `"tuple[float, ...] | None"`. `test_published_prose.py` asserts
README wording — `"STEP editor" in readme`. These fail on harmless refactors and copy edits. PR #40
shows the cost: four follow-up commits to restore facade globals, annotations and module identities
that only those tests observed.

- [x] Dropped the literal `__annotations__` string assertions; the `get_type_hints()`
      resolution check is what remains, extended to `recognise_slots`
- [x] Replaced the README phrase matching with two checks that hold the property the wording
      stood in for: every name a README example imports is really exported, and the example
      still demonstrates `import_step` feeding a recogniser. The old assertions failed on copy
      edits while passing on a README documenting a function that no longer existed
- [x] **Kept** `test_module_graph_is_acyclic`, `test_runtime_package_does_not_import_draftwright`,
      `test_no_accidental_public_modules` and the export-identity checks
- [x] `MODULE_SEAM_EDGES` relaxed from exact equality to "no edge outside the allowed set"
- [x] **Closed a hole found while verifying that relaxation.** `from b123d_recognisers import
      chamfers` was invisible to `_package_import_graph`, which reads only `node.module` — so a
      seam or cycle violation written that way passed every check in the file. Both forms are
      now read
- [x] Coverage floor rounded to `91`

## 4 — Coverage concentration

`branch: agent/geometry-coverage` · behaviour-neutral

Packaging and manifest scaffolding sits at 96–100% while the geometry it exists to protect is
lower. The 92.31% aggregate is partly carried by the easy modules.

- [x] `_geometry.py` 73.4% → **100%**. The dominant-axis tie-break is the one deliberate
      normalization in `migration/PARITY.md` and had no test of its own; it now has the tie
      cases, the band edge, and every rejection path
- [x] `grooves.py` 83.8% → **97.4%**, entirely from the excluded classes
- [ ] `polygonal_bosses.py` 85.4%, `repeating_profiles.py` 87.6% — same treatment, next PR
- [x] Prefer negative and boundary cases over happy-path additions — every test added is a
      shape that must return no record
- [ ] Raise the floor only after, not before

## 5 — Unnamed numeric literals

`branch: agent/name-numeric-literals` · behaviour-neutral ·
[#42](https://github.com/pzfreo/b123d-recognisers/issues/42)

The ~150 literals that are **not** lengths: unit-vector direction gates, ratios, angles, counts,
epsilons. Scaling any of these would be a defect, which is why they are separate from #2.

- [ ] Hoist the `0.99` / `0.05` / `0.02` / `0.01` direction gates in `chamfers`, `fillets`,
      `plates`, `pads`, `levels`, `polygonal_bosses`, `_hole_features` to named constants
- [ ] Name the `0.05` interior-probe fraction shared by `chamfers` and `fillets`
- [ ] Rename `_BC_SPACING_TOL` → `_BC_SPACING_FRAC` — it reads absolute but is already applied
      relatively (`> _BC_SPACING_TOL * even`), which is exactly the confusion worth removing
- [ ] Document the convention: `*_TOL`/`*_MARGIN` = length · `*_FRAC`/`*_RATIO` = dimensionless ·
      `*_ANGLE` = angle · `*_EPS` = machine epsilon
- [ ] Leave `round(x, 4)` and every other serialisation rounding alone — that is the public record
      contract and the capability schema

## 6 — Long functions and partial typing

`branch: agent/decompose-long-recognisers` · behaviour-neutral

PR #40 split modules along tested seams but left the functions intact.
`polygonal_bosses._recognise_one` is 227 lines, `levels.recognise_risers` 129,
`_hole_features.recognise_holes` 119; 22 functions exceed 60 lines. Roughly 38% of definitions carry
no return annotation, and mypy runs without `disallow_untyped_defs` — for a package that ships
`py.typed`, the internal geometry helpers are the least typed part.

- [ ] Decompose the three worst offenders only; leave the rest unless #4 makes a case
- [ ] Annotate the internal geometry helpers, then enable `disallow_untyped_defs`
- [ ] Goldens byte-identical throughout — this is the PR most likely to move behaviour by accident

## 7 — Stray docstring text

Folded into 2a.

- [x] `census.py` line 10: a sentence begins "Progress" and runs into the next line

---

## Not in this epic

- **Process weight.** Seven ADRs, a delivery protocol, a capability manifest, a downstream canary
  and a five-stage landing protocol for a 7k-line alpha with one consumer. This is an observation,
  not a defect — but it is the reason to resist adding more governance surface while working
  through the list above. Each one has to be kept true.
- New recogniser families.
