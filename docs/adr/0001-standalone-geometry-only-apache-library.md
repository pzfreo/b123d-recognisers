# ADR 0001 — Standalone geometry-only Apache library

- **Status:** Accepted
- **Date:** 2026-08-15
- **Decider:** Paul Fremantle

## Context

Draftwright and build123d-mcp both need to recover feature measurements from imported or otherwise
unattributed B-rep solids. Draftwright previously owned recognition to avoid coupling recognition
changes to its rendering dependency, but recognition itself is not drawing-specific. Keeping a
copy in each consumer causes algorithm and bug-fix drift.

Draftwright's ADRs 0007 and 0013 already selected a standalone package named
`b123d-recognisers`; the earlier deployment gate was organizational rather than architectural.
The copyright owner has now chosen to establish that package.

## Decision

Create distribution `b123d-recognisers`, imported as `b123d_recognisers`, under Apache-2.0.

The library accepts build123d shapes, using OCP internally where necessary, and returns geometric
records, measurables, evidence and recognition diagnostics. It does not own:

- drawing requirements, dimensions, callouts, views, placement or lint severity;
- editing-session state, reconstruction commands or CAM operation selection;
- consumer caches tied to a drawing, document or server lifecycle.

Consumers adapt records into their own domain IR. The dependency direction is always
`consumer → b123d-recognisers → build123d/OCP`.

## Consequences

- Recognition algorithms can be reused by Apache, proprietary and copyleft consumers.
- Cross-repository releases become necessary, so the public surface must remain small and stable.
- Draftwright's `RecognitionCache` stays in Draftwright because it implements build/lint lifecycle
  policy; only immutable recognition values cross the boundary.
- Existing recognition code is deliberately relicensed during migration by its copyright owner.

