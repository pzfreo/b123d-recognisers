# 0.2.6 release readiness

This is the post-consolidation release-candidate record. The recognition candidate is merge
commit `a23cd1301ade333fb5689a49e29bd23ea9ea718f` (PR #137), on top of merged PR #136. The final
documentation/artifact commit may be newer, but must not change recognition code without rerunning
the semantic and performance gates below.

## Decision

**Go for a release candidate; do not publish until the artifact gate below has been repeated on
the final documentation commit and the protected PyPI environment has been confirmed.**

Issues #110, #112, #119, #127 and #135 are resolved. Issue #111 remains a documented,
non-blocking limitation: an angled-step blind-end triangle whose outer side is subdivided by a
neighbouring feature can still be missed, and the result model has no first-class
contested/uncertain outcome.

## Semantic and quality gate

- Full suite: 761 passed in 625.53 seconds, 96.11% measured coverage.
- Ruff and mypy: pass (42 source files).
- Semantic goldens and STEP round trips: unchanged except for the explicitly reviewed 0.2.6
  additions already pinned in the golden set.
- NIST real-part count baselines: unchanged.
- MFCAD++ design set: all 40 models scanned, none skipped, and no accepted claim lands on Stock.
- Supported CI matrix: Linux, macOS and Windows on Python 3.10, 3.12 and 3.14 all pass.
- Draftwright candidate-wheel canary: pass.

## #112 and #119 decision

The release does not introduce a minimum slot-size threshold. The three suspicious 0.08, 0.19
and 0.31 mm records were not small valid slots; they were wall pairs assembled across different
recess boundaries. Discovery now rejects contradictory AAG turns and uses smooth-arc connectivity
as the gAAG-equivalent view when STEP subdivides one boundary. Aggregate reconciliation then gives
complete pocket and passage rings precedence over fragments they contain.

On the 40-model design set, 35 proposed slots become 19 accepted slots. The former 32
cross-family recess overlaps collapse to two one-face partial overlaps (Pocket/Slot and
Pocket/Passage). Both survive deliberately because neither claim contains the other.

## Performance gate

Measured on the shared development host using the executable checked-in budget:

| Workload | Samples | Minimum | Ceiling | Peak RSS | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| composite | 5 | 2.068 s | 2.698 s | 450,792 KiB | pass |
| census | 3 | 103.355 s | 109.651 s | 473,136 KiB | pass |

The census samples were 103.355, 104.194 and 108.106 seconds. The composite samples were 2.105,
2.119, 2.068, 2.264 and 2.513 seconds. These are regression checks on this host, not portable
performance promises.

## Public contract

Relative to 0.2.5, the top-level inventory adds four names and removes none:

- `Passage`
- `PrismaticPocket`
- `recognise_passages`
- `recognise_prismatic_pockets`

The supported Python range remains `>=3.10,<3.15`; CI exercises 3.10, 3.12 and 3.14. The build123d
dependency remains `>=0.9,<0.12`. The four embedded version locations remain
`0.2.6.dev0`; the release workflow strips `.dev0` on the tagged commit and builds 0.2.6.

- Capability-manifest SHA-256: `b4bdf4e80a1e83e330804bec55f4e96870d19089b134119311b56a1db342527a`
- Canonical 20-golden-set SHA-256: `0ef8bb2dc164233a11575c69accf979a2dac2248a49d5f9d3b330db9240729e4`

Both digests are unchanged from the pre-consolidation release baseline: the public additions and
their pinned goldens were already present at that baseline, while the later consolidation and
reconciliation work changed accepted aggregate behavior only on the labelled corpus cases outside
the canonical golden set.

## Final artifact gate

- [x] Verify all four embedded versions and generated capability-manifest parity.
- [x] Record the final capability-manifest and canonical-golden SHA-256 digests.
- [ ] Build wheel and sdist through the same dev-suffix stripping step as `publish.yml`.
- [ ] Inspect artifact contents and record exact sizes and SHA-256 hashes.
- [ ] Install the wheel into a clean Python 3.10 environment and exercise public import,
      aggregate recognition, census, capability manifest and capability CLI.
- [ ] Run the bounded Draftwright candidate-wheel checker against the final wheel source.
- [ ] Confirm the final main CI/downstream checks are green.
- [ ] Confirm the GitHub release tag will be exactly `v0.2.6`, attach no hand-built artifacts,
      and require approval in the protected `pypi` environment.
