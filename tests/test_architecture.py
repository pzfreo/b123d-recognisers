# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

import ast
from pathlib import Path

import b123d_recognisers as recognition

ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "src" / "b123d_recognisers"


def test_runtime_package_does_not_import_draftwright():
    violations = []
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            if any(name == "draftwright" or name.startswith("draftwright.") for name in names):
                violations.append(f"{path.name}:{node.lineno}")
    assert violations == []


def test_every_defined_public_recogniser_is_exported_and_snapshotted():
    defined = set()
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        defined.update(
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name.startswith("recognise_")
        )

    exported = {name for name in recognition.__all__ if name.startswith("recognise_")}
    assert exported == defined
