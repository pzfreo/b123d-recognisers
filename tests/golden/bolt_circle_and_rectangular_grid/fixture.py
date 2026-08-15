from math import cos, pi, sin

from build123d import Box, Cylinder, Pos

from tests.golden._common import provenance

PROVENANCE = provenance("tests/test_recognition.py")


def build_fixture():
    part = Box(180, 100, 10)
    for index in range(6):
        angle = 2 * pi * index / 6
        part -= Pos(-50 + 25 * cos(angle), 25 * sin(angle), 0) * Cylinder(3, 10)
    for x in (35, 55, 75):
        for y in (-18, 18):
            part -= Pos(x, y, 0) * Cylinder(2.5, 10)
    return part
