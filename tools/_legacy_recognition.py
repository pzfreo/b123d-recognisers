"""Private tooling imports for frozen detector-baseline measurements, not consumer API."""

from b123d_recognisers.edge_open_circular_recesses import (
    EdgeOpenCircularPocket,
    OpenCircularSection,
    OpenCircularSectionSegment,
    recognise_edge_open_circular_pockets,
)
from b123d_recognisers.edge_open_prismatic_recesses import (
    EdgeOpenPrismaticRecess,
    OpenPolygonalSection,
    OpenSectionOpening,
    recognise_edge_open_prismatic_recesses,
)
from b123d_recognisers.passages import (
    Passage,
    PassageCompatibilityError,
    PassageEnds,
    SectionPassage,
    recognise_passages,
    recognise_section_passages,
)
from b123d_recognisers.prismatic_pockets import (
    PrismaticPocket,
    recognise_prismatic_pockets,
)
from b123d_recognisers.rectangular_blind_slots import (
    RectangularBlindSlot,
    recognise_rectangular_blind_slots,
)
from b123d_recognisers.round_bottom_slots import (
    RoundBottomBlindSlot,
    recognise_round_bottom_blind_slots,
)
from b123d_recognisers.slots import (
    Channel,
    Pocket,
    PocketArray,
    PocketGrid,
    recognise_channels,
    recognise_pocket_patterns,
    recognise_pockets,
)

__all__ = [
    "Pocket",
    "PocketArray",
    "PocketGrid",
    "PrismaticPocket",
    "Channel",
    "RectangularBlindSlot",
    "RoundBottomBlindSlot",
    "EdgeOpenCircularPocket",
    "OpenCircularSection",
    "OpenCircularSectionSegment",
    "EdgeOpenPrismaticRecess",
    "OpenPolygonalSection",
    "OpenSectionOpening",
    "Passage",
    "PassageEnds",
    "SectionPassage",
    "PassageCompatibilityError",
    "recognise_pockets",
    "recognise_pocket_patterns",
    "recognise_channels",
    "recognise_prismatic_pockets",
    "recognise_rectangular_blind_slots",
    "recognise_round_bottom_blind_slots",
    "recognise_edge_open_circular_pockets",
    "recognise_edge_open_prismatic_recesses",
    "recognise_passages",
    "recognise_section_passages",
]


def build_raw_recognition_result(part, *, cylinders=None, rotational=False):
    from b123d_recognisers.result import _take_inventory

    return _take_inventory(part, cylinders=cylinders, rotational=rotational)._legacy_result


build_recognition_result = build_raw_recognition_result


def feature_census(part):
    from b123d_recognisers.census import _LEGACY_CENSUS_BINDINGS
    from b123d_recognisers.result import _take_inventory

    product = _take_inventory(part)
    return {
        key: len(product.distinct_steps.candidates)
        if key == "step"
        else len(getattr(product._legacy_result, field))
        for key, field in _LEGACY_CENSUS_BINDINGS
    }


def namespace():
    """Frozen detector-view adapter used only by the historic golden snapshot tools."""
    from types import SimpleNamespace

    import b123d_recognisers as public

    values = {name: getattr(public, name) for name in public.__all__}
    values.update({name: globals()[name] for name in __all__})
    values.update(
        build_recognition_result=build_recognition_result,
        build_raw_recognition_result=build_raw_recognition_result,
    )
    values["__all__"] = sorted(set(public.__all__) | set(__all__))
    return SimpleNamespace(**values)
