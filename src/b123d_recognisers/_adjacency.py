# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Paul Fremantle
"""Internal face adjacency: which faces of a part meet along an edge.

Every recogniser that reasons about a face's surroundings needs this, and none owns it, so
it sits in ADR 0007's base layer — depending on nothing but the kernel and
:mod:`b123d_recognisers._geometry`'s thresholds, depended on by anything.

It was previously answered five separate ways: an edge→faces dict in ``_hole_features``, a
second one inline in ``fillets``, memoised pairwise closures in ``polygonal_bosses``, and
raw ``IsSame`` sweeps in ``chamfers`` and ``flats``. The line count of that duplication was
small; the risk was not, because nothing tested that five implementations of face identity
agreed. ``tests/test_adjacency.py`` now pins the one answer they share.

**Identity is build123d shape equality**, which is ``TShape`` plus ``Location`` and
orientation-insensitive — exactly the ``IsSame`` predicate the pairwise sweeps used, so
routing them through a dict is behaviour-preserving rather than merely equivalent-looking.
That equivalence is measured, not assumed: :func:`tests.test_adjacency` proves both
predicates induce the same partition of the edges *and* the faces of every pinned fixture.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TypeVar

from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Sphere
from OCP.gp import gp_Pnt, gp_Vec
from OCP.ShapeAnalysis import ShapeAnalysis_Surface
from OCP.TopAbs import TopAbs_EDGE, TopAbs_Orientation
from OCP.TopExp import TopExp_Explorer

from b123d_recognisers._geometry import AXIS_ALIGNED_COS, SMOOTH_ARC_COS
from b123d_recognisers._typing import EdgeLike, FaceLike

_T = TypeVar("_T")


class FaceEdges:
    """Per-face edge lists, computed once and shared for the length of one recognition run.

    ``Face.edges()`` is the single most expensive derived query the suite makes — measured at
    24% of a full :func:`b123d_recognisers.census.feature_census` over the pinned corpus, at
    ~107 µs a call — and every recogniser asks it of the same faces of the same part.

    **The sharing has to cross recogniser boundaries to pay.** Memoising within one
    recogniser call is worth about 2% and is a net loss for several of them; sharing one memo
    across a whole census is worth about 20%. That asymmetry is the whole reason this is a
    threaded parameter rather than a detail each recogniser could keep to itself, and it is
    why ``part.faces()`` sharing — the obvious candidate — is not the answer: re-walking the
    part's faces is only 1.9% of a census, because the walk is cheap and the *derivation*
    hanging off each face is not.

    Keyed on the face itself. build123d shape equality is ``TShape`` + ``Location``, i.e.
    ``IsSame``, proven over every fixture in :mod:`tests.test_adjacency` — so two wrappers for
    the same face, from two different ``part.faces()`` calls in two different recognisers, hit
    the same entry. That proof is what makes this safe; without it the memo would silently
    miss and quietly cost more than it saved.

    Scope it to a single run over a single part. It holds its faces alive, and it must not
    outlive geometry that could be rebuilt.

    The returned list is the memo's own, not a copy: **callers must not mutate it.** Every
    call site either iterates it or derives a new list with ``filter_by``/``sorted``.
    """

    def __init__(self) -> None:
        self._of: dict = {}

    def of(self, face: FaceLike) -> list[EdgeLike]:
        """The edges of *face*, computed on first ask and reused thereafter."""

        edges = self._of.get(face)
        if edges is None:
            self._of[face] = edges = face.edges()
        return edges


@dataclass(frozen=True, eq=False, slots=True)
class FaceNode:
    """A node of one :class:`FaceGraph`, and of no other.

    A bare integer would have carried no provenance: node 0 of one part is a perfectly valid
    index into another, so a node from the wrong graph would have been accepted and silently
    addressed the wrong face -- the accidental identity this substrate exists to remove. These
    are created only by the graph that owns them and compared by identity, so a foreign node is
    rejected rather than misread.

    Frozen, because a writable ``index`` would let a caller invalidate a handle the graph had
    issued -- ``owns`` would then refuse a node that genuinely came from this graph. ``eq=False``
    keeps comparison by identity, which is the whole mechanism.

    Opaque by design. ``index`` is a position in one part's face list, exposed because the graph
    itself needs it; nothing outside this module should read it, and it means nothing once the
    part changes.
    """

    index: int


class FaceGraph:
    """One node per face of one part, for the length of one recognition run.

    Seven modules privately re-derive the same handful of things about a face: its bounding
    box (six of them), its surface type (five), its normal (three), its edges, and which faces
    it meets. The derivations are duplicated, the caches are not shared, and two recognisers
    that disagree about a face have no way to say so except by comparing coordinates. This is
    the node half of that: one place where a face's attributes are derived, once.

    **What it deliberately is not.** Not a persistent identity -- node ids are positions in
    this part's face list and mean nothing outside this object. Not a public schema: no record
    gains a field. Not sampled UV geometry or anything a learned recogniser would want. Not a
    subgraph-matching engine; the recognisers stay procedural.

    **It carries no ownership.** Which recogniser claimed which face is an interpretation of
    these facts, not one of them, and it lives in :class:`b123d_recognisers._claims.ClaimLedger`
    instead -- an append-only sidecar built against one graph. Keeping them apart is what lets
    this object stay immutable after construction and be reused across a whole census while
    each run, or a rerun of one recogniser, keeps its own ledger. Analysis Situs writes
    recognition results back onto the AAG itself as attributes; the separation here is the one
    deliberate divergence, and it buys immutability at the cost of a second object.

    **Every attribute is lazy**, because measurement says eagerness does not
    pay: sharing the walk over ``part.faces()`` was worth 1.9% of a census, while sharing the
    ``Face.edges()`` derivation hanging off it was worth about a fifth. Attributes are derived
    on first ask and kept; a consumer that never asks for normals never pays for them.

    Scope it to one run over one part, as :class:`FaceEdges` is scoped -- it holds the part's
    faces alive, and its node ids stop meaning anything the moment the part changes.
    """

    def __init__(self, part, *, face_edges: FaceEdges | None = None) -> None:
        self._faces: list[FaceLike] = list(part.faces())
        self._nodes = tuple(FaceNode(at) for at in range(len(self._faces)))
        self._index = {face: at for at, face in enumerate(self._faces)}
        self._face_edges = face_edges
        self._edges: dict[int, tuple[EdgeLike, ...]] = {}
        self._surface: dict[int, int] = {}
        self._normal: dict[int, tuple[float, float, float] | None] = {}
        self._bounds: dict[int, tuple] = {}
        self._edge_faces: dict | None = None
        self._neighbours: dict[int, tuple[FaceNode, ...]] = {}

    def __len__(self) -> int:
        return len(self._faces)

    @property
    def nodes(self) -> tuple[FaceNode, ...]:
        """Every node, in the order the kernel yielded the faces."""

        return self._nodes

    def owns(self, node: FaceNode) -> bool:
        """Whether *node* was issued by this graph, checked by identity rather than by value."""

        at = node.index
        return 0 <= at < len(self._nodes) and self._nodes[at] is node

    def _at(self, node: FaceNode) -> int:
        if not self.owns(node):
            raise ValueError(f"{node!r} was not issued by this graph")
        return node.index

    def face(self, node: FaceNode) -> FaceLike:
        return self._faces[self._at(node)]

    def node_of(self, face: FaceLike) -> FaceNode | None:
        """The node for *face*, or None when it belongs to another part.

        Keyed on build123d shape equality, so a face from a second ``part.faces()`` walk
        resolves to the same node -- the property the whole graph rests on, and the one proved
        over every pinned fixture in :mod:`tests.test_adjacency`.
        """

        at = self._index.get(face)
        return None if at is None else self._nodes[at]

    def require_node(self, face: FaceLike) -> FaceNode:
        """This graph's node for *face*, or a refusal that names the mistake.

        The counterpart to :meth:`node_of`, for the callers that cannot do anything useful with
        ``None``. A recogniser resolving faces against a graph built from a different part
        would claim nothing and hand back an empty ledger, which reads downstream as "these
        families claim nothing" rather than as "you paired the wrong graph" -- and a reconciler
        reading that concludes there is no overlap and reports the duplicate it exists to
        suppress.

        Here rather than in each caller: `_recess_core` and `grooves` had grown the same three
        lines and the same message independently, and sharing them through either module would
        have made one recogniser import another for no reason a reader could justify.
        """

        node = self.node_of(face)
        if node is None:
            raise ValueError(
                "the claim ledger's graph was built from a different part: it has no "
                f"{face.bounding_box()}"
            )
        return node

    def edges(self, node: FaceNode) -> tuple[EdgeLike, ...]:
        """The edges of *node*, computed on first ask.

        A tuple, not the memo's own list. A returned list would have made the graph mutable
        through its own API -- clearing it would change adjacency and every later answer -- and
        a "do not mutate" comment is weaker than a type that cannot be. The lazy caches behind
        this do mutate; the answers handed out do not.
        """

        at = self._at(node)
        got = self._edges.get(at)
        if got is None:
            face = self._faces[at]
            self._edges[at] = got = tuple(
                face.edges() if self._face_edges is None else self._face_edges.of(face)
            )
        return got

    def surface(self, node: FaceNode) -> int:
        """The ``GeomAbs`` surface type, so callers stop constructing their own adaptor."""

        at = self._at(node)
        got = self._surface.get(at)
        if got is None:
            self._surface[at] = got = BRepAdaptor_Surface(self._faces[at].wrapped).GetType()
        return got

    def is_planar(self, node: FaceNode) -> bool:
        return bool(self.surface(node) == GeomAbs_Plane)

    def normal(self, node: FaceNode) -> tuple[float, float, float] | None:
        """The unit normal, or None for a face too degenerate to have one.

        **Geometric, not material-side**, and the distinction is load-bearing rather than
        pedantic. This is ``normal_at()``: it points whichever way the surface's parameterisation
        does, so on a ``REVERSED`` face it points *into* the solid. A recogniser asking "which
        side is the material" wants :func:`frame_points_outward` instead, and the two differ by a
        sign on exactly the faces where it matters most. Nothing but this paragraph said so
        before, and it is why ``_recess_core._Face`` cannot simply be replaced by a node.

        None rather than an exception because every caller today wraps the kernel call in a
        ``try`` and skips the face; returning the skip makes that one decision instead of
        seven.
        """

        at = self._at(node)
        if at not in self._normal:
            try:
                unit = self._faces[at].normal_at()
            except Exception:  # noqa: BLE001 - a degenerate face has no normal to read
                self._normal[at] = None
            else:
                self._normal[at] = (unit.X, unit.Y, unit.Z)
        return self._normal[at]

    def bounds(
        self, node: FaceNode
    ) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
        """``((x_lo, x_hi), (y_lo, y_hi), (z_lo, z_hi))``, indexable by axis number.

        By axis rather than as a build123d box because every caller indexes it by an axis it
        computed, and each was unpacking the box by hand to do so.
        """

        at = self._at(node)
        got = self._bounds.get(at)
        if got is None:
            bb = self._faces[at].bounding_box()
            self._bounds[at] = got = (
                (bb.min.X, bb.max.X),
                (bb.min.Y, bb.max.Y),
                (bb.min.Z, bb.max.Z),
            )
        return got

    def neighbours(self, node: FaceNode) -> tuple[FaceNode, ...]:
        """The nodes sharing an edge with *node*, excluding itself, each once.

        Order follows the face's own edge order, so it inherits the part's traversal order and
        nothing more: a caller needing determinism must sort or reduce, as the blend
        recognisers do by keeping the nearest neighbour per axis.
        """

        at = self._at(node)
        got = self._neighbours.get(at)
        if got is None:
            found: list[FaceNode] = []
            seen = {at}
            for edge in self.edges(node):
                for other in self._edge_face_map().get(edge, ()):
                    neighbour = self._index.get(other)
                    if neighbour is None or neighbour in seen:
                        continue
                    seen.add(neighbour)
                    found.append(self._nodes[neighbour])
            self._neighbours[at] = got = tuple(found)
        return got

    def arc(self, a: FaceNode, b: FaceNode) -> str | None:
        """How the solid turns where two faces meet: ``"convex"``, ``"concave"`` or ``"smooth"``.

        The attribute an attributed adjacency graph is *for*, and the half this package went
        without. Nodes carry facts about a face; until now nothing said what happened *between*
        two of them, so a recogniser needing that inferred it at the point of use or did not ask.

        - **smooth** -- the two outward normals agree to :data:`SMOOTH_ARC_COS` where the faces
          meet. A face split in two by a neighbouring feature is the exact case, its halves
          coplanar; a tangential blend is the approximate one. This is why ADR 0004's amendment
          treats seeing *through* a blend and *across* a split as one mechanism: a split is the
          zero-angle blend.
        - **convex** / **concave** -- whether the material forms a wedge at the edge or wraps
          around it. Read from the direction the boundary of *a* walks the shared edge: turning
          left from that direction, in *a*'s surface, points into *a*, and which side of *b* that
          lands on is the answer.

        Evaluated *at a point on the shared edge*, from each face's own normal there, so it is
        total rather than planar-only: a plane has one normal everywhere and a cone does not, and
        a groove's conical lead-in is precisely the face a recogniser must classify an arc
        against.

        None when the faces share no edge, or where a normal or the edge's direction cannot be
        read.

        **Not a generalisation of** :func:`b123d_recognisers._bevel.convex_bevel`, which asks a
        different question -- whether the corner a bevel *replaces* is convex, that is whether
        material was removed there or added. A gusset filling a re-entrant corner has convex arcs
        to both walls it meets while filling a concave corner, and both answers are right.
        """

        shared = self.shared_edges(a, b)
        if not shared:
            return None
        walk = self._boundary_direction(a, shared[0])
        if walk is None:
            return None
        direction, point = walk
        na, nb = self._normal_at(a, point), self._normal_at(b, point)
        if na is None or nb is None:
            return None
        if sum(x * y for x, y in zip(na, nb, strict=True)) > SMOOTH_ARC_COS:
            return "smooth"
        into = (
            na[1] * direction[2] - na[2] * direction[1],
            na[2] * direction[0] - na[0] * direction[2],
            na[0] * direction[1] - na[1] * direction[0],
        )
        return "convex" if sum(x * y for x, y in zip(into, nb, strict=True)) < 0 else "concave"

    def _normal_at(self, node: FaceNode, point) -> tuple[float, float, float] | None:
        """This face's outward normal *at a point*, or None where it has none.

        Not cached, unlike :meth:`normal`: the answer varies over a curved face, so there is no
        one value to keep. The point is the whole reason this exists -- a plane has one normal
        everywhere and a cone does not, and an arc has to be read where the faces actually meet.

        **Not** ``normal_at``, which ignores the point it is given: asked at 0, 90 and 180
        degrees around a cylinder it returns the same vector three times, so a per-point reader
        built on it silently reads the patch's middle instead. The point is projected to a
        surface parameter and the surface differentiated there.

        The sign correction is a single orientation flip, unlike
        :func:`frame_points_outward`'s two terms: ``du x dv`` is built from the parameterisation
        and so already carries the frame's handedness, where a stored axis direction does not.
        Checked on 659 faces across generated solids and imported STEP -- ``FORWARD`` agrees with
        the material side every time, ``REVERSED`` never does.
        """

        face = self._faces[self._at(node)]
        try:
            parameters = ShapeAnalysis_Surface(BRep_Tool.Surface_s(face.wrapped)).ValueOfUV(
                gp_Pnt(*point), 1e-6
            )
            adaptor = BRepAdaptor_Surface(face.wrapped)
            here, along_u, along_v = gp_Pnt(), gp_Vec(), gp_Vec()
            adaptor.D1(parameters.X(), parameters.Y(), here, along_u, along_v)
        except Exception:  # noqa: BLE001 - a degenerate patch has no normal there
            return None
        cross = along_u.Crossed(along_v)
        if cross.Magnitude() < 1e-12:
            return None
        cross.Normalize()
        forward = face.wrapped.Orientation() != TopAbs_Orientation.TopAbs_REVERSED
        sign = 1.0 if forward else -1.0
        return (sign * cross.X(), sign * cross.Y(), sign * cross.Z())

    def _boundary_direction(self, node: FaceNode, edge: EdgeLike):
        """``(direction, point)``: how *node*'s boundary walks *edge*, and where it was measured.

        The edge's own parameterisation is not it -- OCP does not orient that consistently, and a
        classification resting on it reports both signs on a plain box where every edge is
        convex. What is consistent is the orientation the edge carries *within this face*, which
        is what makes the two faces of a manifold edge walk it in opposite directions and the
        arc's answer the same from either end.

        Deliberately **not** flipped for a ``REVERSED`` face. ``normal_at`` already accounts for
        face orientation, so flipping here too double-corrects -- measured, that broke the
        opposite-directions property on exactly half a box's edges.
        """

        face = self._faces[self._at(node)]
        explorer = TopExp_Explorer(face.wrapped, TopAbs_EDGE)
        reversed_here = None
        while explorer.More():
            current = explorer.Current()
            if current.IsSame(edge.wrapped):
                reversed_here = current.Orientation() == TopAbs_Orientation.TopAbs_REVERSED
                break
            explorer.Next()
        if reversed_here is None:
            return None
        curve = BRepAdaptor_Curve(edge.wrapped)
        middle = 0.5 * (curve.FirstParameter() + curve.LastParameter())
        point, tangent = gp_Pnt(), gp_Vec()
        curve.D1(middle, point, tangent)
        raw = (tangent.X(), tangent.Y(), tangent.Z())
        length = sum(x * x for x in raw) ** 0.5
        if length < 1e-12:
            return None
        sign = -1.0 / length if reversed_here else 1.0 / length
        return tuple(x * sign for x in raw), (point.X(), point.Y(), point.Z())

    def shared_edges(self, a: FaceNode, b: FaceNode) -> tuple[EdgeLike, ...]:
        """The edges along which two faces meet, which an arc's classification will need.

        Retained rather than discarded because "is this arc convex" is a question about the
        edge, and answering it later without re-deriving the adjacency requires keeping it.
        """

        other = set(self.edges(b))
        return tuple(edge for edge in self.edges(a) if edge in other)

    def _edge_face_map(self) -> dict:
        if self._edge_faces is None:
            built: dict = {}
            for node in self._nodes:
                for edge in self.edges(node):
                    built.setdefault(edge, []).append(self._faces[node.index])
            self._edge_faces = built
        return self._edge_faces


def frame_points_outward(face: FaceLike) -> bool | None:
    """Does this face's own surface frame already point out of the solid?

    The material-side convention, in one place. An analytic surface carries a frame whose normal
    direction is a property of the *surface*, not of the face using it, so a face records
    separately whether it runs with that direction (``FORWARD``) or against it (``REVERSED``).
    Neither term alone answers the question: **mirroring a solid makes the frame left-handed and
    flips the orientations too**, so a test on orientation alone inverts on a mirrored part. The
    answer is the product, ``FORWARD == frame.Direct()``.

    Three sites derive *which side* from this: cylinders in ``_recess_core`` and
    ``_cylinder_substrate``, spheres in ``_hole_features``. A fourth used it to build a planar
    outward normal, which turned out to be redundant -- ``normal_at`` already returns one -- so
    what this is for is the whole-face question, asked where there is no single normal to read.

    The sites agreed, which is luck rather than design: no test could tell, because
    left-handed frames are 6 of 3,853 across all 72 corpus parts, and deleting the handedness term
    from any of them left the whole suite green. ``tests/test_material_side.py`` generates the
    geometry the corpus lacks and checks the convention against the solid classifier.

    Returns None for a surface this cannot read a frame from -- a torus, a spline -- which is a
    genuine "no answer" rather than a default. Coercing it to False would put material on one
    side of a blend and leave nothing downstream able to tell that from a real answer.

    Every caller today has already established the surface type before asking, so None is
    unreachable for them and ``bool(...)`` at those sites records that rather than dismissing
    it. A caller that has *not* filtered first must handle the third answer, and the honest
    shape is to return None onwards rather than pick a side.
    """

    surface = BRepAdaptor_Surface(face.wrapped)
    kind = surface.GetType()
    if kind == GeomAbs_Plane:
        position = surface.Plane().Position()
    elif kind == GeomAbs_Cylinder:
        position = surface.Cylinder().Position()
    elif kind == GeomAbs_Sphere:
        position = surface.Sphere().Position()
    else:
        return None
    forward = face.wrapped.Orientation() == TopAbs_Orientation.TopAbs_FORWARD
    return bool(forward == position.Direct())


def edge_face_map(faces: Iterable[FaceLike], *, face_edges: FaceEdges | None = None) -> dict:
    """Map every edge of *faces* to the faces that meet along it.

    One pass. The pairwise alternative — asking every face pair whether any of their edges
    match — is ``O(faces² × edges²)``; ``fillets`` measured that at 3.7M ``IsSame`` calls
    and about six seconds before replacing it.

    Takes the faces rather than the part because every caller already holds them, and
    walking ``part.faces()`` a second time here measured at a tenth of ``recognise_fillets``
    on the pinned corpus — the same reason :func:`~b123d_recognisers._geometry.part_scale`
    takes a bounding box rather than a solid.

    Pass *face_edges* to reuse a :class:`FaceEdges` memo across recognisers; omitted, the map
    is built from a private one, so a lone recogniser call behaves exactly as before.

    An edge normally maps to two faces. A seam edge on a closed surface maps to one, and
    a non-manifold edge to more, so callers must not assume the length.
    """

    memo = face_edges if face_edges is not None else FaceEdges()
    edge_faces: dict = {}
    for face in faces:
        for edge in memo.of(face):
            edge_faces.setdefault(edge, []).append(face)
    return edge_faces


def neighbours(face: FaceLike, edge_faces: dict, *, face_edges: FaceEdges | None = None) -> list:
    """The distinct faces sharing an edge with *face*, excluding *face* itself.

    Order follows *face*'s own edge order, so it inherits the part's traversal order and
    nothing more — a caller that needs a deterministic result must sort or reduce it, as
    :func:`b123d_recognisers.recognise_chamfers` does by keeping the nearest neighbour per
    axis rather than the first one seen.

    *face_edges* reuses a shared :class:`FaceEdges` memo; this is the hottest caller of it,
    since the blend recognisers ask for the neighbours of every face of the part.
    """

    seen = {face}
    out = []
    for edge in (face_edges.of(face) if face_edges is not None else face.edges()):
        for other in edge_faces.get(edge, ()):
            if other in seen:
                continue
            seen.add(other)
            out.append(other)
    return out


def axis_aligned_axis(face_wrapped) -> tuple[int, float] | None:
    """The axis a planar face's normal aligns with and that plane's fixed coordinate along
    it, or None if the face is not planar or not axis-aligned. Sign-agnostic (only alignment
    matters here); the coordinate locates the plane."""

    s = BRepAdaptor_Surface(face_wrapped)
    if s.GetType() != GeomAbs_Plane:
        return None
    d = s.Plane().Axis().Direction()
    comp = (abs(d.X()), abs(d.Y()), abs(d.Z()))
    if max(comp) <= AXIS_ALIGNED_COS:
        return None
    ax = max(range(3), key=lambda i: comp[i])
    loc = s.Plane().Location()
    return ax, (loc.X(), loc.Y(), loc.Z())[ax]


def connected_components(
    items: Iterable[_T], joined: Callable[[_T, _T], bool]
) -> list[tuple[_T, ...]]:
    """Group *items* into connected components under the *joined* predicate.

    An ordinary private utility with two consumers, and deliberately not more than that. It was
    private to `polygonal_bosses` until `passages` wanted the same walk -- finding from inside a
    void the ring `polygonal_bosses` finds from outside a prism -- and one consumer does not
    justify a shared primitive.

    It is **not** shared face-adjacency semantics, and an earlier version of this docstring
    called it "the other half of the answer-face-adjacency-once finding", which overstated it:
    every caller still supplies the entire relation, so what they share is the breadth-first
    mechanism and not a domain model. The face adjacency they genuinely share is
    :class:`FaceGraph`, which both of them read their nodes' attributes from.

    **`joined` must be symmetric.** The walk only ever asks `joined(current, other)` with
    *current* already in the component, so an asymmetric predicate makes the answer depend on
    set iteration order: over ``0..4``, ``j == i + 1`` yields one component and ``i == j + 1``
    yields five singletons for the same relation.

    **Component and member order are unspecified.** Reversing either passes the whole suite, so
    nothing pins them -- `polygonal_bosses` sorts its rings by heading downstream and the record
    emitters canonicalise. They are also only deterministic for items whose hash is stable
    across runs, which today means the small ints the one caller passes. Do not rely on either.

    *joined* is supplied by the caller rather than fixed here. Both consumers happen to want
    the same conjunction today -- a shared edge and a shared span -- but they compute the span
    differently, along a caller-chosen axis for passages and along Z for bosses, and neither
    could use the other's. The span half is not decoration: without it, two equal-height bosses
    standing on one plate merge into a single twelve-sided ring.
    """

    components: list[tuple[_T, ...]] = []
    unseen = set(items)
    while unseen:
        connected = {unseen.pop()}
        frontier = list(connected)
        while frontier:
            current = frontier.pop()
            attached = {other for other in unseen if joined(current, other)}
            unseen -= attached
            connected |= attached
            frontier.extend(attached)
        components.append(tuple(connected))
    return components


def nearest_axis_aligned_planes(
    face: FaceLike,
    edge_faces: dict,
    centre: dict[int, float],
    *,
    exclude_axis: int,
    face_edges: FaceEdges | None = None,
) -> dict[int, float]:
    """Per axis, the coordinate of *face*'s nearest axis-aligned neighbour plane.

    The shared "what does this blend bridge" query. ``recognise_chamfers`` and
    ``recognise_fillets`` both need a bevel's or round's two neighbour planes to rebuild the
    virtual sharp corner it replaces, and both previously carried their own copy of this
    filter and its supporting :func:`axis_aligned_axis` — identical code, with each file's
    comment pointing at the other. A caller reads the result twice: an axis missing from it
    means no such neighbour on that axis, which is itself a rejection.

    *exclude_axis* is the axis the feature runs **along**; a plane facing that way is an end
    cap, not one of the two walls the feature bridges.

    The nearest plane per axis is the one forming this local corner. Ties break on the
    coordinate itself rather than on arrival, so the pick cannot depend on the order the
    kernel yields neighbours in — ``slanted_steps`` has a chamfer equidistant from two
    distinct Z planes, where the strict ``<`` this replaces kept whichever came first.
    """

    best: dict[int, tuple[float, float]] = {}  # axis -> (distance, coordinate)
    for other in neighbours(face, edge_faces, face_edges=face_edges):
        aligned = axis_aligned_axis(other.wrapped)
        if aligned is None or aligned[0] == exclude_axis:
            continue
        ax, coord = aligned
        key = (abs(coord - centre[ax]), coord)
        if ax not in best or key < best[ax]:
            best[ax] = key
    return {ax: coord for ax, (_, coord) in best.items()}
