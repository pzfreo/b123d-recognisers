# Release notes

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
