"""The shipped ``py.typed`` marker must describe the complete public boundary."""

from __future__ import annotations

import dataclasses
import inspect
from typing import Any

import quiddity as recognition

_BARE = {tuple, list, dict, set, frozenset, Any}
_BARE_TEXT = {"tuple", "list", "dict", "set", "frozenset", "Any", "typing.Any"}


def _weak(annotation: object) -> bool:
    return annotation in _BARE or (
        isinstance(annotation, str) and annotation.replace(" ", "") in _BARE_TEXT
    )


def test_every_exported_function_has_a_concrete_signature() -> None:
    missing: list[str] = []
    weak: list[str] = []

    for name in recognition.__all__:
        candidate = getattr(recognition, name)
        if not inspect.isfunction(candidate):
            continue
        signature = inspect.signature(candidate)
        for parameter in signature.parameters.values():
            if parameter.annotation is inspect.Parameter.empty:
                missing.append(f"{name}.{parameter.name}")
            elif _weak(parameter.annotation):
                weak.append(f"{name}.{parameter.name}")
        if signature.return_annotation is inspect.Signature.empty:
            missing.append(f"{name}.return")
        elif _weak(signature.return_annotation):
            weak.append(f"{name}.return")

    assert missing == []
    assert weak == []


def test_every_exported_dataclass_field_has_a_concrete_type() -> None:
    weak = {
        f"{name}.{field.name}": field.type
        for name in recognition.__all__
        if inspect.isclass(candidate := getattr(recognition, name))
        and dataclasses.is_dataclass(candidate)
        for field in dataclasses.fields(candidate)
        if _weak(field.type)
    }

    assert weak == {}


def test_every_exported_class_method_has_a_concrete_signature() -> None:
    missing: list[str] = []
    weak: list[str] = []

    for class_name in recognition.__all__:
        candidate = getattr(recognition, class_name)
        if not inspect.isclass(candidate):
            continue
        for owner in candidate.__mro__[:-1]:
            for method_name, descriptor in vars(owner).items():
                if method_name.startswith("_"):
                    continue
                if isinstance(descriptor, property):
                    callable_member = descriptor.fget
                elif isinstance(descriptor, (classmethod, staticmethod)):
                    callable_member = descriptor.__func__
                else:
                    callable_member = descriptor if inspect.isfunction(descriptor) else None
                if callable_member is None:
                    continue
                signature = inspect.signature(callable_member)
                member = f"{class_name}.{method_name}"
                for parameter in signature.parameters.values():
                    if parameter.name in {"self", "cls"}:
                        continue
                    if parameter.annotation is inspect.Parameter.empty:
                        missing.append(f"{member}.{parameter.name}")
                    elif _weak(parameter.annotation):
                        weak.append(f"{member}.{parameter.name}")
                if signature.return_annotation is inspect.Signature.empty:
                    missing.append(f"{member}.return")
                elif _weak(signature.return_annotation):
                    weak.append(f"{member}.return")

    assert missing == []
    assert weak == []
