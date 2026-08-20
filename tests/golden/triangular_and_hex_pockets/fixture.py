from build123d import Box, BuildPart, BuildSketch, Plane, Polygon, Pos, extrude

from tests.golden._common import hex_prism, originated_here

PROVENANCE = originated_here("tests/test_prismatic_pockets.py")


def build_fixture():
    # Two recesses the pairing pocket family cannot see and the ring family can, on one plate,
    # plus one it *can* see so the golden pins the overlap as well as the gap.
    #
    # A triangular recess has no two walls sharing a normal axis, so `recognise_pockets` forms
    # no candidate pair and never runs a gate -- measured at 0% recall on that class over 600
    # MFCAD++ models. A hexagonal one has two such pairs out of six walls and scores 4%. The
    # rectangular recess is found by both families, and the reconciler keeps the `Pocket`.
    with BuildPart() as triangle:
        with BuildSketch(Plane.XY):
            Polygon((-12, -9), (12, -9), (0, 12))
        extrude(amount=14)
    return (
        Box(120, 80, 20)
        - Pos(-35, 0, 2) * triangle.part
        - Pos(35, 0, 2) * hex_prism(height=14)
        - Pos(0, -28, 8) * Box(20, 12, 14)
    )
