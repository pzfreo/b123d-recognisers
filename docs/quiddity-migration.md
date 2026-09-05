# Migrating to Quiddity

Quiddity renames the distribution and import namespace of `b123d-recognisers`.
Recognition algorithms and record geometry are unchanged by the rename.
Quiddity 0.2.0 is the second alpha; the former package was the first alpha.
This starts Quiddity's own version history, not a downgrade of the old distribution.
All inherited capabilities therefore have `introduced_in: 0.2.0` in Quiddity's manifest.
Historical old-package versions remain unchanged. This release is not yet published.
GitHub releases use `quiddity-v0.2.0` (and the same prefix subsequently), because the old
package already has a `v0.2.0` tag. The Python package version is simply `0.2.0`.

After the first Quiddity release:

- Replace the `b123d-recognisers` dependency with `quiddity` and regenerate your lockfile.
- Replace `b123d_recognisers` imports with `quiddity`, including module-qualified imports.
- Replace the `b123d-recognisers-capabilities` command with `quiddity-capabilities`.
- Expect manifest package identity `quiddity` and qualified Python names beginning `quiddity.`.

For example:

```python
from quiddity import build_section_recess_document, import_step_geometry

part = import_step_geometry("part.step")
document = build_section_recess_document(part)
```

There is no forwarding package or old-namespace alias. Existing released
`b123d-recognisers` versions remain available; installing Quiddity does not upgrade or
uninstall them. Avoid passing runtime objects between the two installed namespaces.
Serialized Python module paths and pickles require consumer migration; the supported JSON
approach is preferred for interchange.

JSON geometry schemas and schema version numbers stay unchanged. The public manifest identifiers
change along with the package identity:

| Old format | New format |
| --- | --- |
| `b123d-recognisers-capabilities` | `quiddity-capabilities` |
| `b123d-recognisers-evidence-api` | `quiddity-evidence-api` |
| `b123d-recognisers-inspection-api` | `quiddity-inspection-api` |

Consumers must update format-name checks, namespace checks and package-name checks together.
The SectionRecess JSON document has no package-branded format identifier to rename.
The SectionRecess migration in 0.4.15 remains a separate API change; see
[the recess migration guide](section-recess-migration.md).

The repository URL remains `https://github.com/pzfreo/b123d-recognisers`.
Historical reports, release notes and ADRs retain their original package terminology.
Before merging, configure pending trusted publishers for `quiddity` on TestPyPI and PyPI
as documented in [releasing](releasing.md). A public project lookup returning 404 does not
guarantee that either index will accept the name.

## Draftwright validation checklist

- Test the rename branch in an isolated development environment; do not merge a mutable
  branch/path dependency into production.
- Update dependency, imports, capability command, manifest identities and format checks.
- Run existing capability, recognition-to-IR, drawing and serialization tests. Geometry and
  recognition results should not need new expectations merely because the package was renamed.
- After Quiddity is published, pin its exact stable version and regenerate artifact hashes.
- Keep rollback to the previous old-name dependency/lockfile available.

## Old-package retirement

Only after Quiddity is published and verified, prepare `b123d-recognisers 0.4.16` from the
0.4.15 release line, keeping its runtime code unchanged. Add a prominent rename notice and
migration link in its distribution README/release notes. Do not build this old-name release
from the Quiddity source tree or replace it with a dependency-only placeholder.
Keep all existing releases and project ownership; do not delete or yank old releases.
The new project's trusted-publisher configuration does not replace the old project's publisher.
Keep old-name updates on that maintenance branch. Its release workflow must not run the
current unconditional post-release bump of main: main belongs to Quiddity after the rename.
Isolate or disable that bump on the old release line before publishing an old-name update.

## Old-name audit exceptions

The old name remains only for repository URLs, migration instructions, historical ADRs/reports,
release history and provenance, and frozen development audit/taxonomy format identifiers.
Those audit identifiers and deterministic selection namespaces must not be rewritten: they
identify previously published evidence and selections, not the public runtime package.
The build123d dependency keeps its actual name. No old-name runtime namespace is shipped.
