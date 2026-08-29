# Circular blind-step anatomy audit — MFCAD++-500

**Baseline:** `b17ae81`  
**Dataset:** published MFCAD++ test split, DOI
`10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823`  
**Selection:** lexically first 500 STEP files; selected-ID SHA-256
`323c956889bf6018f37d8411367c6b30b95ffac8011b13a69f06e189568401df`  
**Mapping:** MFCAD++ class 21, `circular_blind_step`  
**Artifact:**
[`circular-blind-step-audit-mfcadpp-500-b17ae81.json`](circular-blind-step-audit-mfcadpp-500-b17ae81.json)

## Decision

Proceed with one bounded circular blind-step family. The proposed geometry contract produces 118
occurrences over all 500 models, and every occurrence's two defining faces carry class 21:
236/236 defining-face precision. It recalls 117 of 173 labelled component proxies (67.63%). The
component denominator is a non-native connected-component proxy, not MFCAD++ instance truth; one
component contains two valid occurrences, hence 118 occurrences and 117 recalled components.

This is not a label-shaped size rule. Labels select and score the audit rows only. Candidate
geometry is determined from the final B-rep:

1. one inward-facing native or certified cylindrical patch spans exactly a quarter turn;
2. its axis is principal and one principal planar terminal is perpendicular to that axis;
3. cylinder and terminal meet concavely at the interior blind end;
4. the cylinder's opposite axial end reaches one envelope end of the same valid source solid;
5. exactly two other principal planes meet its generator sides convexly, on the two axes
   perpendicular to the run, while one convex axial face closes the open envelope end;
6. sweeping the terminal's exact sector face to that envelope has zero volumetric intersection
   with the source solid.

The contract distinguishes a circular blind step from a full blind bore (not a quarter patch), a
through corner groove (no interior terminal), a fillet (no concave perpendicular blind terminal),
an external round/boss (wrong material side), and an enclosed cylindrical pocket (not open to an
axial envelope). It introduces no size cutoff, and the material decision requires exactly zero
volume. Coordinate comparisons reuse ADR 0008's named `COORD_FLOOR`. Cylindrical parameter-space
comparison uses a separate `_QUARTER_TURN_RAD_TOL = 1e-7` radians: this admits only OCCT parameter
noise around an exact quarter turn and displaces a unit-radius boundary by less than 0.1
micrometre. Authored boundary tests pin acceptance at half that allowance and refusal at twice it.

## Canonical counts

| Measure | Result |
| --- | ---: |
| Models selected / loaded / evaluated | 500 / 500 / 500 |
| Invalid or face-count-mismatched models | 0 |
| Class-21 labelled faces | 354 |
| Non-native component proxies | 173 |
| Projected occurrences | 118 |
| Projected class-21 occurrences | 118/118 (100%) |
| Projected defining faces | 236 |
| Projected class-21 defining faces | 236/236 (100%) |
| Recalled component proxies | 117/173 (67.63%) |

The first-failed geometry gates account for all 173 proxies: 117 recognisable, 31 with an
incomplete convex sector boundary, 17 not running from an interior terminal to a solid envelope,
seven without a cylinder/terminal pair, and one non-quarter cylinder. No labelled component that
reached the final exact swept-sector test contained material.

## Existing-family conflicts

The projected defining nodes overlap 114 accepted `Fillet` candidates and three accepted `Plate`
candidates in the current aggregate inventory. This is useful downstream movement, not a reason to
avoid the family:

- a quarter-cylinder edge cut is presently understandable to the fillet family as a cylindrical
  round because no more specific physical family claims it;
- the new family must claim both its cylindrical wall and planar terminal, then reconciliation
  must prefer it over a fillet sharing that cylindrical wall;
- plate overlap on a terminal face is compatible unless a complete-claim containment rule proves
  otherwise. A plate is stock context and is absent from the feature census; it must not be
  silently deleted merely because one feature terminates on it.

The implementation child must report both raw family recall and the contested-face change. A
reconciler may remove the 114 duplicate fillet interpretations only where the circular-step
candidate itself survives; ADR 0003 forbids using reconciliation to repair discovery misses.

## Reproduction and provenance

```bash
uv run python tools/audit_mfcadpp_circular_blind_steps.py \
  /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --limit 500 \
  --output docs/benchmarks/circular-blind-step-audit-mfcadpp-500-b17ae81.json
```

The tool fails closed on an absent/empty root, invalid imported geometry, and imported-face/label
count disagreement. Authored tests pin the positive quarter-cylinder, rotation behavior, node-order
independence, blind-hole refusal, and through-cut refusal.

MFCAD++ is Epic #290's open development corpus. Model `10000` was inspected to confirm what the
class name meant geometrically; no MFInstSeg model was inspected. The intended MFInstSeg root
`/app/workspaces-codex/datasets/mfinstseg` was absent during this audit, so #293 remains the transfer
baseline gate.
