from build123d import Box, Pos

from tests.golden._common import originated_here

PROVENANCE = originated_here("tests/test_through_steps.py")


def build_fixture():
    return Box(40, 30, 20) - Pos(15, 10, 0) * Box(20, 20, 30)
