# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
import pytest

from structclasses.decorator import structclass
from structclasses.field.meta import field
from structclasses.field.union import (
    UnionProperty,
    UnionPropertyValue,
    UnionValueNotActiveError,
    union,
)


@structclass
class StdCUnionClass:
    """Struct class with a union field operating in standard C mode."""

    prop: union[("a", int), ("b", bool)]


@structclass
class SelectorUnionClass:
    sel: int
    prop: union[("a", int), ("b", bool)] = field(selector="sel", field_selector_map=dict(a=1, b=2))


def assert_props(prop, kind, **kwargs):
    assert kind == prop.__kind__
    for key in ("a", "b"):
        if key in kwargs:
            assert kwargs[key] == getattr(prop, key)
        else:
            with pytest.raises(UnionValueNotActiveError):
                getattr(prop, key)
    if kind:
        assert getattr(prop, kind) == prop.__value__


def test_std_c_union_property() -> None:
    assert isinstance(StdCUnionClass.prop, UnionProperty)

    uc = StdCUnionClass(b"\0\0\0\0")
    assert isinstance(uc.prop, UnionPropertyValue)

    assert_props(uc.prop, None, a=0, b=False)

    uc.prop.a = 42
    assert_props(uc.prop, None, a=42, b=True)

    uc.prop.b = False
    assert_props(uc.prop, None, a=0, b=False)

    uc.prop.b = True
    assert_props(uc.prop, None, a=1, b=True)

    del uc.prop
    assert_props(uc.prop, None, a=0, b=False)


def test_union_format() -> None:
    # The static size when there is no selector, is to use the largest member.
    assert "=4s" == StdCUnionClass._format()
