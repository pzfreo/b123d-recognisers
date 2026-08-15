from build123d import Box, Cone, Cylinder, Pos

from tests.golden._common import PROVENANCE as _PROVENANCE

PROVENANCE = dict(_PROVENANCE)


def build_fixture():
    part = Box(90, 50, 20)
    part -= Pos(-22, 0, 0) * Cylinder(4, 20)
    part -= Pos(-22, 0, 7) * Cylinder(8, 6)
    part -= Pos(22, 0, 0) * Cylinder(3, 20)
    part -= Pos(22, 0, 7) * Cone(3, 7, 6)
    return part
