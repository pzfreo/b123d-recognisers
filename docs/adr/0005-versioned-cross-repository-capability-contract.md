# ADR 0005 — Versioned cross-repository capability contract

- **Status:** Accepted
- **Date:** 2026-08-15
- **Decider:** Paul Fremantle
- **Package review:** `b123d-recognisers` issue #22
- **Consumer review:** `draftwright` issue #1173

## Context

A public recogniser is not automatically a drafting feature. This package owns geometry-only
recognition, while Draftwright separately owns its IR, declarations, compiler, generated code,
drawing policy, and completeness semantics. A new record family can therefore be valid package
capability even when it deliberately has no Draftwright representation.

Code and prose alone do not make that boundary safe. A package release can add an exported
recogniser that a consumer does not know exists; a consumer declaration can outlive the adapter
or test that once justified it; and an apparently empty downstream implementation can mean
either an intentional geometry-only boundary or unfinished work. Those cases must be distinct
and machine-checkable.

ADRs 0001 and 0002 remain authoritative. In particular, the package must not import Draftwright
or encode drafting policy as geometry truth, and its public records remain deterministic,
frozen, serialisable geometry values. Draftwright ADRs 0011, 0013, 0015, and 0017 remain
consumer decisions rather than package policy.

## Decision

Use two versioned JSON documents joined by stable feature-family identifiers:

1. The **package manifest** is distributed by `b123d-recognisers`. It declares public
   recognition families, entry points, record schemas, package versions, independent golden
   evidence, and documentation.
2. The **consumer declaration** is maintained by Draftwright. It pins a supported package and
   manifest range and declares the state of each package family at the IR, DSL, generated-code,
   drawing, and completeness boundaries.

Neither document is authoritative for the other repository's implementation. Each repository
derives its actual inventory independently and validates the declarations against it. The join
is a compatibility contract, not a shared implementation or synchronized release.

### Format version 2 (0.4)

Format 2 adds a required recogniser `role` (`physical`, `compatibility`, or `derived`) and a
family-level `census_output`. These fields make the singular physical authority and counted
aggregate field executable when an old public API remains as a projection. Consumers supporting
only format 1 must reject format 2. Existing family `introduced_in` values remain unchanged; new
record publication is recorded by package release notes and each record's schema version.

Issue #336 advances `RiserEvidence` from schema 1 to schema 2 by adding optional serialized
`body_levels`. Recogniser-produced records always provide the complete same-solid FaceLevel
occurrence authority;
`null` exists only so hand-built schema-1-style records remain constructible and project with their
historical value-only semantics. Consumers that persist or declare RiserEvidence must explicitly
accept schema 2 before enabling compound-safe projection.

### Stable family identifiers

A family identifier is a lower-case segmented token matching
`^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*$`, for example `holes`, `hole-patterns`, or
`repeating-radial-profiles`. It names a semantic recognition family, not a Python module,
function, class, Draftwright feature, or rendered annotation. Refactoring any of those does not
change the identifier.

Identifiers are unique, permanent, and never reused. A family can have more than one entry
point or output record, and a record can participate in more than one family only when that
relationship is declared explicitly. A rename is a compatibility event, not a spelling edit;
the old identifier remains as a deprecated alias for at least one major-version cycle.

### Package manifest, format version 1

The installed distribution exposes one supported public query returning this JSON-compatible
shape. The precise Python query name is implementation work for issue #23.

```json
{
  "format": "b123d-recognisers-capabilities",
  "format_version": 1,
  "package": {"name": "b123d-recognisers", "version": "0.1.0"},
  "families": [
    {
      "id": "bosses",
      "status": "supported",
      "introduced_in": "0.1.0",
      "recognisers": [
        {"entry_point": "b123d_recognisers.recognise_bosses", "kind": "part"}
      ],
      "records": [
        {
          "name": "BossRecord",
          "qualified_name": "b123d_recognisers.BossRecord",
          "schema_version": 1,
          "role": "output",
          "aggregate_membership": ["RecognitionResult.bosses"],
          "fields": {
            "axis": {"type": "tuple[float,3]", "required": true, "units": "unit-vector"},
            "diameter": {"type": "float", "required": true, "units": "mm"},
            "height": {"type": "float", "required": true, "units": "mm"},
            "location": {"type": "tuple[float,3]", "required": true, "units": "mm"}
          }
        }
      ],
      "census_name": "boss",
      "golden_evidence": ["tests/golden/simple_through_hole/expected.json"],
      "test_evidence": ["tests/test_recogniser_contract.py"],
      "documentation": ["docs/capabilities.md#proven-recognition-capability"]
    }
  ],
  "aliases": []
}
```

The top-level fields are:

