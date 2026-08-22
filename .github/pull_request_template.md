## Scope and evidence

- [ ] The issue's positive, negative, golden, performance and provenance evidence is present.
- [ ] Recognition semantics/goldens are unchanged, or a separately approved behavior issue is linked.
- [ ] Public record, manifest, typing, documentation and archive boundaries were checked.

For any recogniser or record change, follow the tests-first
[`docs/delivery-protocol.md`][protocol]: record every downstream state and attach the
package/Draftwright compatibility and rollback evidence.

[protocol]: https://github.com/pzfreo/b123d-recognisers/blob/main/docs/delivery-protocol.md

## Verification

- [ ] Relevant tests, Ruff, mypy, coverage and deterministic/golden checks pass.
- [ ] The complete diff, CI, reviews, comments and unresolved threads were inspected.
- [ ] Versioning and release notes match the compatibility impact.
