# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
import pytest

from structclasses.decorator import fields, structclass
from structclasses.field.data import text
from structclasses.field.meta import field
from structclasses.field.primitive import int32, uint8, uint32, uint64
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
    assert_props(uc.prop, None)


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


def test_union_alignment() -> None:
    @structclass
    class Data:
        len: int
        msg: text[32] = field(pack_length="msg", unpack_length="len")
        sent: uint64

    @structclass
    class DataUnion:
        kind: int
        buffer: union[("a", int), ("b", Data)] = field(
            selector="kind",
            field_selector_map={"a": 1, "b": 2},
        )

    du = DataUnion(2, Data(0, "foo", 1)._pack())
    assert "=i3s1xQ" == Data(0, "foo", 1)._format()
    assert "=i4x16s" == du._format()
    assert 24 == len(du)

    Data.__structclass_fields__["sent"].configure(align=1)
    DataUnion.__structclass_fields__["buffer"].fields["b"].configure(align=1)
    du = DataUnion(2, Data(0, "foo", 1)._pack())

    assert "=i3sQ" == Data(0, "foo", 1)._format()
    assert "=i4x15s" == du._format()
    assert 23 == len(du)

    DataUnion.__structclass_fields__["buffer"].configure(align=4)

    assert "=i15s" == du._format()
    assert 19 == len(du)


@pytest.mark.parametrize(
    "pack_data, pack_union, data_fmt, union_fmt, union_len",
    [
        (False, False, "=i3s1xQ", "=i4x16s", 24),
        (True, False, "=i3sQ", "=i4x15s", 23),
        (False, True, "=i3s1xQ", "=i16s", 20),
        (True, True, "=i3sQ", "=i15s", 19),
    ],
)
def test_packed_records(pack_data, pack_union, data_fmt, union_fmt, union_len) -> None:
    @structclass(packed=pack_data)
    class PackedData:
        len: int
        msg: text[32] = field(pack_length="msg", unpack_length="len")
        sent: uint64

    @structclass(packed=pack_union)
    class PackedUnion:
        kind: int
        buffer: union[("a", int), ("b", PackedData)] = field(
            selector="kind",
            field_selector_map={"a": 1, "b": 2},
        )

    pu = PackedUnion(2, PackedData(0, "foo", 1)._pack())
    assert data_fmt == PackedData(0, "foo", 1)._format()
    assert union_fmt == pu._format()
    assert union_len == len(pu)


def test_empty_union() -> None:
    @structclass
    class U:
        buflen: uint32
        buffer: union[
            ("a", uint32),  # noqa: F821
            ("b", int32),  # noqa: F821
        ] = field(
            pack_length="buffer",
            unpack_length="buflen",
        )

    assert "=I4s" == U._format()
    assert b"\0\0\0\0" == U(0, b"")._pack()
    assert U(0, b"") == U._unpack(b"\0\0\0\0")


def test_empty_union_selector() -> None:
    @structclass(packed=True)
    class U:
        kind: uint8
        buflen: uint8
        buffer: union[
            ("a", uint32),  # noqa: F821
            ("b", int32),  # noqa: F821
        ] = field(
            selector="kind",
            field_selector_map=dict(a=1, b=2),
            pack_length="buffer",
            unpack_length="buflen",
        )

    u = U(1, 0, b"")
    assert "=2B4s" == U._format()
    assert u == U._unpack(b"\1\0")
    assert u.buffer.__value__ is None
    assert b"\1\0" == u._pack()
    assert 0 == u.buflen