| Field | Contract |
| --- | --- |
| `format` | Exact document kind. A different value is not this contract. |
| `format_version` | Positive integer schema major. Consumers reject unsupported values. |
| `package.name` | Exact distribution name. |
| `package.version` | Normalized installed distribution version; it must match runtime metadata. |
| `families` | Non-empty, ID-sorted array containing every exported `recognise_*` entry point and every exported `Record` subclass exactly once under a primary owning family. |
| `aliases` | ID-sorted deprecated family/record aliases with replacement, deprecation version, removal version, and rationale. |

Every family requires:

| Field | Contract |
| --- | --- |
| `id` | Stable semantic identifier under the rules above. |
| `status` | Package state: `supported`, `deferred`, or `unsupported`. |
| `introduced_in` | First package version exposing this family ID. |
| `recognisers` | Public qualified entry point plus ADR-0002 kind: `part` or `derived`. |
| `records` | Every public record's name, qualified public import, positive integer schema version, role (`output`, `nested`, `aggregate`, `projection`, or `evidence`), aggregate membership, and serialized field schema. |
| `census_name` | Stable `feature_census` key, or `null` plus a rationale when the family is deliberately absent from the census. |
| `golden_evidence` | Independently authored canonical expected-data paths proving semantics; never generated during validation. |
| `test_evidence` | Behavior/contract test paths, including negative evidence where the supported boundary needs it. |
| `documentation` | Published capability documentation path or stable URL. |

`supported` requires all fields and live evidence. `deferred` means the identifier is reserved
but no public recogniser is shipped; it requires a non-empty `rationale`, an empty recogniser and
record inventory, and no claim of golden support. `unsupported` records a deliberate package
boundary and likewise requires a rationale. Exported runtime entry points may only belong to
`supported` families. Issue #23 may choose not to encode reserved families initially; the states
are defined so their later appearance is unambiguous.

Every exported `Record` subclass has one primary family even when it is not a direct recogniser
return. `nested` covers values such as `CounterBore`; `aggregate` covers values such as
`TurnedProfile`; `projection` covers values such as `StepShoulder`; and `evidence` covers values
retained for orchestration or critique. `aggregate_membership` names each `RecognitionResult`
field containing the record directly or through a declared aggregate; an empty list requires a
rationale. This makes helper/projection records and the aggregate/census boundary visible rather
than accidentally exempt from inventory checks.

The record schema version describes the serialized `.to_dict()` field contract, not the Python
dataclass implementation. Each `fields` key is a serialized field name. Its value requires a
machine-readable `type`, `required` boolean, and `units` string (`none` when dimensionless).
Version 1 types are `null`, `bool`, `int`, `float`, `str`, `record:<PublicName>`, homogeneous
`list[T]`, fixed homogeneous `tuple[T,N]`, and `T|U` unions. Nested public records reference
their own versioned schema instead of duplicating it. Field ordering is lexical in the manifest
and is not a promise about dataclass constructor ordering. Names, types, requiredness, semantic
units, and the meaning documented for each field form the record contract.

Paths use forward slashes relative to the source archive. Manifest validation proves referenced
files exist in the sdist. A wheel need not contain test fixtures, but its public manifest data
must be identical to the sdist's installed manifest data.

### Draftwright consumer declaration, format version 1

Draftwright owns a separate declaration. The illustrative `bosses` family is fully consumed;
`repeating-radial-profiles` is intentionally geometry-only critique evidence and does not gain
an inferred IR feature merely to fill the table.

```json
{
  "format": "draftwright-recogniser-capabilities",
  "format_version": 1,
  "consumer": {"name": "draftwright", "version": "0.4.7.dev0"},
  "package_compatibility": {
    "distribution": "b123d-recognisers",
    "version": "==0.1.0",
    "manifest_format": 1
  },
  "families": [
    {
      "id": "bosses",
      "record_schemas": {"BossRecord": 1},
      "disposition": "supported",
      "ir_adapter": {
        "state": "supported",
        "implementation": "draftwright.model.detect._convert_boss",
        "evidence": ["tests/test_detect_registry.py"]
      },
      "dsl_declaration": {
        "state": "supported",
        "implementation": "draftwright.sheet.Sheet.boss",
        "evidence": ["tests/test_declare.py"]
      },
      "generated_code": {
        "state": "supported",
        "implementation": "draftwright.sheet_emit",
        "evidence": ["tests/test_sheet_emit.py"]
      },
      "drawing_consumer": {
        "state": "supported",
        "implementation": "draftwright.annotations.from_model.render_boss_diameters",
        "evidence": ["tests/test_make_drawing.py"]
      },
      "completeness": {
        "state": "supported",
        "implementation": "draftwright.linting.coverage",
        "evidence": ["tests/test_issue_885_prismatic_coverage.py"]
      },
      "documentation": {
        "state": "supported",
        "evidence": ["docs/reference/sheet.md"]
      }
    },
    {
      "id": "repeating-radial-profiles",
      "record_schemas": {"RepeatingRadialProfile": 1},
      "disposition": "geometry-only",
      "rationale": "Independent critique evidence; gear semantics require authored intent.",
      "package_evidence": [
        "tests/golden/repeating_radial_profile/expected.json"
      ],
      "ir_adapter": {"state": "not-applicable", "rationale": "No inferred gear IR."},
      "dsl_declaration": {"state": "not-applicable", "rationale": "Authored gear declarations are separate."},
      "generated_code": {"state": "not-applicable", "rationale": "No inferred feature to emit."},
      "drawing_consumer": {"state": "not-applicable", "rationale": "Evidence validates authored intent only."},
      "completeness": {
        "state": "supported",
        "implementation": "draftwright.linting.gear_coverage",
        "evidence": ["tests/test_issue_1086_declared_gears.py"]
      },
      "documentation": {
        "state": "supported",
        "evidence": ["docs/research/1062-repeating-radial-profile-evidence.md"]
      }
    }
  ]
}
```

