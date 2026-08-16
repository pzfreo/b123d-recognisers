"""Shared construction helpers for synthetic golden fixtures."""

from __future__ import annotations

import importlib.util
from math import cos, pi, sin

from build123d import Box, Cylinder, Polygon, Pos, RegularPolygon, extrude

SOURCE_COMMIT = "3fe20b0f71a71deced06b310943dd44cc66e355e"


def provenance(source_path: str) -> dict[str, str]:
    """Record the exact relicensed Draftwright test source adapted by a fixture."""

    return {
        "creator": "Paul Fremantle",
        "source_repository": "https://github.com/pzfreo/draftwright.git",
        "source_commit": SOURCE_COMMIT,
        "source_path": source_path,
        "license": "Apache-2.0",
    }


def load_fixture(path):
    """Import a golden ``fixture.py`` by path, without adding it to ``sys.modules``."""

    spec = importlib.util.spec_from_file_location(f"golden_fixture_{path.parent.name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def obround_tool(length: float, width: float, height: float):
    straight = length - width
    return (
        Box(straight, width, height)
        + Pos(straight / 2, 0, 0) * Cylinder(width / 2, height)
        + Pos(-straight / 2, 0, 0) * Cylinder(width / 2, height)
    )


def hex_prism(radius: float = 20, height: float = 30):
    return extrude(RegularPolygon(radius, 6), height)


def toothed_prism(repeats: int = 8, inner_radius: float = 16, outer_radius: float = 20):
    points = []
    for index in range(2 * repeats):
        angle = 2 * pi * index / (2 * repeats)
        radius = outer_radius if index % 2 == 0 else inner_radius
        points.append((radius * cos(angle), radius * sin(angle)))
    return extrude(Polygon(*points), 10)
