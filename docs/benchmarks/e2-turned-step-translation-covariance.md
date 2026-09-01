# E2 turned-step translation-covariance validation

- **Issue:** #389
- **Parent main:** `600268cb7e1c502faca5166279b17bd849540458`
- **Implementation source:** `7d8fb1a2184923669d5944555948da16945a5e67`
- **Dataset:** published MFCAD++ test split, canonical lexical first 500 unique model IDs
- **Selection SHA-256:** `323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`
- **Taxonomy:** v8, SHA-256 `ef8ec7e88b0f72acdce5f7c11470af9b62c0aee5e550c0d1208fe33ecb69eb0f`
- **Recognition frame:** raw

## Geometry decision

A turned shoulder face is eligible from its radial reach around the recognised profile axis line,
not its distance from the world origin. `TurnedProfileKey.axis_origin` is already derived from the
same body-local cylindrical bands used to establish the profile. The shoulder filter now subtracts
that transverse origin before comparing the face bounds with the local outside radius.

The exact reported blind-bore reproduction retains two physical steps after translation instead of
splitting the smaller band at the internal bore floor. Authored regressions exercise X, Y and Z
profiles under an arbitrary translation and prove parity between direct discovery and the raw
aggregate's caller-coordinate result. Existing controls retain plural off-centre profile grouping,
framed rigid-motion inventory, body ownership, STEP round trips, chamfered shoulders, through bores,
and deterministic aggregate attribution.

This is a coordinate-covariance correction, not a new heuristic. It changes no tolerance, public
record/schema, profile grouping, framing policy, defining evidence, or reconciliation rule.

## MFCAD++ development evidence

The implementation report is
[`effectiveness-mfcadpp-500-turned-translation-7d8fb1a.json`](effectiveness-mfcadpp-500-turned-translation-7d8fb1a.json),
compared with the immediate-main
[`effectiveness-mfcadpp-500-countersink-f53392f.json`](effectiveness-mfcadpp-500-countersink-f53392f.json).
All 500 models loaded and evaluated. After removing `.runtime`, `.package.commit`, and every
`.models[].seconds`, the reports are byte-identical with normalized SHA-256
`b479e01576489e823d9de42709f643941d02637873039006696d30e1b515d663`.
The implementation report SHA-256 is
`cec6bd34111b68ca3b63a43072e020229ea992b0c764214f326992bcdfd22557`.

Standalone runtime did not regress:

| Metric | Parent | Implementation | Ratio |
| --- | ---: | ---: | ---: |
| total | 344.023 s | 336.320 s | 0.9776x |
| median/model | 0.6381 s | 0.6317 s | 0.9899x |
| p95/model | 1.2208 s | 1.2050 s | 0.9871x |

## Validation and architecture review

- Full fast tier: 2,557 passed.
- Focused turned-step and profile-locality suite: 26 passed.
- Ruff and mypy are clean for the changed source.
- ADR 0002 requires deterministic equivalent-geometry results and directly supports measuring from
  the recognised axis line. ADR 0007 keeps the correction inside turned-step discovery. ADR 0008
  requires no amendment because no numeric gate changes. ADR 0011 keeps raw coordinates in caller
  space and framed coordinates paired with the one working shape; neither boundary changes.
- The final diff changes only the radial reference and its covariance regression. No ADR amendment
  is required.
- One bounded independent review found no geometry, contract, test, evidence, or ADR defect and no
  bounded follow-up. A second review was not warranted for this narrow coordinate correction.
