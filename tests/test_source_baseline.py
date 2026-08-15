import json
import re
from pathlib import Path

ROOT = Path(__file__).parents[1]
MANIFEST = ROOT / "migration" / "source-baseline.json"
SHA1 = re.compile(r"[0-9a-f]{40}")


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_source_baseline_is_an_immutable_clean_commit_inventory():
    manifest = _manifest()

    assert manifest["schema_version"] == 1
    assert manifest["source"]["repository"] == "https://github.com/pzfreo/draftwright.git"
    assert SHA1.fullmatch(manifest["source"]["commit"])
    assert "clean" in manifest["source"]["selection"].lower()

    sources = manifest["sources"]
    paths = [source["path"] for source in sources]
    assert len(paths) == len(set(paths))
    assert all(SHA1.fullmatch(source["blob"]) for source in sources)
    assert {source["origin"] for source in sources} <= {
        "draftwright",
        "build123d-drafting-helpers-and-draftwright",
    }


def test_source_baseline_covers_the_whole_recognition_package_and_census_boundary():
    paths = {source["path"] for source in _manifest()["sources"]}

    assert paths == {
        "src/draftwright/_geometry.py",
        "src/draftwright/recognition/__init__.py",
        "src/draftwright/recognition/_features.py",
        "src/draftwright/recognition/_record.py",
        "src/draftwright/recognition/chamfers.py",
        "src/draftwright/recognition/countersinks.py",
        "src/draftwright/recognition/fillets.py",
        "src/draftwright/recognition/flats.py",
        "src/draftwright/recognition/grooves.py",
        "src/draftwright/recognition/levels.py",
        "src/draftwright/recognition/pads.py",
        "src/draftwright/recognition/plates.py",
        "src/draftwright/recognition/polygonal_bosses.py",
        "src/draftwright/recognition/profiled_bores.py",
        "src/draftwright/recognition/repeating_profiles.py",
        "src/draftwright/recognition/result.py",
        "src/draftwright/recognition/slots.py",
        "src/draftwright/recognition/turned.py",
        "src/draftwright/score.py",
    }


def test_source_baseline_records_relicensing_and_keeps_consumer_cache_out():
    manifest = _manifest()

    assert manifest["licensing"] == {
        "copyright_owner": "Paul Fremantle",
        "copyright_years": "2024-2026",
        "relicense": "Apache-2.0",
        "grant": "Relicensed for this extraction by the copyright owner",
        "derived_notice": (
            "The initial hole, boss, cylinder and pattern implementation in _features.py was "
            "derived from the Apache-2.0 build123d-drafting-helpers project and remains "
            "identified in NOTICE."
        ),
    }
    assert manifest["excluded"] == [
        {
            "name": "RecognitionCache",
            "reason": (
                "Consumer build and lint lifecycle state remains owned by Draftwright under "
                "ADR 0001."
            ),
        }
    ]
