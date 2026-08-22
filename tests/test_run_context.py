# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle

"""One run derives its shared state once, and both entry points derive it the same way.

`RecognitionRun` claims that the face graph, the face-edge memo and the cylinder scan are facts
about a run rather than about a recogniser, and are therefore derived once. Nothing about the
records a run reports would change if that claim were false — a second graph over the same solid
answers the same questions, more slowly — so a golden comparison cannot see it, and this is the
only place that can.

It is not a speculative property. Counting constructions is what found `recognise_polygonal_bosses`
building its own graph inside the aggregate: it had no parameter to receive the caller's, so every
run over a single solid resolved the same faces twice. The measurement caught it; no test did.

The multi-solid case is here to stop that fix going too far. Polygonal bosses look at each solid
separately on purpose, because a ring assembled from faces of two solids is not a boss — so on a
two-solid part the extra graphs are correct, and a future change that "optimised" them away would
be changing what is recognised.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from build123d import Axis, Box, Cylinder, GeomType, Pos, fillet

import b123d_recognisers as r
from b123d_recognisers import _adjacency, _cylinder_substrate
from b123d_recognisers.census import feature_census
from tests.golden._common import load_fixture

GOLDEN = Path(__file__).parent / "golden"


@pytest.fixture
def derivations(monkeypatch):
    """Count each shared derivation as it happens, wherever in the package it is asked for.

    Patched on the classes and on the module the aggregate imports from, rather than on each
    importing module: a recogniser that reaches for its own graph is exactly what this is
    looking for, and patching per-call-site would miss the one that does not go through a
    call site the test knows about.
    """

    counts = {"graph": 0, "edges": 0, "cylinders": 0}

    def counting(cls, key):
        original = cls.__init__

        def wrapper(self, *args, **kwargs):
            counts[key] += 1
            original(self, *args, **kwargs)

        monkeypatch.setattr(cls, "__init__", wrapper)

    counting(_adjacency.FaceGraph, "graph")
    counting(_adjacency.FaceEdges, "edges")

    scan = _cylinder_substrate.analyse_cylinders

    def counted_scan(*args, **kwargs):
        counts["cylinders"] += 1
        return scan(*args, **kwargs)

    # Every module holding a reference, not just the one that defines it. `from ... import
    # analyse_cylinders` binds the function into the importing module's namespace, so patching
    # the definition site alone would leave a rescanning recogniser invisible -- which is the
    # exact thing being counted.
    for module in list(sys.modules.values()):
        if getattr(module, "__name__", "").startswith("b123d_recognisers") and (
            getattr(module, "analyse_cylinders", None) is scan
        ):
            monkeypatch.setattr(module, "analyse_cylinders", counted_scan)
    return counts


def _golden(name):
    return load_fixture(GOLDEN / name / "fixture.py").build_fixture()


@pytest.mark.parametrize("name", ["simple_through_hole", "turned_steps_and_grooves"])
def test_the_aggregate_derives_each_shared_fact_once(derivations, name):
    """The property `RecognitionRun` exists to hold: one part, one graph, one memo, one scan."""

    r.build_recognition_result(_golden(name))
    assert derivations == {"graph": 1, "edges": 1, "cylinders": 1}


@pytest.mark.parametrize("name", ["simple_through_hole", "turned_steps_and_grooves"])
def test_the_census_derives_each_shared_fact_once(derivations, name):
    """And the census does not derive a second set of them, because it is the same inventory."""

    feature_census(_golden(name))
    assert derivations == {"graph": 1, "edges": 1, "cylinders": 1}


def test_a_radiused_groove_reuses_the_run_face_edge_memo(derivations):
    """The torus walk needs adjacency, but it still uses the run's one shared memo."""

    plain = Cylinder(15, 20) + Pos(0, 0, 12.5) * Cylinder(12, 5)
    plain += Pos(0, 0, 22.5) * Cylinder(15, 20)
    shoulder = plain.edges().filter_by(GeomType.CIRCLE).group_by(Axis.Z)[1]
    radiused = fillet(shoulder, 1.0)

    result = r.build_recognition_result(radiused, rotational=True)

    assert len(result.grooves) == 1
    assert derivations == {"graph": 1, "edges": 1, "cylinders": 1}


def test_an_injected_cylinder_scan_is_not_repeated(derivations):
    """A caller that has already paid for the scan hands it in and is not charged again."""

    part = _golden("simple_through_hole")
    scan = r.analyse_cylinders(part)
    before = derivations["cylinders"]
    r.build_recognition_result(part, cylinders=scan)
    assert derivations["cylinders"] == before


def test_a_multi_solid_part_still_gets_one_graph_per_solid(derivations):
    """The limit of the sharing, and it is a correctness limit rather than an oversight.

    `recognise_polygonal_bosses` examines each solid on its own so that a ring cannot be
    assembled from two of them. Handing it the whole-part graph there would be handing it the
    wrong inventory, so it builds its own per solid, and this pins that it still does.
    """

    two = Box(30, 30, 10) + Pos(60, 0, 0) * Box(30, 30, 10)
    assert len(two.solids()) == 2, "the point of the fixture"
    r.build_recognition_result(two)
    assert derivations["graph"] == 3, "the run's, plus one per solid for the boss scan"


def test_a_graph_over_the_wrong_solid_is_refused_rather_than_answered():
    """The one provenance link the sharing adds, and it is checked rather than trusted.

    A graph is not self-describing: handed one built over a different solid,
    `recognise_polygonal_bosses` would answer questions about the wrong faces and report a boss
    found on one part as belonging to another. There is no wrong number to notice afterwards,
    so the check is at the door — the same guard `_rings` applies to its own caller.
    """

    from b123d_recognisers._adjacency import FaceGraph

    hexagon = _golden("hexagonal_passage")
    with pytest.raises(ValueError):
        r.recognise_polygonal_bosses(hexagon, graph=FaceGraph(Box(30, 30, 10)))
