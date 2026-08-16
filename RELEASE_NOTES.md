# Release notes

## 0.2.4

Corrects a regression in 0.2.3. Recognition output returns to `0.2.2` behaviour at every scale the
golden corpus covers, and every pinned golden is byte-identical to the original Draftwright capture
again. Anyone on 0.2.3 should take this.

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
- `tests/test_large_part_small_features.py` pins the property with parts larger than the fixture
  corpus carrying features smaller than it implies — the combination the 30–180 mm fixtures never
  covered.

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
