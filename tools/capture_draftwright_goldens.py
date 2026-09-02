#!/usr/bin/env python3
"""Capture canonical semantic goldens from the pinned Draftwright baseline."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

from golden_support import CANONICALIZER_VERSION, canonicalize, write_canonical
from recognition_snapshot import recognition_snapshot
from verify_source_baseline import DEFAULT_MANIFEST, BaselineError, verify

ROOT = Path(__file__).parents[1]
GOLDEN_ROOT = ROOT / "tests" / "golden"


def _load_fixture(path: Path):
    module_name = f"b123d_recognisers_golden_{path.parent.name}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load fixture {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _recognise(part):
    import draftwright.recognition as recognition
    from draftwright.score import feature_census

    return recognition_snapshot(recognition, feature_census, part)


def capture(draftwright: Path, manifest_path: Path, *, overwrite: bool) -> list[Path]:
    verify(draftwright, manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(draftwright / "src"))

    fixture_paths = [
        path
        for path in sorted(GOLDEN_ROOT.glob("*/fixture.py"))
        if getattr(_load_fixture(path), "LEGACY_SNAPSHOT", True)
    ]
    outputs = [path.with_name("expected.json") for path in fixture_paths]
    if not overwrite:
        existing = [path for path in outputs if path.exists()]
        if existing:
            raise FileExistsError(
                f"refusing to overwrite {existing[0]}; pass --overwrite to replace reviewed data"
            )

    pending = []
    for fixture_path, output in zip(fixture_paths, outputs, strict=True):
        fixture = _load_fixture(fixture_path)
        recognition = _recognise(fixture.build_fixture())
        if hasattr(fixture, "equivalent_fixtures"):
            expected = canonicalize(recognition)
            for name, variant in fixture.equivalent_fixtures().items():
                if canonicalize(_recognise(variant)) != expected:
                    raise RuntimeError(
                        f"{fixture_path.parent.name} variant {name!r} changed semantic recognition"
                    )
        payload = {
            "canonicalizer_version": CANONICALIZER_VERSION,
            "fixture": fixture_path.parent.name,
            "provenance": fixture.PROVENANCE,
            "source": {
                "repository": manifest["source"]["repository"],
                "commit": manifest["source"]["commit"],
            },
            "recognition": recognition,
        }
        pending.append((output, payload))

    for output, payload in pending:
        write_canonical(output, payload, overwrite=overwrite)
    return outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draftwright", required=True, type=Path)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    manifest_path = args.manifest.resolve()
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected_commit = manifest["source"]["commit"]
        if args.commit != expected_commit:
            raise BaselineError(f"--commit is {args.commit}, expected {expected_commit}")
        paths = capture(args.draftwright.resolve(), manifest_path, overwrite=args.overwrite)
    except (BaselineError, FileExistsError, OSError, ValueError, KeyError) as error:
        print(f"golden capture failed: {error}", file=sys.stderr)
        return 1
    print(f"captured {len(paths)} canonical Draftwright goldens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
