#!/usr/bin/env python3
"""Export the experimental ADR-0019 section-recess JSON for one STEP file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from b123d_recognisers import import_step_geometry  # noqa: E402
from b123d_recognisers._section_recess_prototype import (  # noqa: E402
    build_section_recess_prototype,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", type=Path, help="STEP file to recognise")
    parser.add_argument("--output", "-o", type=Path, help="write JSON here instead of stdout")
    args = parser.parse_args()

    document = build_section_recess_prototype(import_step_geometry(args.step))
    encoded = json.dumps(document.to_dict(), indent=2, sort_keys=True) + "\n"
    if args.output is None:
        sys.stdout.write(encoded)
    else:
        args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
