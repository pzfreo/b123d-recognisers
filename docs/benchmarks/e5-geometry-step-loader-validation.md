# E5 geometry-only STEP-loader validation

Issue #421 changes only how repository corpus tools load STEP geometry. It bypasses the XCAF
metadata traversal used by `build123d.import_step`, because an absent component-name attribute can
terminate the Python process before recognition begins. Recognition records, face identity,
ownership, reconciliation, and scoring are unchanged.

## Public crash reproduction

The public NIST MBE PMI STEP archive linked from the
[NIST PMI STEP-file page](https://www.nist.gov/document/nist-pmi-step-files) was downloaded and
tested at implementation commit `85e473bdb91265911d72d5baf974dbaf0bd3be6b`.

- archive SHA-256: `8fa78429e6d8d9b0d7681d223b6aa9ec98c3772185c55b1a0e3679b21c181911`;
- `nist_ctc_02_asme1_ap242-e2.stp` SHA-256:
  `99a0a2079ddeb64d05c2432cbe931fa17c89da60d8b0bcb0b11bd0ed94fa2e68`;
- `build123d.import_step` exited by `SIGSEGV` (`-11` from Python's subprocess API, `139` from the
  shell);
- `import_step_geometry` returned a compound containing 637 faces and one solid, after which the
  production feature census completed and returned 155 records.

The crash fixture is not copied into this repository. The regression suite instead proves that
the public loader never calls the unsafe XCAF importer, while the public, hash-identified NIST
model supplies reproducible process-level evidence for the dependency fault itself.

## Import equivalence controls

All 17 AP242 files in that NIST archive were evaluated in isolated subprocesses. Fifteen usable
files loaded through both paths with identical returned shape type, solid count, face count, and
SHA-256 of the ordered face signatures `(geometry type, area, centre)`. CTC-02 crashed only the
metadata importer and loaded through the geometry reader as described above.

The remaining file, `nist_ftc_08_asme1_ap242-e1-tg.stp`, returned the same compound, one solid,
and 273 faces through both readers. Its transferred faces have null surfaces under both paths, so
neither reader can construct the geometric signature or run recognition. It is therefore not a
loader regression and is excluded from the 15 comparable controls.

A generated two-solid STEP compound is also a permanent test fixture: both loaders return two
solids and the same ordered face signatures. This proves that flattening STEP product structure
does not collapse the solid boundaries used by body-local ownership.

## MFCAD++ functional control

The lexical first 500 models of the published MFCAD++ test split were evaluated in raw coordinates
with taxonomy v10:

```bash
uv run python tools/run_effectiveness_baseline.py \
  mfcadpp /app/workspaces-codex/datasets/mfcadpp/MFCAD++_dataset/step/test \
  --dataset-version \
  'MFCAD++ published test split; DOI 10.17034/d1fec5a0-8c10-4630-b02e-b92dc81df823' \
  --taxonomy docs/benchmarks/effectiveness-taxonomy-v10.json \
  --limit 500 --recognition-frame raw --allow-invalid \
  --output /tmp/effectiveness-mfcadpp-500-loader-85e473b.json
```

All 500 selected models were evaluated, with no invalid or empty rows. Against the canonical
[`effectiveness-mfcadpp-500-chamfer-af054c9.json`](effectiveness-mfcadpp-500-chamfer-af054c9.json)
report, every model's recognition result and the complete effectiveness summary are identical.
Only elapsed-time fields and expected source provenance differ. Runtime is not interpreted here;
performance is explicitly deferred to a later golden-result performance epic.

## Architecture review

The implementation follows ADR 0001 by keeping input transport separate from recognition
semantics, ADR 0005 by treating the new public function as a future minor-release addition, and
ADR 0007 by preserving body-local solids. ADR 0014 records the specific geometry-only loading
decision and its metadata trade-off. The final diff changes no recognition predicate or record
schema and publishes no release beyond v0.4.12. MFInstSeg is neither inspected nor required for
this loader-only change; exact MFCAD++ equivalence is the stronger functional gate.
