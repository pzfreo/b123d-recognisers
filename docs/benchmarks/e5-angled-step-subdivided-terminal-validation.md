# E5 AngledStep subdivided-terminal validation

- **Issue:** #111
- **Parent main:** `fa02e777f99cad0e7f59ad8d1dae4e403e52fe1b`
- **Implementation source:** `2fb50c3c3d3086733f32f3499e2f888fe0845d1b`
- **Dataset:** published MFCAD++ test split, canonical lexical first 500 unique model IDs
- **Selection SHA-256:** `323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`
- **Taxonomy:** v8, SHA-256 `ef8ec7e88b0f72acdce5f7c11470af9b62c0aee5e550c0d1208fe33ecb69eb0f`
- **Recognition frame:** raw

## Geometry decision

An AngledStep blind end is geometrically triangular when its axis-aligned planar outer boundary
has exactly three cyclic straight runs. A topological split may turn one straight side into several
consecutive co-directed linear edges without changing that fact. Discovery collapses only those
directions under the existing dimensionless smooth-direction tolerance; it does not relax a raw
edge-count threshold. Rectangular caps retain four runs, a kink outside the tolerance retains four,
and curved, degenerate or unreadable boundaries fail closed.

The authored fixture constructs a valid closed solid with the terminal/slant shared boundary split
in two. It now yields one AngledStep with the exact slant as defining evidence and the exact terminal
face as constituent evidence; the aggregate's existing named reconciliation removes the overlapping
Chamfer and emits no residual diagnostic. Translation preserves raw coordinates and physical values.
Straight-run direction controls cover both sides of the tolerance boundary, a true rectangle, a
reversed boundary, curved/unreadable failure, and the existing through-Chamfer, pocket, gusset,
scale, principal-axis, STEP and topology-order controls.

Independently authored MFCAD++ test model `11512` is vendored byte-for-byte under CC BY with source
SHA-256 `5dc3ff1ba7307846c534650ac0c0c2ae1442cd51f29fb0a028a63a1ecd041e67`.
Its class-20 terminal has five raw outer edges but three straight runs. Under translated X/Y/Z
principal-axis presentations, direct recognition and the raw aggregate each retain one occurrence
with invariant `leg1=6.121`, `leg2=2.685`, `angle=23.68`, and `length=13.534`; no surviving Chamfer
shares its slant anchor.

## MFCAD++ development evidence

The implementation report is
[`effectiveness-mfcadpp-500-angled-terminal-2fb50c3.json`](effectiveness-mfcadpp-500-angled-terminal-2fb50c3.json),
compared with immediate-main
[`effectiveness-mfcadpp-500-turned-translation-7d8fb1a.json`](effectiveness-mfcadpp-500-turned-translation-7d8fb1a.json).
All 500 models loaded and evaluated. After removing runtime, source commit and per-model seconds,
exact recursive comparison finds changes only in model `11512` and their aggregate summary:

- physical AngledSteps: 140 → 141; Chamfers: 87 → 86;
- class-20 mapped records and matched defining faces: 136 → 137;
- class-20 defining precision: 136/140 (97.14%) → 137/141 (97.16%);
- class-20 defining recall: 136/411 (33.09%) → 137/411 (33.33%);
- class-0 precision denominator: 95 → 94, with its 69 matched faces unchanged;
- named Chamfer-superseded-by-AngledStep drops: 92 → 93;
- taxonomy mismatch defining faces: 3,195 → 3,194; and
- the one failed-terminal observation and unsupported diagnostic disappear.

No other model or summary field changes. The implementation report SHA-256 is
`3d3c45f0a94b07d496639cc402de09d24c245fe28e2e70898d365b21fdb2a6ee`.

Standalone runtime remains inside ordinary run variance for this one-model semantic change:

| Metric | Parent | Implementation | Ratio |
| --- | ---: | ---: | ---: |
| total | 336.320 s | 350.497 s | 1.0422x |
| median/model | 0.6317 s | 0.6565 s | 1.0393x |
| p95/model | 1.2050 s | 1.2373 s | 1.0269x |

## Validation and architecture review

- Full fast tier: 2,563 passed.
- Focused AngledStep, diagnostics, explanations, bevel claims and vendored MFCAD++ suite: 69 passed.
- The final full Ruff and mypy checks are recorded after the evidence commit.
- ADR 0002 keeps equivalent geometry deterministic; the proof depends only on cyclic unit directions.
  ADR 0003 retains independent proposals and unchanged named reconciliation. ADR 0004 is amended to
  supersede its diagnostic-only boundary for this exact three-run fact. ADR 0007 keeps the query
  local to AngledStep discovery. ADR 0008 classifies the reused unit-direction comparison as
  dimensionless and introduces no new tolerance. ADR 0009 keeps terminal filtering inside its owning
  recogniser. ADR 0011's raw/framed coordinate meanings are unchanged.

