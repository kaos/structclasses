# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
import pytest

from structclasses.decorator import fields, structclass
from structclasses.field.data import text
from structclasses.field.meta import field
from structclasses.field.union import (
    UnionFieldError,
    UnionFieldSelectorMapError,
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


def assert_props(prop, kind, *, error_cls=UnionFieldError, **kwargs):
    assert kind == prop.__kind__
    for key in ("a", "b"):
        if key in kwargs:
            assert kwargs[key] == getattr(prop, key)
        else:
            with pytest.raises(error_cls):
                getattr(prop, key)
    if kind:
        assert getattr(prop, kind) == prop.__value__


def test_union_format() -> None:
    # The static size when there is no selector, is to use the largest member.
    assert "=4s" == StdCUnionClass._format()


def test_std_c_union() -> None:
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


def test_selector_union() -> None:
    assert isinstance(SelectorUnionClass.prop, UnionProperty)

    uc = SelectorUnionClass(1, b"*\0\0\0")
    assert isinstance(uc.prop, UnionPropertyValue)

    assert_props(uc.prop, "a", a=42)

    uc.prop.b = True
    assert_props(uc.prop, "b", b=True)
    assert 2 == uc.sel

    uc.sel = 1
    assert_props(uc.prop, "a", a=0)

    uc.sel = 2
    assert_props(uc.prop, "b", b=False)


def test_create_selector_union_value() -> None:
    uc = SelectorUnionClass(None, {"a": 1234})
    assert 1 == uc.sel
    assert_props(uc.prop, "a", a=1234)


def test_multi_selector_union() -> None:

    @structclass
    class MultiUnion:
        a: int
        b: text[4]
        u: union[("a0_foo", bool), ("a0_bar", bool), ("a1_gunk", bool)] = field(
            selector=("a", "b"),
            field_selector_map=dict(
                a0_foo=(0, "foo"),
                a0_bar=(0, "bar"),
                a1_gunk=(1, "gunk"),
            ),
        )

    mu = MultiUnion(a=0, b="bar", u=b"\0")
    assert mu.u.__kind__ == "a0_bar"
    mu.b = "gunk"
    with pytest.raises(UnionFieldSelectorMapError):
        mu.u.__kind__
    mu.a = 1
    assert mu.u.__kind__ == "a1_gunk"
    assert mu.u.a1_gunk == False
    mu.u.a0_foo = True
    assert mu.a == 0
    assert mu.b == "foo"
    assert b"\0\0\0\0foo\0\1" == mu._pack()


def test_sized_union() -> None:
    @structclass
    class Data:
        len: int
        msg: text[32] = field(pack_length="msg", unpack_length="len")

    @structclass
    class SizedUnion:
        kind: int
        buflen: int
        buffer: union[("a", int), ("b", Data)] = field(
            selector="kind",
            pack_length="buffer",
            unpack_length="buflen",
            field_selector_map={"a": 1, "b": 2},
        )

    su = SizedUnion(1, 4, b"\0x42")
    assert 12 == len(su)
    su.buffer.b = Data(0, "test message")
    assert 2 == su.kind
    assert 12 == su.buffer.b.len
    assert 24 == len(su)
    assert 16 == su.buflen  # Not updated until the field has been `pack`ed.
    assert b"\2\0\0\0\x10\0\0\0\x0c\0\0\0test message" == su._pack()
