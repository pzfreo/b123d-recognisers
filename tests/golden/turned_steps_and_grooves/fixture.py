from build123d import Cylinder, Pos

from tests.golden._common import provenance

PROVENANCE = provenance("tests/test_make_drawing.py")


def build_fixture():
    shaft = Cylinder(15, 70)
    shaft -= Pos(0, 0, 18) * (Cylinder(15, 5) - Cylinder(12, 5))
    shaft -= Pos(0, 0, 44) * (Cylinder(15, 4) - Cylinder(11, 4))
    return shaft