The examples are reviewed against Draftwright's current adapter, declaration, emitter, renderer,
coverage, and critique seams. Issue #1173 must derive and bind their exact supported references
independently when it implements the overlay; the example is not itself validation.

The consumer must declare every package family exactly once and no nonexistent family. It pins
every consumed record schema version. Each downstream capability object has a `state` and the
state-specific evidence below:

| State | Meaning | Required evidence |
| --- | --- | --- |
| `supported` | Implemented and part of the consumer contract. | `implementation` plus one or more independent behavior-test paths. |
| `geometry-only` | Family-level disposition: package evidence is useful, but drafting semantics must not be inferred. | Non-empty rationale, package evidence, and an explicit state for every downstream capability. |
| `deferred` | Applicable work is intentionally scheduled but not yet a consumer capability. | Non-empty rationale and tracking URL; no implementation claim. |
| `not-applicable` | The capability has no valid meaning for this family. | Non-empty rationale explaining the ownership/domain boundary. |
| `unsupported` | Meaningful in principle but deliberately not accepted by this consumer. | Non-empty rationale and negative/diagnostic evidence showing fail-loud behavior. |

`geometry-only` is valid only as the family `disposition`. Other dispositions are `supported`,
`deferred`, and `unsupported`. A `supported` family can still have an explicitly deferred,
not-applicable, or unsupported downstream stage; “supported” means the consumer has deliberately
accounted for the family, not that every stage must exist. A geometry-only disposition cannot
claim a supported IR adapter, DSL declaration, generated-code path, or drawing consumer.

The consumer owns the exact implementation and evidence reference syntax. References must be
resolved independently against installed package exports, Draftwright registries, DSL methods,
code-generation cases, drawing consumers, requirements/completeness policy, documentation, and
tests. Merely deserializing this declaration and comparing it with itself is not validation.

### Fail-closed validation

Package CI independently derives public `recognise_*` exports, every exported `Record` subclass,
their annotated record returns, aggregate membership, census keys, record serialized fields,
runtime package version, and source-archive contents. It fails for an unlisted or multiply listed
entry point/record, stale reference, missing evidence, schema drift, invalid ordering, or
unsupported manifest format. Canonical expected data is input to this check, never rewritten by
it.

Draftwright CI obtains the manifest only through the installed package's public surface. It must
not read a sibling checkout or private package module. It independently derives the actual
adapter, DSL, code-generation, drawing, and completeness inventories and fails for:

- an unknown or missing package family;
- a stale extra consumer declaration;
- an unrecognized record schema version;
- a missing implementation or evidence reference;
- a supported claim without behavior evidence;
- geometry-only capability with invented drafting semantics;
- a transition lacking the version and compatibility evidence below; or
- an unsupported document format/major version.

Errors name the family, boundary, installed package version, expected/actual state, and repair
action. Unknown future families are never silently treated as geometry-only, ignored, or mapped
to a generic feature.

### Compatibility and state transitions

Semantic versions govern observable package and consumer contracts. Pre-1.0 releases may still
use minor versions for breaking changes only when release notes call that out, but the manifest
validator applies the same explicit transition evidence; “alpha” is not permission for silent
drift.

