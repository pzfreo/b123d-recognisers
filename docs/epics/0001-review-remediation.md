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

**One PR per finding.** They are independent and can land in any order, with one exception noted
in #2. Only #2 changes recognition behaviour and needs a minor release; everything else is a patch.

---

## 1 — No test imports a STEP file

`branch: agent/step-round-trip-goldens` · behaviour-neutral

Zero `.step`/`.stp` files in the repo and zero `import_step` calls in `tests/`. All 17 goldens are
clean build123d CSG solids. Imported STEP topology differs in ways the recognisers depend on: sewn
shells with split faces, seam edges, tolerant edges, and B-spline surfaces that are analytically
cylindrical but not typed as `Cylinder`. The README's opening claim — recovering features from
imported STEP — is currently *unproven, not disproven*.

- [ ] Round-trip harness: export each fixture to STEP, re-import, run recognition
- [ ] Assert the re-imported part yields the same canonical records as the constructed part
- [ ] Land the harness first with whatever subset passes, and record the failures as normal test
      expectations — do not `xfail`
- [ ] Fix what it exposes, or document the gap in `docs/capabilities.md` as an explicit exclusion
- [ ] Keep the STEP files out of the wheel (`sdist` include list already scopes this)

**Highest value per hour in the epic.** It tests the sentence at the top of the README.

## 2 — Absolute millimetre tolerances

`branch: agent/scale-tolerances` · **behaviour change** · target 0.3.0

~39 length constants are fixed millimetres: `_MERGE_TOL = 0.5`, `_HOLE_DIA_TOL = 0.2`,
`_CHORD_MIN = 0.05`, `STEP_LADDER_BOUNDARY_MARGIN = 0.6`. A 2 mm micro-part and a 2 m weldment get
the same absolute gates, and a model authored in inches silently changes classification.
`profiled_bores` and `repeating_profiles` already derive `max(tol, part_scale * 1e-5)`, and
`_pattern_geometry._pattern_tol(nominal) = rel * nominal + floor` is the exact form to generalise —
this is adopting an idiom the codebase already has, in one uniform pass.

- [ ] `_geometry.length_tol(nominal, *, rel, floor)` and one `part_scale(part)` (currently spelled
      three different ways)
- [ ] Apply to all ~39 length constants. **Calibrate so that at the fixtures' envelope the
      effective tolerance equals today's value** — goldens then stay byte-identical at reference
      scale by construction, and only off-scale behaviour moves
- [ ] Scale-invariance test: rebuild each fixture at 0.1×/1×/10×/100×, assert proportional records
- [ ] `tol: float | None = None` on the five public recognisers that expose the keyword; `None`
      resolves to the derived value. Regenerate the capability manifest — these signatures are in it
- [ ] ADR 0008 recording the policy: lengths scale; unit-vector gates, angles, counts and record
      rounding never do
- [ ] Release note stating the behaviour change and the reference-scale guarantee
- [ ] `0.3.0a1` prerelease for the Draftwright canary, then `0.3.0`

**Do #1 first.** If STEP re-import perturbs geometry, the tolerances have to absorb that noise, and
that changes the calibration. Sequencing these the other way risks calibrating twice.

**Split only if it fails.** If the goldens move at 1×, split `_recess_core` into its own PR — it is
987 lines and its tolerances interact (merge feeds collapse feeds obround extension). Do not
pre-split on suspicion.

## 3 — Tests that pin prose and implementation detail

`branch: agent/loosen-brittle-assertions` · behaviour-neutral

`test_architecture.py` asserts the exact internal module import-graph edge set and literal
`__annotations__` strings such as `"tuple[float, ...] | None"`. `test_published_prose.py` asserts
README wording — `"STEP editor" in readme`. These fail on harmless refactors and copy edits. PR #40
shows the cost: four follow-up commits to restore facade globals, annotations and module identities
that only those tests observed.

- [ ] Drop the literal `__annotations__` string assertions; keep the `get_type_hints()` resolution
      check, which tests the property that actually matters
- [ ] Drop the README phrase matching in `test_published_prose.py`
- [ ] **Keep** `test_module_graph_is_acyclic`, `test_runtime_package_does_not_import_draftwright`,
      `test_no_accidental_public_modules` and the export-identity checks — those encode real
      invariants
- [ ] Relax `MODULE_SEAM_EDGES` from exact equality to "no edge outside the allowed set", so adding
      a permitted import is not a test change
- [ ] Round the coverage floor to `91` — two decimal places is the same instinct in miniature

## 4 — Coverage concentration

`branch: agent/geometry-coverage` · behaviour-neutral

Packaging and manifest scaffolding sits at 96–100% while the geometry it exists to protect is
lower. The 92.31% aggregate is partly carried by the easy modules.

- [ ] `_geometry.py` 73.4% — the axis/tie-break code, which is the one piece with a documented
      cross-platform hazard, is the least covered file in the package
- [ ] `grooves.py` 83.8%, `polygonal_bosses.py` 85.2%, `repeating_profiles.py` 87.6%
- [ ] Prefer negative and boundary cases over happy-path additions — the excluded classes in
      `docs/capabilities.md` are a ready-made list of what should return no record
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

Fold into whichever PR lands first.

- [ ] `census.py` line 10: a sentence begins "Progress" and runs into the next line

---

## Not in this epic

- **Process weight.** Seven ADRs, a delivery protocol, a capability manifest, a downstream canary
  and a five-stage landing protocol for a 7k-line alpha with one consumer. This is an observation,
  not a defect — but it is the reason to resist adding more governance surface while working
  through the list above. Each one has to be kept true.
- New recogniser families.
