"""Versioned canonical semantic projection for migration goldens."""

from __future__ import annotations

import dataclasses
import json
import math
from enum import Enum
from pathlib import Path
from typing import Any

CANONICALIZER_VERSION = 2
FLOAT_DIGITS = 8
_U_EXTENT_DIGITS = 7
_OMIT_MAPPING_KEYS = frozenset({"face", "solid_idx"})


class CanonicalizationError(TypeError):
    """A value cannot cross the canonical golden boundary."""


def _float(value: float) -> float:
    if not math.isfinite(value):
        raise CanonicalizationError("non-finite floats are not canonical")
    value = round(value, FLOAT_DIGITS)
    return 0.0 if value == 0 else value


def canonicalize(value: Any) -> Any:
    """Project *value* to deterministic JSON primitives without CAD objects."""

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        fields = {
            field.name: canonicalize(getattr(value, field.name))
            for field in dataclasses.fields(value)
        }
        return {"_type": type(value).__name__, **fields}
    if isinstance(value, Enum):
        return canonicalize(value.value)
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return _float(value)
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise CanonicalizationError("canonical mapping keys must be strings")
        result = {}
        for key, item in sorted(value.items()):
            if key in _OMIT_MAPPING_KEYS:
                continue
            # OCCT can move an analytic STEP face's dimensionless parameter span by roughly
            # 1.4e-8 while preserving its geometry. Seven digits remove that observed jitter;
            # other floats retain the established eight-digit semantic snapshot contract.
            result[key] = (
                _float(round(item, _U_EXTENT_DIGITS))
                if key == "u_extent" and isinstance(item, float)
                else canonicalize(item)
            )
        return result
    if isinstance(value, (list, tuple)):
        return [canonicalize(item) for item in value]
    if isinstance(value, (set, frozenset)):
        items = [canonicalize(item) for item in value]
        return sorted(items, key=canonical_json)
    raise CanonicalizationError(
        f"{type(value).__module__}.{type(value).__qualname__} is not canonical JSON data"
    )


def canonical_json(value: Any) -> str:
    """Serialize *value* using the versioned canonical projection."""

    return json.dumps(canonicalize(value), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_canonical(path: Path, value: Any, *, overwrite: bool = False) -> None:
    """Write canonical JSON, refusing to replace reviewed data by default."""

    if path.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite {path}; pass overwrite=True")
    path.write_text(canonical_json(value), encoding="utf-8")
