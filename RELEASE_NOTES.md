# Release notes

## 0.1.0a1

First prerelease of the standalone Apache-2.0 recognition package extracted from Draftwright.

- Includes every recogniser, shared geometry substrate, aggregate result, and feature census from
  Draftwright commit `3fe20b0f71a71deced06b310943dd44cc66e355e`.
- Matches all 17 pinned semantic golden fixtures and preserves the ADR 0002 public contract.
- Normalizes an exact dominant-axis numerical tie to the pinned result across Windows, macOS, and
  Linux; no feature-policy changes are included.
- Ships typed Python sources plus `LICENSE`, `NOTICE`, and `THIRD_PARTY_NOTICES.md`.

The complete migration and performance evidence is in [`migration/PARITY.md`](migration/PARITY.md).
