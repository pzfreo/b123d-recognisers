from build123d import Align, Box, BuildPart, BuildSketch, Plane, Polygon, Pos, Rot, extrude

from tests.golden._common import provenance

PROVENANCE = provenance("tests/test_slanted_blind_step.py")


def build_fixture():
    # Adapted from that test's `bounded_slanted_recess` -- "a partial-width ramp whose ends
    # are defining profile transitions". Its profile is a quadrilateral, which closes the
    # ramp's blind ends with quads; taking the ramp all the way to the corner makes them
    # triangles, which is what distinguishes an angled blind step from a chamfer.
    align_min = (Align.MIN, Align.MIN, Align.MIN)
    base = Box(50, 50, 25, align=align_min)
    with BuildPart() as ramp:
        with BuildSketch(Plane.XZ):
            Polygon((0, 15), (15, 25), (0, 25))
        extrude(amount=12)
    # A full-length 45 degrees bevel on the far top edge, so the fixture pins the *boundary*
    # between the two families rather than just the new one: both must appear, on the same
    # part, each claimed by exactly one recogniser.
    edge_break = Pos(25, 50, 25) * Rot(45, 0, 0) * Box(60, 4.243, 4.243)
    return base - Pos(0, 12, 0) * ramp.part - edge_break
