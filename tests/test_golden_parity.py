import importlib.util
import json
import sys
from pathlib import Path

import pytest

import b123d_recognisers as recognition
import b123d_recognisers.result as result_module
from b123d_recognisers import feature_census
from b123d_recognisers._candidates import FamilyId
from b123d_recognisers.levels import _StepLevelAttributionError

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


CASES = sorted(GOLDEN_ROOT.glob("*/fixture.py"))
TRAVERSAL_CASES = [path for path in CASES if path.parent.name == "traversal_order"]


@pytest.mark.parametrize("fixture_path", CASES, ids=lambda path: path.parent.name)
def test_package_matches_pinned_draftwright_semantic_golden(fixture_path):
    fixture = _load_fixture(fixture_path)
    expected = json.loads(fixture_path.with_name("expected.json").read_text(encoding="utf-8"))

    if fixture_path.parent.name == "chamfers_fillets_and_flats":
        # Its three independent solids intentionally share horizontal Z clusters. The public
        # geometry-only records remain unchanged, but #240 cannot truthfully attach one-body
        # evidence to that whole-part aggregate. Pin the named fail-closed boundary instead of
        # teaching the registry to catch/drop it or weakening the ownership contract.
        captured = []
        real_ledger = result_module.ClaimLedger

        def ledger(graph, **kwargs):
            value = real_ledger(graph, **kwargs)
            captured.append(value)
            return value

        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(result_module, "ClaimLedger", ledger)
            with pytest.raises(_StepLevelAttributionError, match="one valid solid"):
                recognition_snapshot(recognition, feature_census, fixture.build_fixture())
        assert len(captured) == 1
        assert captured[0].candidate_set(FamilyId.STEP_LEVELS).candidates == ()
        return

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
