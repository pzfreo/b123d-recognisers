from math import cos, radians, sin

from build123d import Box, Cylinder, Plane

from tests.golden._common import provenance

PROVENANCE = provenance("tests/test_recognition.py")


def build_fixture():
    angle = radians(45)
    plane = Plane(origin=(0, 0, 0), z_dir=(sin(angle), 0, cos(angle)))
    return Box(60, 60, 20) - (plane * Cylinder(5, 80)) - (plane.offset(8) * Cylinder(9, 30))
