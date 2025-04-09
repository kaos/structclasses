# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
import pytest

from structclasses import array, field, structclass, text, uint16, uint32, uint64


@pytest.mark.parametrize(
    "atype, field_type_name",
    [
        (array[uint16, 3], "ArrayField__3x__PrimitiveField__int__H"),
        (array[uint32, 3], "ArrayField__3x__PrimitiveField__int__I"),
    ],
)
def test_array_field_class_name(atype: type, field_type_name: str) -> None:
    field_type = atype.__metadata__[0]
    assert field_type_name == field_type.__name__


def test_nested_struct() -> None:
    @structclass(packed=True)
    class Item:
        len: uint32
        val: text[32] = field(pack_length="val", unpack_length="len")

    @structclass(packed=True)
    class List:
        count: uint32
        items: array[Item, 10] = field(pack_length="items", unpack_length="count")

    list = List(2, [Item(5, "tests"), Item(7, "testing")])
    data = list._pack()
    assert b"\x02\x00\x00\x00\x05\x00\x00\x00tests\x07\x00\x00\x00testing" == data
    assert list == List._unpack(data)


@pytest.mark.timeout(1)
def test_dynamic_array_with_large_max_num_items() -> None:
    @structclass
    class Item:
        foo: uint64
        bar: uint64

    @structclass
    class List:
        num_items: uint32
        items: array[Item, 1000 * 1000] = field(pack_length="items", unpack_length="num_items")

    assert "=I" == List._format()


@pytest.mark.timeout(1)
def test_array_with_large_num_items() -> None:
    @structclass
    class Item:
        foo: uint64
        bar: uint64

    @structclass
    class List:
        items: array[Item, 5000]

    assert "=2Q" == Item._format()
    assert "=80000s" == List._format()


@pytest.mark.timeout(1)
def test_array_with_large_num_items_of_dynamic_size() -> None:
    @structclass
    class Item:
        data: text[32] = field(pack_length="data", unpack_length=uint32)

    @structclass
    class List:
        items: array[Item, 5000]

    assert "=I" == Item._format()
    assert "=" == List._format()  # The size of `items` is unknown without data.
