#!/usr/bin/env python3
"""Reproducible F7 spike benchmark: direct private seams versus the facade."""

from __future__ import annotations

import argparse
import json
import math
import resource
import statistics
import time

from build123d import Axis, Box, Pos, RegularPolygon, extrude, fillet
from OCP.BRepAdaptor import BRepAdaptor_Surface

from b123d_recognisers._adjacency import FaceGraph
from b123d_recognisers._blend_view import BlendCollapseIndex
from b123d_recognisers._effective_surfaces import EffectiveSurfaceIndex
from b123d_recognisers.experimental_geometry import AnalyticSurface, GeometryGraph, inspect_face
from b123d_recognisers.fillets import fillet_anchor


def _blend_part():
    prism = extrude(RegularPolygon(20, 6), 30)
    vertical = [edge for edge in prism.edges() if abs(float(edge.tangent_at().Z)) > 0.99]
    return Box(100, 80, 10) + Pos(0, 0, 5) * fillet(vertical, 2)


def _fillet_face():
    part = fillet(Box(60, 40, 30).edges().filter_by(Axis.Z).sort_by(Axis.X)[-1], 5)
    return next(face for face in part.faces() if face.geom_type.name == "CYLINDER")


def _direct_blend(part) -> tuple[int, int]:
    graph = FaceGraph(part)
    surfaces = EffectiveSurfaceIndex(graph)
    index = BlendCollapseIndex(graph, surfaces)
    chains = index.chains()
    view = index.view(chains)
    nodes = view.logical_nodes()
    provenance = [
        view.expand_arc(arc)
        for at, left in enumerate(nodes)
        for right in nodes[at + 1 :]
        for arc in view.arcs_between(left, right)
        if arc.synthetic
    ]
    return len(chains), sum(len(item.arcs) for item in provenance)


def _facade_blend(part) -> tuple[int, int]:
    graph = GeometryGraph(part)
    chains = graph.blend_facts()
    bridges = graph.collapsed_bridges(tuple(chain.ref for chain in chains))
    return len(chains), sum(len(bridge.provenance.boundary) for bridge in bridges)


def _direct_fillet(face) -> tuple[float, tuple[float, float, float]]:
    surface = BRepAdaptor_Surface(face.wrapped)
    return float(surface.Cylinder().Radius()), fillet_anchor(surface)


def _facade_fillet(face) -> tuple[float, tuple[float, float, float]]:
    inspection = inspect_face(face)
    fact = inspection.surface
    assert isinstance(fact, AnalyticSurface)
    assert inspection.anchor is not None
    return fact.parameters[6], inspection.anchor


def _run(name: str, iterations: int) -> dict[str, float | str]:
    part = _blend_part()
    face = _fillet_face()
    operation = {
        "direct-blend": lambda: _direct_blend(part),
        "facade-blend": lambda: _facade_blend(part),
        "direct-fillet": lambda: _direct_fillet(face),
        "facade-fillet": lambda: _facade_fillet(face),
    }[name]
    operation()
    samples = []
    for _ in range(7):
        started = time.perf_counter()
        for _ in range(iterations):
            operation()
        samples.append((time.perf_counter() - started) / iterations)
    rss = float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return {
        "mode": name,
        "median_seconds": statistics.median(samples),
        "peak_rss_kib": rss,
        "samples": len(samples),
        "iterations_per_sample": iterations,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "mode", choices=("direct-blend", "facade-blend", "direct-fillet", "facade-fillet")
    )
    parser.add_argument("--iterations", type=int, default=3)
    args = parser.parse_args()
    if args.iterations <= 0 or not math.isfinite(float(args.iterations)):
        raise SystemExit("--iterations must be positive")
    print(json.dumps(_run(args.mode, args.iterations), sort_keys=True))


if __name__ == "__main__":
    main()
