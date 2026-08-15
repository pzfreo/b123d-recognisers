import importlib.util
import sys
from pathlib import Path

from build123d import Shape

ROOT = Path(__file__).parents[1]
GOLDEN_ROOT = ROOT / "tests" / "golden"
sys.path.insert(0, str(ROOT))

EXPECTED_CASES = {
    "blind_pockets_and_pocket_patterns",
    "bolt_circle_and_rectangular_grid",
    "chamfers_fillets_and_flats",
    "counterbored_and_countersunk_holes",
    "double_d_bore",
    "interrupted_and_cross_bores",
    "open_channels",
    "plates_pads_levels_and_slanted_steps",
    "polygonal_boss",
    "polygonal_stock",
    "repeating_radial_profile",
    "simple_through_hole",
    "slanted_counterbore",
    "slanted_steps",
    "straight_and_obround_slots",
    "traversal_order",
    "turned_steps_and_grooves",
}


def _load(path):
    spec = importlib.util.spec_from_file_location(f"fixture_{path.parent.name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_complete_synthetic_fixture_corpus_is_executable_and_provenanced():
    fixture_paths = sorted(GOLDEN_ROOT.glob("*/fixture.py"))

    assert {path.parent.name for path in fixture_paths} == EXPECTED_CASES
    for path in fixture_paths:
        fixture = _load(path)
        assert fixture.PROVENANCE == {
            "creator": "Paul Fremantle",
            "source": "Synthetic build123d geometry created for b123d-recognisers epic #1",
            "license": "Apache-2.0",
        }
        shape = fixture.build_fixture()
        assert isinstance(shape, Shape)
        assert shape.is_valid
        for variant in getattr(fixture, "equivalent_fixtures", lambda: {})().values():
            assert isinstance(variant, Shape)
            assert variant.is_valid
