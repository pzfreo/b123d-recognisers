import importlib.util
import json
import sys
from pathlib import Path

import pytest

import quiddity as recognition
from quiddity import feature_census

ROOT = Path(__file__).parents[1]
GOLDEN_ROOT = ROOT / "tests" / "golden"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from golden_support import canonicalize  # noqa: E402
from recognition_snapshot import recognition_snapshot  # noqa: E402


def _load_fixture(path):
    spec = importlib.util.spec_from_file_location(f"parity_fixture_{path.parent.name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Only pinned Draftwright snapshots carry ``expected.json``. Package-originated semantic
# contracts share the executable fixture corpus but have their own contract test and schema.
CASES = sorted(
    path for path in GOLDEN_ROOT.glob("*/fixture.py") if path.with_name("expected.json").is_file()
)
TRAVERSAL_CASES = [path for path in CASES if path.parent.name == "traversal_order"]


@pytest.mark.parametrize("fixture_path", CASES, ids=lambda path: path.parent.name)
def test_package_matches_pinned_draftwright_semantic_golden(fixture_path):
    fixture = _load_fixture(fixture_path)
    expected = json.loads(fixture_path.with_name("expected.json").read_text(encoding="utf-8"))

    actual = recognition_snapshot(recognition, feature_census, fixture.build_fixture())

    assert canonicalize(actual) == expected["recognition"]


@pytest.mark.parametrize("fixture_path", TRAVERSAL_CASES, ids=lambda path: path.parent.name)
def test_equivalent_topology_traversals_produce_the_same_snapshot(fixture_path):
    fixture = _load_fixture(fixture_path)
    variants = getattr(fixture, "equivalent_fixtures", lambda: {})()
    assert variants

    baseline = canonicalize(
        recognition_snapshot(recognition, feature_census, fixture.build_fixture())
    )
    for name, part in variants.items():
        assert canonicalize(recognition_snapshot(recognition, feature_census, part)) == baseline, (
            name
        )
