# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
# from __future__ import annotations


import pytest

from structclasses import (
    INHERIT,
    ByteOrder,
    array,
    binary,
    field,
    fields,
    int8,
    record,
    structclass,
    text,
    uint8,
    union,
)
from structclasses.base import Context, Params


def assert_roundtrip(value):
    assert value == value._unpack(value._pack())


def test_it_doesnt_blow_up():
    @structclass
    class Simple:
        pass

    assert isinstance(Simple, type)


@pytest.mark.parametrize(
    "byte_order, value, packed",
    [
        (ByteOrder.BIG_ENDIAN, 0o42, b"\0\0\0\42"),
        (ByteOrder.LITTLE_ENDIAN, 0o42, b"\42\0\0\0"),
    ],
)
def test_int_field(byte_order: ByteOrder, value: int, packed: bytes) -> None:
    @structclass(byte_order=byte_order)
    class SimpleInt:
        a: int

    s = SimpleInt(value)
    assert f"{byte_order.value}i" == s._format()
    assert value == s.a
    assert packed == s._pack()
    assert s == SimpleInt._unpack(packed)
    assert len(s) == 4


def test_two_fields():
    @structclass
    class TwoInts:
        a: int8
        b: int8

    s = TwoInts(1, 2)
    assert ">bb" == s._format()
    assert 1 == s.a
    assert 2 == s.b
    assert b"\1\2" == s._pack()
    assert_roundtrip(s)
    assert len(s) == 2


def test_nested_structures():
    @structclass
    class Inner:
        a: int8
        b: int8

    @structclass
    class Outer:
        c: int8
        d: Inner
        e: int8

    s = Outer(c=3, d=Inner(1, 2), e=4)
    assert ">bbbb" == s._format()
    assert_roundtrip(s)
    assert len(s) == 4
    assert len(Outer) == 4
    assert len(Inner) == 2


@pytest.mark.parametrize(
    "byte_order, value, packed",
    [
        (
            ByteOrder.BIG_ENDIAN,
            [0x1234, 0x12, 0x34],
            b"\0\0\x124\0\0\0\x12\0\0\x004",
        ),
        (
            ByteOrder.LITTLE_ENDIAN,
            [0x43, 0x21, 0x4321],
            b"C\0\0\0!\0\0\0!C\0\0",
        ),
    ],
)
def test_int_array(byte_order: ByteOrder, value: int, packed: bytes) -> None:
    @structclass(byte_order=byte_order)
    class IntArray:
        xs: array[int, len(value)]

    s = IntArray(value)
    assert f"{byte_order.value}{len(value)}i" == s._format()
    assert_roundtrip(s)
    assert packed == s._pack()
    assert len(s) == 4 * len(value)


@pytest.mark.parametrize(
    "byte_order, value, size, packed",
    [
        (
            ByteOrder.BIG_ENDIAN,
            [dict(x=0x1234, y=1), dict(x=0x12, y=2), dict(x=0x34, y=3)],
            24,
            b"\0\0\x124\0\0\0\1\0\0\0\x12\0\0\0\2\0\0\x004\0\0\0\3",
        ),
        (
            ByteOrder.LITTLE_ENDIAN,
            [dict(x=0x43, y=1), dict(x=0x21, y=2), dict(x=0x4321, y=3)],
            24,
            b"C\0\0\0\1\0\0\0\x21\0\0\0\2\0\0\x00!C\0\0\3\0\0\0",
        ),
    ],
)
def test_nested_int_array(byte_order: ByteOrder, value: list, size: int, packed: bytes) -> None:
    @structclass(byte_order=byte_order)
    class ArrayOfIntRecords:
        xs: array[record[dict, ("x", int), ("y", int)], len(value)]

    s = ArrayOfIntRecords(value)
    assert f"{byte_order.value}{size}s" == s._format()
    assert_roundtrip(s)
    assert packed == s._pack()
    assert len(s) == size