| Change | Required action |
| --- | --- |
| Add supported family or additive optional record field | Package minor release; new evidence and docs; consumer rejects it until an explicit compatible declaration lands. |
| Fix prose/evidence reference without changing contract | Package patch release. |
| Add required record field, change meaning/unit/type, remove field/record/family, or reuse ID | Next minor before package 1.0, otherwise package major; deprecation/alias where representable; migration and release notes. |
| Rename family or record | Add alias and deprecation first; removal is a major compatibility event. |
| Increase record `schema_version` additively | Package minor release; consumer explicitly lists the accepted version before using it. |
| `deferred`/`unsupported`/`geometry-only` to consumer `supported` | Draftwright minor release with implementation and independent end-to-end evidence. |
| Consumer `supported` to a weaker state | Next minor before Draftwright 1.0, otherwise Draftwright major, or a prior deprecation cycle; release notes and negative/fail-loud evidence. |
| Change `not-applicable` to an applicable state | Draftwright minor release plus rationale change and evidence; no package change unless geometry truth changed. |
| Increase either document `format_version` | New schema major; readers reject until explicitly upgraded. |

Package and consumer releases are asymmetric. For an additive family, Draftwright may first
release a declaration that accepts a named package prerelease/range, then the package releases,
then Draftwright adopts the immutable package artifact. For a breaking record change, introduce
an alias or dual-readable schema first whenever possible. The detailed landing, rollback, local
override, and automation protocol belongs to issues #24 and Draftwright #1170; this ADR defines
the compatibility facts that protocol must prove.

An alias contains `kind` (`family` or `record`), `old`, `replacement`, `deprecated_in`,
`remove_in`, and `rationale`. Readers normalize aliases before inventory comparison but report a
deprecation. Unknown aliases, alias cycles, reused names, and aliases whose removal version has
passed fail validation.

### Safe evolution of the document formats

Version 1 documents reject unknown required enum values and unknown top-level or capability
fields. A later format may add optional extension data only under a namespaced `extensions`
object; readers may ignore an extension only when its declaration says `required: false`.
Required unknown extensions fail. This prevents a permissive JSON parser from turning future
policy into accidental support.

## Demonstrated boundaries

The two examples above prove the schema can describe opposite valid outcomes without changing
recognition behavior:

- `bosses` shows a package record with a fully evidenced Draftwright path through adapter, DSL,
  generated code, drawing, completeness, and documentation.
- `repeating-radial-profiles` shows accepted geometry evidence that must not become inferred gear
  semantics. It can support critique while its IR/DSL/codegen/drawing stages remain explicitly
  not applicable.

Implementation issues #23 and Draftwright #1173 must replace illustrative consumer references
with independently verified current inventory. They must not alter recognition or regenerate
canonical goldens to make validation pass.

## Consequences

- A recogniser cannot become public without a stable family ID, record contract, evidence, and
  documentation.
- Draftwright cannot silently ignore a package family or keep a declaration whose implementation
  disappeared.
- Geometry-only evidence is a first-class, reviewed state rather than a hole in a checklist.
- The package remains reusable by consumers with completely different IR and policy.
- Cross-repository work requires explicit version/release coordination, but neither repository
  needs a sibling checkout or synchronized source commit.
- Schema and state changes become compatibility events with reviewable evidence.

## Alternatives considered

### Put Draftwright fields in the package manifest

Rejected. That would make a geometry library publish one consumer's IR and drawing policy and
would invert ADR 0001's dependency boundary.

### Infer downstream support from imports or converter registries

Rejected. Presence does not prove DSL, generated-code, drawing, or completeness behavior, and it
cannot distinguish geometry-only intent from unfinished work.

### Require every family to be fully consumed

Rejected. Recognition evidence such as repeating radial profiles can be valuable for critique
without justifying an inferred manufacturing or drafting feature.

### Ignore unknown families for forward compatibility

Rejected. Silent forward compatibility is precisely how downstream obligations drift. Explicit
prerelease/range coordination provides compatibility without pretending unknown semantics are
safe.

## F5 attribution metadata does not change format 1

The closed attribution disposition is private registry metadata and reviewed human capability
prose. It adds no field to `capabilities.json`, no public record/result field and no Draftwright pin
movement. Publishing machine-readable attribution requires a separately authorised format
transition under this ADR; unknown format-1 family fields remain rejected.

## Bounded explanation reason evolution (issue #304)

`ReconciliationReason` is a public closed projection of package-owned aggregate policy, but it is
not a feature family, record serialization schema or capability-manifest field. A new named
precedence rule therefore adds the same reason value to the private and public enums and requires
behavior evidence plus an exact parity guard between them. It does not advance a record schema or
manifest format. Consumers must not infer drafting semantics from the reason; they may display or
persist the new aggregate explanation value. Removing or changing a reason value remains a public
compatibility event.

## Free-axis Slot capability event (issue #310)

The successor records, entry points, aggregate fields, census key and reconciliation reason are
an additive capability, not a patch correction to axis-letter `Slot`. They begin the `0.5.0`
development line. Legacy principal Slot values remain unchanged; consumers opt in explicitly.
