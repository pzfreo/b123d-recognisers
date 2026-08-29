from build123d import Box, Cylinder, Pos, Rot

from tests.golden._common import originated_here

PROVENANCE = originated_here("tests/test_circular_blind_steps.py")


def build_fixture():
    stock = Box(40, 30, 20)
    cutter = Pos(7.5, 15, 10) * Rot(0, 90, 0) * Cylinder(4, 25)
    return stock - cutter
