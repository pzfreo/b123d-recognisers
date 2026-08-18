from build123d import Box, Pos

from tests.golden._common import hex_prism, provenance

PROVENANCE = provenance("tests/test_issue_676_polygonal_boss.py")


def build_fixture():
    # The same hexagonal prism that test's boss fixture stands on the plate, cut through it
    # instead. A passage and a polygonal boss are bounded by the identical ring of walls; only
    # which side the material is on separates them, so the inverse of that fixture is the
    # sharpest thing to pin this family against.
    return Box(100, 80, 10) - Pos(0, 0, -10) * hex_prism(height=30)
