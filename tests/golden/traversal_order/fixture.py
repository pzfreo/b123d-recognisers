from build123d import Box, Compound, Pos

from tests.golden._common import PROVENANCE as _PROVENANCE

PROVENANCE = dict(_PROVENANCE)


def _body():
    return Box(60, 30, 10) - Box(30, 8, 20)


def _compound(ys):
    body = _body()
    return Compound(children=[Pos(0, y, 0) * body for y in ys])


def build_fixture():
    return _compound((0, 60, 120))


def equivalent_fixtures():
    return {"reversed_children": _compound((120, 60, 0))}
