# Tests-first recogniser delivery protocol

This is the supported landing protocol for a recognition family that can affect both
`b123d-recognisers` and Draftwright. The repositories do not merge in lockstep: the package owns
geometry evidence and immutable records, while Draftwright owns every downstream interpretation.
Each intermediate commit and release must leave both repositories green and independently
releasable.

Start from the recogniser issue template. Evidence is authored before behavior: define the B-Rep
scope and tolerances, record schema, negative and ambiguous cases, canonical functional tests,
topology-order variants, operation-count and wall-time budget, and fixture/code provenance. A
behavior change also needs its own approved issue and compatibility note; cleanup must not silently
weaken those tests.

## Ownership of tests

| Evidence | Owner |
| --- | --- |
| geometry contract and canonical functional tests, negative topology, determinism and performance | `b123d-recognisers` |
| public record typing, serialization, manifest family and schema | `b123d-recognisers` |
| IR adapter and parameter identity | Draftwright |
| DSL and generated-code round trip | Draftwright |
| drawing regression, annotation placement and lint | Draftwright |
| completeness semantics, requirements and score policy | Draftwright |

Tests must derive inventories from runtime exports, type hints, registries or executable branches;
comparing two declarations produced from the same table is not independent evidence.

## Compatible landing order

### 1. Propose and freeze evidence

Open the package recogniser proposal and the linked Draftwright capability decision. Add independent
fixtures and negative expectations without enabling new behavior. Reserve a stable family ID when
needed. **Both repositories green:** released behavior, consumer lock and existing declarations are
unchanged.

### 2. Publish an additive package contract

Implement and test geometry recognition in the package. Add the immutable record, public typing,
schema version, manifest entry, documentation, functional tests, provenance and performance bound
together. Publish the stable additive package only after its own contract and release gates pass.
The current release path does not support prereleases, so this protocol does not claim a pre-release
consumer join. **Both repositories green:** Draftwright still consumes its previous exact release;
the new package artifact is independently valid but not yet consumed there.

### 3. Add consumer support

After the additive package release exists, open a Draftwright branch that updates the immutable
package version and hashes in the lockfile to that exact stable artifact. Declare every downstream
state and add independent IR, DSL, code-generation, drawing and completeness tests that apply. Use
`deferred` with a tracking issue or `not-applicable`/`unsupported` with evidence when support is not
valid. Draftwright's own CI proves the join before its pin-bump PR merges.
**Both repositories green:** package behavior is additive; released Draftwright ignores it, while
candidate Draftwright fails closed against exactly the new contract.

### 4. Enable behavior

Merge the Draftwright adapter/policy branch only after its released package lock, generated-Sheet
round trip, drawing regressions and completeness decision are green. Enable user-visible recognition
only in the repository that owns it and only under the approved behavior issue. **Both repositories
green:** old Draftwright remains compatible with the older package pin and new Draftwright consumes
the new immutable artifact.

### 5. Clean up and deprecate

Remove compatibility scaffolding only after all supported consumers have moved. Keep deprecated
family/record aliases for the period required by ADR 0005, with replacement and removal versions.
Release levels follow ADR 0005: prose/evidence-only fixes use a patch; a supported family, additive
optional record field or additive schema version uses a minor; a required-field change or removal
uses the next minor before 1.0 and otherwise a major, with aliases and deprecation where
representable. **Both repositories green:** aliases and version ranges remain valid until the
documented removal release.

Do not merge a mutable Git/path dependency, duplicate a recogniser in Draftwright, or widen a
production range merely to make paired branches pass.

## Versions, rollback and failure ownership

- Release levels follow ADR 0005's transition table: prose/evidence-only fixes use a stable patch;
  new supported families and additive optional public fields or schemas use a stable minor; required
  or removed contract elements use the next minor before 1.0 and otherwise a major, with the
  prescribed migration evidence.
- Draftwright's declared and locked production range is deliberately a singleton stable version, not
  an open interval. Its tested compatibility window is therefore the exact artifact named by the
  consumer declaration; widening that window requires evidence against every newly admitted version.
- Production Draftwright uses an exact stable package version and checked `uv.lock` artifact hashes.
- The current package release path does not support prereleases. Cross-repository compatibility is
  therefore established stable-package-first: the additive artifact is published from green
  package evidence, then Draftwright pins and tests it before changing its production dependency.
- Additive records land package-first. Breaking changes require the ADR 0005 release level and
  migration evidence: the next minor before 1.0 and otherwise a major, plus a deprecation window
  and consumer support before removal where the change is representable by an alias.
- Roll back Draftwright by reverting its dependency/overlay commit to the last known registry hash.
  Roll back package behavior with a new patch release; never replace an existing PyPI file or tag.
- A package geometry/fixture/manifest failure belongs to `b123d-recognisers`. An IR, DSL, generated
  code, drawing or completeness failure belongs to Draftwright. A join failure is triaged jointly,
  but the declaration remains Draftwright-owned and geometry truth remains package-owned.

## Geometry-only and deferred families

A useful geometry record does not need drafting semantics. Publish its package evidence normally,
then declare the Draftwright family `geometry-only`, give a rationale and evidence, and mark IR,
DSL, generated code and drawing `not-applicable`. A meaningful but intentionally delayed stage is
`deferred` and must link a tracking issue. Never add a placeholder adapter or inferred CAD intent to
make the capability table look complete.

## Upgrading Draftwright

Compatibility is proven where the upgrade happens: on a Draftwright branch that moves the exact
lockfile pin to the stable package artifact. Draftwright's own CI runs its capability/import contract
tests, drawing regressions and completeness checks before the pin-bump PR merges. This package's CI
does not run Draftwright's tests. The package-first order is safe for additive contracts because the
existing Draftwright release remains locked to its previous artifact; the new artifact becomes a
production dependency only after Draftwright has tested and reviewed the exact pin. The consumer PR
is the review point for any semantic transition the release notes declare.

## BossRecord walkthrough

The existing `bosses` family demonstrates the protocol without changing recognition:

1. Package-owned cylinder fixtures independently establish `BossRecord` location, axis, diameter
   and height, negative ownership cases, deterministic JSON and the `bosses` manifest schema.
   **Both repositories green:** no consumer declaration is needed to validate geometry truth.
2. Package 0.2.0 publishes that stable record and manifest as immutable PyPI artifacts.
   **Both repositories green:** the previous Draftwright lock remains reproducible.
3. Draftwright's consumer declaration joins `bosses` to `_convert_boss`, `Sheet.boss`, generated
   feature code, diameter rendering and boss-height coverage, with independent tests for each seam.
   **Both repositories green:** the join is tested against the released artifact before merge.
4. The generated Sheet is executed and its rebuilt boss parameters equal the detected IR.
   **Both repositories green:** geometry records contain no Draftwright policy, and Draftwright has
   no copied recognition implementation.

This walkthrough is contract evidence, not authorization to change boss recognition behavior.
