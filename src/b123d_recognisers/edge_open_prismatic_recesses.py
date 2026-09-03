# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Edge-open prismatic recess records and recognition."""

from __future__ import annotations

import math
from dataclasses import dataclass

from b123d_recognisers._record import Record

_AXES = "xyz"
_EPS = 1e-9


def _point(value: object, *, name: str) -> tuple[float, float]:
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or any(isinstance(item, bool) or not isinstance(item, int | float) for item in value)
    ):
        raise ValueError(f"{name} must be a pair of finite numbers")
    result = (float(value[0]), float(value[1]))
    if not all(math.isfinite(item) for item in result):
        raise ValueError(f"{name} must be a pair of finite numbers")
    if any(round(item, 4) != item for item in result):
        raise ValueError(f"{name} must serialize exactly at four decimal places")
    return tuple(0.0 if item == 0.0 else item for item in result)  # type: ignore[return-value]


def _turn(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _crosses(
    first: tuple[tuple[float, float], tuple[float, float]],
    second: tuple[tuple[float, float], tuple[float, float]],
) -> bool:
    a, b = first
    c, d = second
    return _turn(a, b, c) * _turn(a, b, d) <= _EPS and _turn(c, d, a) * _turn(c, d, b) <= _EPS


def _validate_simple(chain: tuple[tuple[float, float], ...]) -> None:
    edges = tuple(zip(chain, (*chain[1:], chain[0]), strict=True))
    for index, edge in enumerate(edges):
        for other_index in range(index + 1, len(edges)):
            adjacent = other_index == index + 1 or (index == 0 and other_index == len(edges) - 1)
            if not adjacent and _crosses(edge, edges[other_index]):
                raise ValueError("wall chain and opening must bound a simple profile")


@dataclass(frozen=True, order=True, slots=True)
class OpenSectionOpening(Record):
    """The non-material side joining the endpoints of an open wall chain."""

    start: tuple[float, float]
    end: tuple[float, float]

    def __post_init__(self) -> None:
        start = _point(self.start, name="opening start")
        end = _point(self.end, name="opening end")
        if math.dist(start, end) <= _EPS:
            raise ValueError("opening endpoints must be distinct")
        object.__setattr__(self, "start", start)
        object.__setattr__(self, "end", end)


@dataclass(frozen=True, order=True, slots=True)
class OpenPolygonalSection(Record):
    """A canonical physical wall chain plus its explicit non-wall opening side."""

    wall_chain: tuple[tuple[float, float], ...]
    opening: OpenSectionOpening

    def __post_init__(self) -> None:
        if not isinstance(self.wall_chain, tuple):
            raise ValueError("wall_chain must be a tuple")
        chain = tuple(_point(point, name="wall-chain point") for point in self.wall_chain)
        if len(chain) < 4:
            raise ValueError("an open polygonal section needs at least three wall segments")
        if any(
            math.dist(chain[index], chain[index + 1]) <= _EPS for index in range(len(chain) - 1)
        ):
            raise ValueError("adjacent wall-chain points must be distinct")
        _validate_simple(chain)
        if not isinstance(self.opening, OpenSectionOpening) or (
            self.opening.start,
            self.opening.end,
        ) != (chain[-1], chain[0]):
            raise ValueError("opening must run from the wall-chain end to its start")
        reverse = tuple(reversed(chain))
        if reverse < chain:
            raise ValueError("wall_chain must use its canonical direction")
        object.__setattr__(self, "wall_chain", chain)


@dataclass(frozen=True, order=True, slots=True)
class EdgeOpenPrismaticRecess(Record):
    """A blind prismatic recess with one physical side open to the stock exterior."""

    axis: str
    run_interval: tuple[float, float]
    open_sign: int
    section: OpenPolygonalSection

    def __post_init__(self) -> None:
        if self.axis not in _AXES:
            raise ValueError("axis must be 'x', 'y', or 'z'")
        if (
            not isinstance(self.run_interval, tuple)
            or len(self.run_interval) != 2
            or any(
                isinstance(item, bool) or not isinstance(item, int | float)
                for item in self.run_interval
            )
        ):
            raise ValueError("run_interval must be a pair of finite numbers")
        interval = (float(self.run_interval[0]), float(self.run_interval[1]))
        if not all(math.isfinite(item) for item in interval) or interval[1] - interval[0] <= _EPS:
            raise ValueError("run_interval must be finite and strictly increasing")
        if any(round(item, 3) != item for item in interval):
            raise ValueError("run_interval must serialize exactly at three decimal places")
        if self.open_sign not in (-1, 1):
            raise ValueError("open_sign must be -1 or 1")
        if not isinstance(self.section, OpenPolygonalSection):
            raise ValueError("section must be an OpenPolygonalSection")
        object.__setattr__(self, "run_interval", interval)
