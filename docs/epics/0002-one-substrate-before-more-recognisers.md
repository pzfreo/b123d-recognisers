# Epic 0002 — One substrate before more recognisers

**Status:** proposed
**Owner:** @pzfreo
**Opened:** 2026-08-19
**Baseline:** `c638120` (0.2.6.dev0) — 657 tests, 95.65% branch coverage, ruff and mypy clean

MFCAD++ carries 25 labelled classes and this package recognises roughly half of them. The
temptation is to work through the other half. This epic argues for consolidating what is already
here first — not because the substrate blocks the missing classes (it does not; see item 5) but
because every concept currently implemented several times privately will be implemented once more
by each recogniser added on top of it.

The evidence for that is [#92](https://github.com/pzfreo/b123d-recognisers/issues/92)'s: the
concepts do not stay uncopied. They get rebuilt locally, and the copies drift where nobody is
looking.

| # | Item | Value | Behaviour change | Effort |
|---|---|---|---|---|
| 0 | Per-face recall, measured rather than fitted | Sizes 1–5 | no | **done for four families** |
| 5 | Oblique recesses: migrate, not a scope decision | **Highest** | **yes** | L |
| 1 | Material-side convention, lifted to one place | **done** | no | — |
| 2 | Convexity probe shared; the arc attribute is separate | **probe done** | no | — |
| 3 | Smooth arcs: through a blend, and across a split | Medium | **yes** | M |
| 4 | One adjacency API instead of two | **declined** | no | — |

**Re-ranked by item 0's sweep, and the numbering is kept so the history stays readable.** The
first version ordered the work by duplication count, which is what the replacement gate below
selects on. The sweep supplied something better: evidence about which of these changes what is
*recognisable* rather than only what is tidy. Items 5 and 4 moved to the top for one measured
reason, recorded in full under "What the sweep changed" below. Item 4 was promoted with them
and has since been demoted again on item 5's own instrumentation — see item 4 for why, since a
re-ranking reversed within a day is worth keeping visible.

**The consolidation half is now done.** Items 1 and 2 are closed, item 0 has run for the four
claiming families, and item 4 is demoted to last. What remains — items 5 and 3, plus the arc
attribute item 2 turned out not to contain — all changes what is *recognised* rather than what is
tidy, and each needs a decision before code. The epic stops being a queue here and becomes a set
of questions.

---

## What the sweep changed

Item 0 ran over 2,000 MFCAD++ test-split models — 51,327 labelled faces, none skipped, none
failed. Four findings, each with an issue, and the first is why this epic is re-ordered.

### The substrate decides what is recognisable, not just what is tidy

| | rectangular | triangular | 6-sided |
|---|---|---|---|
| **pockets** — pair faces within an axis bucket | 38% | **0%** | 4% |
| **passages** — walk connected components over adjacency | 61% | **59%** | 49% |

Same solids, same obliquity, same corpus. `recognise_pockets` buckets faces by `_Face.axis`,
keeps those flagged `wall`, and pairs them within a bucket — a triangular pocket has no two walls
sharing an axis, so it yields zero candidates *before any gate runs*. `recognise_passages` asks
no wall to be axis-aligned.

#75 concluded that *"adjacency is the cheap part"*, on a count of ~25 lines out of 6,198. That
measured syntax. Measured per face, the family built on adjacency traversal is the one with no
orientation gate at all. **Adjacency was not the cheap part; it was the part that decided what a
family could see.** This is the evidence that epic's measurement regime could never have produced,
and it is why items 5 and 4 now lead. Tracked as
[#110](https://github.com/pzfreo/b123d-recognisers/issues/110).

### Axis-alignment is the shared vocabulary, not a per-recogniser gate

`_Face` reduces every face to `normal`, `axis`, `wall` before anything decides, and nineteen
modules reference axis alignment. So the oblique gap is a property of the reduction the shared
core performs *before* a recogniser is consulted, which is why it shows up identically across
families and why no single fix has ever been proposed for it. `FaceGraph` carries `normal`,
`bounds` and `surface` and **no** `axis` field — the graph node is orientation-neutral where
`_Face` is not, which sharpens item 1 rather than changing it.

### Categories fail as whole classes, and thresholds get the blame

Blind steps 62%, rectangular *through* steps 8%, 2-sided 1%, slanted 2%. Both extremes are
axis-aligned in every wall, so shape separates neither; what separates them is the feature
reaching the part boundary. The recess core enumerates categories by how many ends are capped,
and a step running off one edge is too open for `recognise_pockets` and not open enough for
`recognise_channels`. 5,512 labelled faces sit in that crack. A hole in the category system, not
a threshold — which is why tolerance work never found it, and why a fitted measurement could not
tell it apart from the orientation gap. Tracked on
[#89](https://github.com/pzfreo/b123d-recognisers/issues/89), whose own table this corrected.

### Reconciliation has a ceiling set by the weakest recogniser

28 chamfer records survive on faces labelled *Triangular blind step* — the exact faces
`chamfers_that_are_not_angled_steps` exists to remove — because `recognise_angled_steps` never
claimed them. **A precedence rule corrects double-counting, not recall.** When one family misses
what another proposes, reconciliation converts a false negative into a false positive, and the
census reads healthy either way: one record per face, wrong family. ADR 0003 offers accept,
combine or reject, and there is no *"contested, and not confident"* — which is the first argument
for ADR 0004's residual-evidence half that comes from measurement rather than architecture.
Tracked as [#111](https://github.com/pzfreo/b123d-recognisers/issues/111) and
[#112](https://github.com/pzfreo/b123d-recognisers/issues/112).

**Issue #111 is now addressed for the demonstrated representation failure.** The family reads a
terminal plane as a local smooth-coplanar gAAG region and proves that region's actual exterior is
three straight runs. A valid sewn solid, collinear splits, multi-face splits, holes, STEP
round-trip, all principal axes and 0.001×–1000× scale are positive evidence; rectangular and
notched regions, curved boundaries, fillet bridges, invalid/backtracking loops and a rectangular
region split into triangular patches are negative evidence. Claims remain slant-only and the
central rule is unchanged. The 40-model design subset and the previously frozen 33-model holdout
remain unchanged, including 8/8 held-out angled-step precision and no stock claims. The original
2,000-model sweep is not available in this repository, so the historical 28 is not rewritten as a
recovery count: the implementation decision rests on the geometric motif, not an unrepeatable
aggregate score. A first-class contested outcome remains separate residual-evidence work.

**The bounded rectangular-through-step seam is now implemented.** Development-only inspection
found a repeated geometric motif rather than a useful score threshold: two orthogonal principal
planar regions, normalized through direct coplanar AAG arcs, joined by one complete concave seam
and running between the same two source-solid ends. The recogniser additionally proves distinct
envelope-reaching profile legs, convex terminal context, absence of a third co-spanning concave
region, and an exactly material-free removed prism. It records the actual open three-point section
and claims every source patch in the two defining regions. On the 40-model design subset this
produces three records claiming 6 of 26 incidentally present rectangular-through-step faces with
no off-class claims; those counts are diagnostic evidence after the geometry was stated, not the
definition. After the predicate and two independent reviews were fixed, the frozen 33-model
holdout produced three additional records claiming six faces, all correctly labelled rectangular
through step. Two-sided, slanted, interacting and incomplete variants remain explicitly deferred.

**Two-sided through steps were investigated and deliberately not implemented.** The clean
development motif is an induced all-concave three-region tripod: two generally oblique side walls
share a spine and meet a terminal material face along two V rays. That terminal face commonly
continues far beyond the local feature footprint, so claiming the whole face would misrepresent
ownership merely because MFCAD++ labels it as one feature. The current `ThroughStep` record also
cannot preserve the orientation-neutral 3-D tripod or distinguish its capped and open spine ends.
A future bounded family therefore needs a skeleton record (apex, spine endpoint and both V
endpoints), exact empty-wedge evidence, and either sub-face claims or an explicit consulted-context
role. Larger interacting components, concave chains and corpus-labelled face aggregates are not a
justification for a loose K3 recogniser. This is recorded as a research prerequisite rather than
turned into a fitted implementation.

**A bounded round-bottom blind-slot family is the next implemented mixed-surface gain.** The
development subset contributes only one model, but its two independent instances expose the same
exact analytic motif at different sizes/orientations: a flat floor tangent to two equal-radius
quarter cylinders, one matching concave cap, one source-envelope opening, and one materially empty
constant U sweep. The implementation decision therefore rests on constructed topology properties,
including split representation, through/two-cap, cap-hole, cap-continuation, bridge, compound and
family-confusion adversaries—not on recovering eight labels. It uses a dedicated record because
the existing rectangular/obround pocket records cannot preserve this cross-section. The two
development records claim eight faces, all carrying the horizontal circular-end blind-slot label.
After two independent implementation reviews accepted the geometry and layering, the frozen
33-model holdout produced five more records claiming twenty faces, all with that same label.
The ten NIST complex-part contracts, installed-wheel schema/type checks and Draftwright's bounded
downstream contract remain green; the composite workload remains within its recorded ceiling.

### And the negative control failed at scale

No claim landed on *Stock* across the vendored 40's 271 such faces. Across 13,438, four did.
`test_no_claim_lands_on_a_stock_face` passes on the vendored subset because 271 faces is too few
to contain the case — this epic's own corpus-blindness argument, landing on the test written to
embody it. Tracked as [#108](https://github.com/pzfreo/b123d-recognisers/issues/108).

## The method this epic is committing to

**Measure the disagreement before migrating.** Every consolidation in the previous epic that was
undertaken on an assumption of equivalence found something: phase 1 consolidated five adjacency
implementations and [#82](https://github.com/pzfreo/b123d-recognisers/issues/82) then found a
sixth, written as a list comprehension with no dedupe and no self-exclusion. `_recess_core._Face`
looked like the obvious next migration and turned out to be the one that must not happen, because
its normal convention and `FaceGraph`'s were believed to differ by a sign the recess families
depend on -- which measurement later showed they never do (see item 1).

So each item below starts with a count, not a patch: run the existing implementations over the
72 corpus parts and record where they disagree. That converts "is this mechanical?" from a
judgement into a number, before any code moves.

**Goldens are refactor safety, not correctness.** Where the copies agree, byte-identical goldens
are the right check and the migration is mechanical. Where they disagree, one of them is wrong,
the golden **must** move, and the change needs the evidence standard
[#104](https://github.com/pzfreo/b123d-recognisers/pull/104) used: establish which answer is right
first, regenerate second, and say in the PR what moved and why.

These two are in tension by construction. A consolidation of implementations that *agree* is
cosmetic; the debt is precisely where they do not. "Capture the current results and replicate them
underneath" is therefore the correct plan for part of this work and a way of freezing a bug for
the rest, and the count in each item is what tells the two apart.

**The corpus is a false-negative detector, not ground truth.** Three defects lived in code the
golden corpus exercised on every run and none was visible to it; they appeared only when real
turned parts were vendored. Byte-identity over 72 parts proves the new code agrees with the old
code on those parts. Where half the classes are unrecognised, capturing current output as golden
also encodes that absence as correct.

**So what carries the weight instead**, in descending order of strength, and item 1's checklist is
the worked example:

1. **An independent oracle**, where a cheap one exists. For material side it does: step a point off
   the face along the claimed outward normal and classify it against the solid. That is a different
   mechanism from every implementation being checked, so it can say which one is *right* — which no
   amount of cross-comparison between copies can. For pair convexity the oracle *is* the incumbent
   implementation, which is why item 2 is the easier of the two.
2. **Metamorphic properties**, where no oracle exists. You need not know the right answer, only how
   it must transform: mirror the solid and every material-side answer flips; scale it and every
   topological answer holds. `recognise_angled_steps` already rests on the second — *"a step is a
   step at any scale"* — and it is the strongest assertion in that module.
3. **Mutation testing**, to check the tests can see a break at all. #104 ran five; four were caught
   and the survivor exposed a real ordering defect that record counts could never have shown.

Goldens keep exactly one job, and it is a real one: proving that **nothing else moved**. That is a
blast-radius check, not a correctness check, and this epic should not ask more of them than that.

## The gate this epic replaces

Every phase of [#75](https://github.com/pzfreo/b123d-recognisers/issues/75) was declined or
narrowed on **recall or runtime**, and each decision was defensible alone. Five of them were
reversed within days — the components extraction, run-local ownership, coordinate-based
passage/slot reconciliation, and the shared triangular-companion predicate. The declines that
stand are the ones about performance and machinery: the shared edge→faces map at a 1.9% ceiling,
subgraph matching, gAAG, public serialised ownership.

The split has a cause. Identity, ownership and classification produce no recall and no runtime, so
a regime measuring only those two could return "no consumer" indefinitely, and did. The
architecture was not avoided; it was made implicit and inconsistent.

**Replacement gate: does this concept already exist privately in more than one place?** It is a
duplication-and-drift question, answerable by grep, and it does not require the value to show up
in a metric that structurally cannot carry it. Applied today it selects items 1, 2 and 4, would
have selected the components walk at two copies and ownership at two, and still correctly declines
subgraph matching, gAAG and serialised ownership — which exist zero times.

**It is a selection gate, not a ranking one, and item 0 supplied the ranking.** Duplication says
what is worth doing; it says nothing about order, and ordering by it put the two items that change
what is recognisable last. Per-face attribution is the ranking instrument, and it only became
available once six families claimed — which is itself the answer to why #75 could not have found
any of this. Both are needed: the gate keeps speculative architecture out, the measurement decides
what to build first among the things that pass.

---

## 0 — Per-face recall, measured rather than fitted

`behaviour-neutral` · no source change

Every recall figure quoted for this package outside chamfers and angled steps comes from
non-negative least squares fitting record counts against labelled-face counts across models. That
is correlational: it infers attribution rather than observing it, R² is weak for several families,
and it cannot distinguish "not recognised" from "recognised under a different family name".

[#75](https://github.com/pzfreo/b123d-recognisers/issues/75) identified the fix and named it a
prerequisite: *"recall scoring needs face ownership, not the whole graph"*, and *"the MFCAD++
evaluation should be re-run per-face once 5a exists, before any further architectural conclusion is
drawn from it"*.

**It exists now and has never been used.** Six families write defining claims into the ledger —
slots, passages, grooves, turned steps, chamfers, angled steps — and MFCAD++ labels live on the
`ADVANCED_FACE` name, so claimed node → face → label is a direct join.

- [x] `tools/per_face_scan.py`, run over the vendored 40, pinned by two tests
- [x] Widen claiming to pockets — the largest thing the scan was blind to
- [x] Sweep 2,000 MFCAD++ test-split models, streamed from the archive: 51,327 labelled faces,
      0 skipped, 0 failed
- [x] Classify the misses — see "What the sweep changed" above, and #108–#112
- [ ] Widen claiming to holes, fillets and bosses, which still write none
- [ ] Re-run once they do, and once item 5 has moved

**What the first run established, and the limit it hit.** Angled steps claim 11 faces, all
labelled *Triangular blind step*; chamfers 11 of 14 on *Chamfer*, the same 79% the record-centroid
test measures, reached independently through the ledger. Passages claim 103 faces and **every one
is a passage** across all three shape variants, which the family does not distinguish — a
vocabulary difference, and a number never measured before. Slots claim 73 faces across 11 labelled
classes, most of them *Circular end pocket*; that is the one the scan records rather than
endorses, and item 5 is where it should be settled. No claim lands on *Stock*, which is the
negative control and the assertion a precision figure cannot make.

**The limit is claiming coverage, not corpus size.** Per-label share here means "claimed by a
*claiming* family", and only four claim. *Through hole* 0%, *Blind hole* 0%, *O-ring* 0% and
*Rectangular pocket* 1% are statements about the ledger, not about the recognisers — holes,
pockets, fillets and bosses write no claims at all. Grooves and turned steps claim but have no
MFCAD++ counterpart, the corpus being prismatic. So a larger draw would multiply the models
behind a table whose rows are mostly structurally blind, and **widening claiming has to come
first.** That the measurement's reach is bounded by substrate adoption is this epic's ordering
argument, arrived at empirically rather than asserted.

## 1 — Material-side as a named node attribute

`behaviour-neutral where the copies agree`

"Which side of this face is the material" is answered privately in four places, by one convention
specialised to three surface types:

| site | surface | shape |
|---|---|---|
| `_recess_core._outward_normal:74` | plane | orientation `FORWARD` × plane frame handedness |
| `_recess_core:330` | cylinder | *"mirrors `_outward_normal`'s FORWARD/handedness test"* |
| `_cylinder_substrate.py:87` | cylinder | orientation × `Position().Direct()` |
| `_hole_features.py:287` | sphere | orientation × `Position().Direct()` |

**A correction worth recording**: an earlier reading of this called it three mutually incompatible
styles. It is not. These four agree in method and differ only in surface type, which is duplication
rather than drift. The genuine incompatibility is between this family and `FaceGraph.normal`, which
was believed to be *geometric* (`normal_at`) and to differ by a sign on `REVERSED` faces.
**That was wrong**, and it is corrected below. Both were thought live,
both are correct for their own question, and nothing in the package says so — the distinction
currently survives as a note explaining why `_recess_core._Face` must not be migrated.

**And the corpus cannot answer this one on its own.** The convention has two factors, and they are
not equally exercised. Surveyed over all 72 parts: `REVERSED` faces number 3,061 of 4,407 and every
one of the 72 parts carries at least one, so the orientation factor is well covered. **Left-handed
surface frames number 6 of 3,853, on 1 of 72 parts.** Since a two-term convention differs
precisely where handedness flips, a disagreement count over the corpus would very likely come back
zero and mean nothing — the same blindness that makes goldens the wrong check here, one level down.
So the count is necessary and not sufficient, and the falsifier has to be built rather than found.

- [x] Count where the four disagree — and establish first that the corpus *cannot* answer it.
      `REVERSED` faces are 3,061 of 4,407 across all 72 parts, but left-handed frames are **6 of
      3,853, on 1 of 72**, and deleting the handedness term left all 667 tests green (#115)
- [x] Generate the four-cell matrix from mirrored solids, with a test asserting the fixtures reach
      all four so the suite cannot quietly cover three (#115)
- [x] Check against an **independent oracle** rather than against each other (#115)
- [x] One implementation, `_adjacency.frame_points_outward`, and all four call sites on it;
      byte-identical over all 72 parts (#116)
- [x] **No node attribute, deliberately.** None of the four call sites holds a `FaceGraph` --
      `analyse_cylinders` takes a bare part -- so a method with no consumer is the speculation
      this project declines. What the attribute was *for* is visibility, delivered instead in
      `FaceGraph.normal`'s docstring -- which then turned out to be stating something false, and
      is corrected below. That reason had lived only in a memory note
- [x] `_recess_core._Face` keeps its own reader, and now shares the convention underneath it

The prize is not the four lines. It is that the next recogniser needing material side finds one
attribute with a name that says which convention it is.

**Postscript: the premise of this item was false, and measuring it is what showed that.**

Item 1 rested on there being two material-side conventions in the package, differing by a sign on
`REVERSED` faces -- the stated reason `_recess_core` could not read the graph, written into
`FaceGraph.normal`'s docstring and into the note explaining why `_Face` must not migrate.

There is one convention. build123d's `normal_at` already applies the orientation correction, so
`FaceGraph.normal` *is* the material-side normal. Measured over 1,144 imported-STEP faces from a
corpus that is 70% `REVERSED`, and over generated mirrored solids covering all four
orientation/handedness cells: the two are **never** opposite, and `normal` survives the
solid-classifier falsifier in every cell.

So `FaceGraph.outward_normal`, added under this item, is removed again -- it computed by a longer
route what `normal` already returned. `frame_points_outward` stays for the three sites that ask
*which side* about a whole face with no single normal to read.

The falsifier built for this item is what caught it, one PR later, by being pointed at the other
reader. That is the argument for building a falsifier before a migration rather than after: it
outlives the migration and can be aimed at the next claim.

## 2 — The convexity probe, shared; the arc attribute, still unbuilt

`the probe is done; the arc is not, and it is a different thing`

This is the AAG's defining attribute, the one [#75](https://github.com/pzfreo/b123d-recognisers/issues/75)
phase 2 called *"this is the actual AAG"* and declined for want of a consumer. **It has two, and it
is already implemented for both:**

- `chamfers.convex_bevel:142` — reconstruct the virtual sharp corner where the two neighbour
  planes cross, nudge toward the bevel face, and classify the point against the solid
- `fillets.py:138–147` — the same construction, inline, with the sense inverted

**The framing above was wrong, and the item is split because of it.** It read as "the arc attribute
already exists twice, just lift it". Two different things were being conflated:

- **the probe** existed twice and is now lifted — `fillets` calls `chamfers.convex_bevel` rather
  than restating it, byte-identical over all 72 parts (#117). That was the consolidation, and the
  replacement gate selected it correctly;
- **the arc attribute** does not exist at all, and cannot be built from the probe.

The reason is structural rather than a matter of effort. The probe answers *"is the corner where
these two neighbour planes cross convex"* — and **those two planes do not share an edge.** The
blend sits between them. There is no arc in the graph to hang the answer on, because the pair whose
convexity is being measured is not an adjacent pair.

An arc-shaped answer has to be a *different computation*: the dihedral between the blend face and
each neighbour, which are adjacent. That is plausible and probably right, and it is **new
capability, not consolidation** — a behaviour change with its own evidence to earn, which is why it
now sits with item 3 rather than here.

Two design facts whichever way that goes:

- **The probe is better than the angle where it applies.** It classifies actual material at a
  point rather than inferring from a normal difference, which is why the chamfer recall analysis
  found nothing for an angle-based attribute to improve on. Adopting Analysis Situs's dihedral
  taxonomy wholesale would be a downgrade for this case.
- **It does not generalise as written.** It needs a *virtual corner*, which needs two axis-aligned
  neighbour planes. An arc between two arbitrary faces cannot be classified this way, so the
  general case needs the angle as well and the arc attribute is a union of the two, not a
  replacement of one by the other.

- [x] Confirm the two implementations are the same decision, not merely similar ones: identical
      construction, probe fraction and classifier tolerance, differing only in whether the caller
      reads the result as keep or skip
- [x] `fillets` calls `convex_bevel`; byte-identical over all 72 parts, and inverting the shared
      probe now fails 10 tests where the same break previously had to be made twice (#117)
- [ ] **Open, and not this item's work:** an arc attribute means dihedral classification between
      *adjacent* faces. Angular per ADR 0008, dimensionless, defaulting off — the same gate item 3
      needs, and the same consumers, so the two should be decided together

**Raised by the lift, and then resolved.** The probe reached three consumers — `chamfers`,
`angled_steps`, `fillets` — while living in a recogniser the other two also imported
`classify_bevel` from. Two could be read as one module happening to import another; three is an
undeclared layer. It is now `_bevel`, with a seam-map entry that can have an opinion about it.
Behaviour-neutral, and the public surface is unchanged and asserted: `BevelReject` and
`classify_bevel` are still exported from `b123d_recognisers` and still reachable through
`chamfers`, which is what ADR 0005 requires of a versioned contract.

## 3 — Smooth arcs, for seeing through a blend and across a split

`behaviour-changing` · blocked on item 2

ADR 0004's amendment (PR [#105](https://github.com/pzfreo/b123d-recognisers/pull/105)) adds the
criterion this needs, and it has **two limbs**: two regions separated by a blend face are reachable
under a named relation, *and* a face subdivided by a neighbouring feature answers as one region.

**One mechanism serves both, and the reason should be stated rather than assumed.** A subdivided
face is not separated by a blend — it is split, and the two pieces are coplanar and share an edge.
The arc between them is therefore the *zero-angle* case of smoothness, so a traversal that walks
smooth arcs and reports the merged region's boundary answers the split limb as a degenerate case
of the blend limb. If an implementation delivers blend traversal without recovering split faces,
the item is half done however well the first limb works, and the two acceptance tests below are
what keep them apart.

ADR 0004's own decision text already says nodes identify *"faces or **normalized regions**"*. That
region concept is unbuilt, and neither the amendment nor this item introduces a new one — the
merged region is a query result, not a second node type.

Two live consumers, one per limb, both already costing recall:

- `grooves._joined` matches a conical lead-in to both band rims by hand, because a manufactured
  groove's bands never touch (issue #60). Without it the groove is absent, not mis-measured.
- `recognise_angled_steps` finds a blind end by an exactly-three-edge neighbour, so a triangle a
  neighbouring feature subdivides reads as four or five. 24 of its 49 misses over 120 MFCAD++
  models have no bare triangular face on them.

The Analysis Situs taxonomy's useful part is the *sided* smooth pair — `SmoothConcave` and
`SmoothConvex` — since a tangential join still has a material side. Its `Collapse()` primitive is
explicitly not the shape to copy: it mutates the graph, propagates attributes to inserted arcs only
where angles are equal, and its header warns `PopSubgraph()` does not clean them up.

- [ ] Angular smoothness gate, dimensionless per ADR 0008, defaulting off
- [ ] A **named** traversal query — not a widened `neighbours()`, which would move every existing
      recogniser's answer at once
- [ ] **Blend limb:** `grooves._joined` reimplemented on it, or the item is not done
- [x] **Split limb:** a subdivided triangle answers with three boundary runs, tested separately
      from the blend limb on geometry with no blend. The historical 24-miss source corpus is not
      available locally, so no post-change recovery count is claimed.

**The split limb is now implemented without claiming an unavailable recovery count.** Issue #111
normalizes a subdivided angled-step terminal, and 0.2.11 lifts its direct-planar traversal into the
cached neutral `FaceGraph.coplanar_region` query when prismatic ring walls become the second real
consumer. Both families reduce the actual regional boundary rather than a convex hull. The
original 2,000-model sweep is not vendored, so its historical 24 misses remain diagnostic context,
not a claimed post-change result. The 40-model design subset is unchanged by both bounded motifs.

## 4 — One adjacency API instead of two

`behaviour-neutral`

Phase 1 consolidated five implementations into `edge_face_map`. #92 then built `FaceGraph` beside
it. Both are live and the split is by module, not by need:

- **graph** — `passages`, `polygonal_bosses`, `_recess_core`
- **dict map** — `_hole_features`, `angled_steps`, `chamfers`, `fillets`, `flats`

Claiming is much wider than reading: six families write claims, but only `passages` and
`polygonal_bosses` read node attributes at all. `chamfers` and `angled_steps` claim a node and then
derive their own normals and bounds by hand three lines later.

**Promoted on the sweep, then demoted again by item 5's own measurement. Both are recorded,
because the mistake is instructive.** The promotion claimed the five dict-map modules "are the
ones that find features by pairing axis-aligned faces, and the recess core does the same through
`_Face.axis`". That conflated two different things. `chamfers`, `angled_steps` and `fillets`
consult `nearest_axis_aligned_planes` — axis-dependent, but not *pairing* — while `flats` and
`_hole_features` only walk neighbours. **The pairing that costs the recall is in `_recess_core`,
which is not one of the five and already uses `FaceGraph` for its claims.**

So migrating those five would not unblock item 5, and moving them to a graph API leaves
`nearest_axis_aligned_planes` exactly as axis-dependent as it was. The original caution was right
and stands restored: a migration whose only benefit is API uniformity is the kind this project has
correctly declined before, and this is one. It goes last.

What *would* help item 5 is `_recess_core` reading faces from `FaceGraph` nodes so `_planar_faces`
can retire — and that is item 1's territory, not this one's.

**Declined, and closed rather than deferred.** A deferred item reads as a plan; there is no plan
here, only a condition. Its whole benefit is that one API replaces two, and item 5's
instrumentation showed that buys nothing: the five modules do not pair by axis bucket, so
migrating them leaves `nearest_axis_aligned_planes` exactly as axis-dependent and unblocks
nothing. That is the definition of a uniformity migration, which this project has declined
before and should again.

It becomes worth doing on the same condition #75's components extraction was: **when a migrated
module would read node attributes too**, rather than only swap one adjacency call for another.
Today none would.

Note that the substrate work this item was ranked highly for did happen, under items 1 and 2 and
under `_bevel` — by lifting the *concepts* three modules shared rather than the API they called
them through. That is the distinction the original ranking missed.

## 5 — Oblique recesses: a migration with a precedent, not a scope decision

`behaviour-changing` · the highest-value item, on item 0's evidence

**Corrected by item 0's first run.** The inherited claim — from #75's non-negative least squares,
which was the best evidence available then — was that the dead classes are the *"triangular,
slanted, 6-sided and 2-sided"* variants while their rectangular counterparts recognise. Measured
per face over the vendored 40, that lumps together two groups that behave differently:

| class | claimed |
|---|---|
| Rectangular passage | 81% |
| Triangular passage | 40% |
| 6-sided passage | 27% |
| Slanted through step | **0%** |
| Triangular pocket | **0%** |

The odd-*sided* prismatic classes are not dead — `recognise_passages` claims them, and it
post-dates the measurement that called them empty. What is dead is the oblique-*walled* group,
which is a narrower and more accurate statement of the same finding: a wall whose normal aligns
with no principal axis dies at `AXIS_ALIGNED_COS`, one face at a time, before adjacency is
consulted. Side count was never the discriminator; orientation was.

**This was written as a scope decision — implement oblique support, or document the exclusion.
The sweep withdrew that framing.** `recognise_passages` scores 59% on triangular geometry and 49%
on 6-sided, flat across obliquity, on the same solids where `recognise_pockets` scores 0% and 4%.
So oblique support is not a research question with an honest "no" available: one family in this
package already has it, and the difference is that it walks adjacency instead of pairing faces
within an axis bucket.

That makes this a migration with a working precedent in-tree. An earlier draft added that item 4
was therefore its prerequisite; the instrumentation below withdrew that, because the axis-bucketed
pairing lives in `_recess_core` and not in the five dict-map modules. The prerequisite is item 1 —
`_recess_core` reading faces from graph nodes, so `_planar_faces` can retire.

- [x] Confirm the mechanism by instrumentation, not by reading (#110). Measured over 600 models,
      tracing every labelled face through the reduction: **94% of triangular-pocket faces never
      reach a gate** -- they are oblique, or axis-aligned with no same-feature partner in their
      bucket, so no pair is formed and `_pocket_candidate` is never called. Pairability explains
      recall rather than merely correlating with it (80% pairable → 38% claimed for rectangular
      pockets, 8% → 4% for 6-sided, 6% → 0% for triangular). The control settles it: **triangular
      passages are 2% pairable and 59% claimed**, because `recognise_passages` does not pair
- [x] Assess whether the recess core can be found ring-first as `recognise_passages` is. The
      answer is the separate `recognise_prismatic_pockets` family: it walks one-capped rings of
      arbitrary planar cross-section without changing the paired rectangular `Pocket` contract.
- [x] Reconcile the overlap centrally: a four-wall ring yields to the dimensioned rectangular
      `Pocket`; a non-rectangular ring survives and defeats paired-wall fragments.
- [x] State the boundary in `capabilities.md`, including obrounds (no planar ring), open passages,
      enclosed cavities and genuinely interrupted/piecewise walls.

---

## Not in this epic

- **Subgraph isomorphism.** Replacing golden-pinned procedural recognisers with pattern matching is
  a rewrite with no evidence behind it, and the declared position since #75. Unchanged.
- **gAAG, UV sampling, learned recognition.** Closed by ADR 0002's determinism contract.
- **Public serialised face ownership.** Zero consumers, and it needs a stable identity scheme that
  fixture-stable face order cannot provide.
- **Migrating `_recess_core._Face` to `FaceGraph` nodes.** Investigated and rejected: the
  conventions were believed to differ by a sign the recess families depend on. Item 1 makes that
  supposed difference
explicit; it does not remove it.

### Semicircular-bottom blind-slot iteration (0.2.12)

The next bounded gain uses the same substrate for a distinct sharp profile: two rectangular
planar legs tangent to one half-cylinder and closed by one exact cap. It deliberately rejects the
interacted extra-closure and chamfer/cone-mediated development anatomies rather than reconstructing
them from labels. Synthetic topology and actual-boundary invariants define acceptance; the
development subset's two records/eight on-target claimed faces are post-design diagnostics. The
frozen holdout was revealed only after two independent implementation reviews accepted the
result; it adds three records/twelve on-target claimed faces without changing the predicate.
