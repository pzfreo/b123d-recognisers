"""Shared construction helpers for synthetic golden fixtures."""

from __future__ import annotations

from math import cos, pi, sin

from build123d import Box, Cylinder, Polygon, Pos, RegularPolygon, extrude

PROVENANCE = {
    "creator": "Paul Fremantle",
    "source": "Synthetic build123d geometry created for b123d-recognisers epic #1",
    "license": "Apache-2.0",
}


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
