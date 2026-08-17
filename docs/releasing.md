# Releasing

Between releases `main` carries a `.devN` version — `0.2.6.dev0` after 0.2.5 shipped. Every
push to `main` publishes a snapshot of it to TestPyPI, so the published path is exercised
continuously rather than only at a release.

A release is one GitHub release. The workflow builds the artifact itself, from the tagged
commit:

1. Make sure `RELEASE_NOTES.md` has a `## X.Y.Z` section for the version about to ship. The
   workflow refuses a tag without one, and it checks the *tag's* tree — so add it before
   tagging, not after.
2. Create a GitHub release whose tag is `v` followed by the version, with no `.dev` suffix
   (`v0.2.6` while `main` is on `0.2.6.dev0`). **Attach nothing.** The version is taken from
   the tag, so a prerelease is just `v0.2.6rc1` — see `docs/delivery-protocol.md`, which makes
   `0.2.NrcK` the paired prerelease Draftwright validates a new public record against.
3. That is all. `build-release` checks out the tag, strips the `.dev` suffix, builds the
   wheel and sdist, and verifies they match the tag. One artifact then goes to TestPyPI, is
   installed and imported from there, and only then reaches the protected `pypi` environment
   for approval.
4. When PyPI accepts it, the workflow opens a PR moving `main` to the next `.devN`. It
   dispatches CI against that branch explicitly, because a branch pushed with `GITHUB_TOKEN`
   raises no events and would otherwise arrive with no checks.

The published wheel is therefore a function of the tag and nothing else. It used to be built
on a maintainer's machine and attached to the release for the workflow to promote, which
could only check that the attached artifact's *version* matched the tag — something a wheel
built from a dirty tree also satisfies.

## One-time repository settings

Besides the Trusted Publishing records below, **Settings → Actions → General → Workflow
permissions → "Allow GitHub Actions to create and approve pull requests"** must be enabled.
It defaults to disabled, and without it the post-release bump fails at `gh pr create` — after
PyPI has already accepted the release, so the release itself is fine but `main` is left on the
old `.devN` until someone opens that PR by hand.

## Changing the minor or major version

`bump-version` only ever does patch + 1. To release `0.3.0`, open a PR first that moves
`main` to `0.3.0.dev0` using `scripts/update-recogniser-version`, then tag `v0.3.0`. Tagging
`v0.3.0` while `main` is on `0.2.x.devN` does not mispublish — `verify_release_assets.py`
rejects the mismatch before anything is uploaded — but it does fail the release.

## Moving the version by hand

`scripts/update-recogniser-version X.Y.Z[.devN]` is the only supported way. Four files hold
the version — `pyproject.toml`, `uv.lock`, `capabilities.json`'s `package.version`, and the
`PackageNotFoundError` fallback in `__init__.py` — and the script moves all four or restores
all four. Editing any of them by hand is how the fallback came to sit at 0.2.2 through both
the 0.2.3 and 0.2.4 releases.

## Trusted Publishing

Publishing uses PyPI Trusted Publishing (GitHub OIDC), never repository API-token secrets.
The one-time pending-publisher records on the two indexes must be:

| Index | Project | Owner | Repository | Workflow | Environment |
| --- | --- | --- | --- | --- | --- |
| TestPyPI | `b123d-recognisers` | `pzfreo` | `b123d-recognisers` | `publish.yml` | `testpypi` |
| PyPI | `b123d-recognisers` | `pzfreo` | `b123d-recognisers` | `publish.yml` | `pypi` |

TestPyPI and PyPI accounts and publisher registrations are independent. Protect the GitHub
`pypi` environment with required reviewer approval; `testpypi` does not need approval.
