from build123d import Box, Cylinder

from tests.golden._common import PROVENANCE as _PROVENANCE

PROVENANCE = dict(_PROVENANCE)


def build_fixture():
    return Box(60, 60, 40) - Cylinder(5, 40) - Cylinder(3, 60, rotation=(0, 90, 0))
