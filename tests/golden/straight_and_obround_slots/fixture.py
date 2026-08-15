from build123d import Box, Pos

from tests.golden._common import obround_tool, provenance

PROVENANCE = provenance("tests/test_slot_pattern_recognition.py")


def build_fixture():
    part = Box(130, 150, 16)
    for y in (-48, -16, 16, 48):
        part -= Pos(-32, y, 0) * Box(30, 8, 16)
    part -= Pos(32, 0, 0) * obround_tool(34, 10, 16)
    return part
