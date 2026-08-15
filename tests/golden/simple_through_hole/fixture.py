from build123d import Box, Cylinder, Pos

from tests.golden._common import PROVENANCE as _PROVENANCE

PROVENANCE = dict(_PROVENANCE)


def build_fixture():
    return Box(60, 50, 10) - Pos(-12, 0, 0) * Cylinder(4, 10) + Pos(15, 0, 9) * Cylinder(8, 8)
