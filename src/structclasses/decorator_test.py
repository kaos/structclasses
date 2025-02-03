# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
# from __future__ import annotations

import pytest

from structclasses import ByteOrder, array, int8, record, structclass, text, union
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


def test_text_array():
    @structclass
    class TextArray:
        msgs: array[text[5], 5]

    s = TextArray(["a", "bc", "def", "ghij", "klmno"])
    assert ">25s" == s._format()
    assert_roundtrip(s)


def test_dynamic_size_array():
    @structclass
    class DynIntArray:
        count: int
        xs: array[int, "count"]

    s = DynIntArray(3, [11, 22, 33])
    assert ">i|" == s._format()
    assert ">i3i" == s._format(context=Context(Params(), s))
    assert_roundtrip(s)


def test_dynamic_length_text():
    @structclass
    class DynTextField:
        len: int
        txt: text["len"]

    s = DynTextField(4, "abcd")
    assert ">i|" == s._format()
    assert ">i4s" == s._format(context=Context(Params(), s))
    assert_roundtrip(s)


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