def test_text_array():
    @structclass
    class TextArray:
        msgs: array[text[5], 5]

    s = TextArray(["a", "bc", "def", "ghij", "klmno"])
    assert ">25s" == s._format()
    assert_roundtrip(s)
    assert len(s) == 25


def test_dynamic_size_array():
    @structclass
    class DynIntArray:
        count: int
        xs: array[int, "count"]

    s = DynIntArray(3, [11, 22, 33])
    assert ">i|" == s._format()
    assert ">i3i" == s._format(context=Context(Params(), s))
    assert_roundtrip(s)
    assert len(s) == 16


def test_dynamic_length_text():
    @structclass
    class DynTextField:
        len: int
        txt: text["len"]

    s = DynTextField(4, "abcd")
    assert ">i|" == s._format()
    assert ">i4s" == s._format(context=Context(Params(), s))
    assert_roundtrip(s)
    assert len(s) == 8


def test_union_type():
    @structclass
    class Val1:
        a: int

    @structclass
    class Val2:
        b: int
        c: int

    @structclass
    class UnionValue:
        typ: int
        v: union["typ", (0, Val1), (1, Val2)]

    s = UnionValue(1, Val2(2, 3))
    assert ">i|" == s._format()
    assert ">iii" == s._format(context=Context(Params(), s))
    assert_roundtrip(s)
    assert len(s) == 12


def test_primitive_type_array():
    """This is not supported.

    (yet?)
    """
    with pytest.raises(TypeError):

        @structclass
        class PrimitiveArray:
            data: int8[3]

        s = PrimitiveArray([4, 5, 6])
        assert ">3b" == s._format()


def test_disjoint_dynamic_length_text() -> None:
    """Disjoint, meaning the length is different for reading and writing."""

    @structclass
    class HeaderStuff:
        msg_len: uint8

    @structclass
    class DisjointTextLength:
        hdr: HeaderStuff
        msg: text[32] = field(pack_length="msg", unpack_length="hdr.msg_len")

    s = DisjointTextLength(HeaderStuff(4), "test")
    assert ">B|" == s._format()
    assert ">B4s" == s._format(context=Context(Params(), s))
    assert_roundtrip(s)
    assert len(s) == 5

    with pytest.raises(ValueError):
        # Max length for the msg field is 32
        len(DisjointTextLength(HeaderStuff(0), "01234567890123456789012345678912x"))

    v = DisjointTextLength._unpack(b"\4testing extra data not included")
    assert v == s

    v = DisjointTextLength(HeaderStuff(0), "test")._pack()
    assert v == b"\4test"

    s = DisjointTextLength(HeaderStuff(0), "01234567890123456789012345678912")
    assert 0 == s.hdr.msg_len
    v = s._pack()
    assert v == b"\x2001234567890123456789012345678912"
    assert 32 == s.hdr.msg_len


def _check_field(cls, name, length, pack_length, unpack_length):
    fld = next(fld for n, fld in fields(cls) if name == n)
    assert length == fld.length
    assert pack_length == fld.pack_length
    assert unpack_length == fld.unpack_length


def test_override_field_def() -> None:
    @structclass
    class Base:
        field_a: text[4]
        field_b: text[5] = field(pack_length=7)
        field_c: text[6] = field(unpack_length=8)

    @structclass
    class Augment(Base):
        field_a: text[8] = field(pack_length=5, unpack_length=6)
        field_b: text[9]

    _check_field(Base, "field_a", 4, None, None)
    _check_field(Base, "field_b", 5, 7, None)
    _check_field(Base, "field_c", 6, None, 8)
    _check_field(Augment, "field_a", 8, 5, 6)
    _check_field(Augment, "field_b", 9, None, None)
    _check_field(Augment, "field_c", 6, None, 8)


def test_inherit_length() -> None:
    @structclass
    class Base:
        field: binary[10]

    @structclass
    class Child(Base):
        field: binary[INHERIT] = field(pack_length=2)

    _check_field(Base, "field", 10, None, None)
    _check_field(Child, "field", 10, 2, None)
