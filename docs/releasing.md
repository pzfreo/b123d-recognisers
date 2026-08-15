# Releasing

Release distributions move through one promotion path:

1. Build and test the wheel and sdist locally.
2. Create a GitHub release whose tag is `v` followed by the package version and attach exactly
   one wheel and one sdist.
3. Run **Publish distributions** with that tag and target `testpypi`. The workflow verifies
   the embedded versions, publishes the attached artifacts to TestPyPI, and installs/imports
   the package from TestPyPI.
4. Rerun the workflow with target `both`. TestPyPI safely skips the already-published files,
   repeats the install check, and the protected `pypi` environment then requires approval
   before those same workflow artifacts reach PyPI.

Publishing uses PyPI Trusted Publishing (GitHub OIDC), never repository API-token secrets.
The one-time pending-publisher records on the two indexes must be:

| Index | Project | Owner | Repository | Workflow | Environment |
| --- | --- | --- | --- | --- | --- |
| TestPyPI | `b123d-recognisers` | `pzfreo` | `b123d-recognisers` | `publish.yml` | `testpypi` |
| PyPI | `b123d-recognisers` | `pzfreo` | `b123d-recognisers` | `publish.yml` | `pypi` |

TestPyPI and PyPI accounts and publisher registrations are independent. Protect the GitHub
`pypi` environment with required reviewer approval; `testpypi` does not need approval. A
normal future GitHub release automatically follows the same TestPyPI-first path and pauses at
the production environment gate.

GitHub release assets are the reviewed artifacts and are promoted without rebuilding. The
workflow rejects missing, duplicate, malformed, wrong-project, and tag/version-mismatched
distributions before requesting either index credential.
