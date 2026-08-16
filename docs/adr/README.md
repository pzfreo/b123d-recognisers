# Architecture decision records

These records extract the recognition-specific decisions from Draftwright without importing
its drawing/compiler policy. Accepted records describe contracts already proven in Draftwright;
proposed records describe the next recognition architecture and require evidence before
acceptance.

| ADR | Title | Status |
| --- | --- | --- |
| [0001](0001-standalone-geometry-only-apache-library.md) | Standalone geometry-only Apache library | Accepted |
| [0002](0002-uniform-deterministic-recogniser-contract.md) | Uniform deterministic recogniser contract | Accepted |
| [0003](0003-one-recognition-result-and-explicit-reconciliation.md) | One recognition result and explicit reconciliation | Proposed |
| [0004](0004-attributed-geometry-graph-and-residual-evidence.md) | Attributed geometry graph and residual evidence | Proposed |
| [0005](0005-versioned-cross-repository-capability-contract.md) | Versioned cross-repository capability contract | Accepted |
| [0006](0006-explicit-step-ladder-z-span.md) | Explicit step-ladder Z-span boundary | Accepted |
| [0007](0007-recogniser-module-seams.md) | Internal recogniser module seams | Accepted |
| [0008](0008-length-tolerance-policy.md) | Length tolerance policy | Accepted |

Draftwright ADRs 0007, 0013, 0015 and 0017 are historical inputs, not normative records for this
project. Consumer-specific requirements, annotation provenance, lint and placement remain owned
by Draftwright.
