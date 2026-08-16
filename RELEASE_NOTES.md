# Release notes

## Unreleased

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
