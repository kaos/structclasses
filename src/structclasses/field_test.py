# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from enum import IntEnum, auto
from typing import Annotated, Any, Union

import pytest

from structclasses import (
    Field,
    array,
    binary,
    double,
    int8,
    int16,
    int32,
    int64,
    long,
    record,
    text,
    uint8,
    uint16,
    uint32,
    uint64,
    ulong,
)
from structclasses.base import Context


class MyEnum(IntEnum):
    A = auto()
    B = auto()


@pytest.mark.parametrize(
    "py_type, field_type, fmt, value",
    [
        (float, double, ">d", 4.2),
        (int, int16, ">h", 0x1234),
        (int, int32, ">i", 0x12345678),
        (int, int64, ">q", 0x1234567898765432),
        (int, int8, ">b", 0x12),
        (int, long, ">l", 0x12345678),
        (int, uint16, ">H", 0x8765),
        (int, uint32, ">I", 0x87654321),
        (int, uint64, ">Q", 0x9876543212345678),
        (int, uint8, ">B", 0x87),
        (int, ulong, ">L", 0x87654321),
        (int, int, ">i", None),
        (bool, bool, ">?", True),
        (float, float, ">f", 1.25),
        (str, text[8], ">8s", "abcd"),
        (bytes, binary[3], ">3s", b"123"),
        (dict, record[dict, ("a", int), ("b", bool)], ">i?", dict(a=1, b=False)),
        (list[uint16], array[uint16, 5], ">5H", [12, 23, 34, 45, 56]),
        (list[text[3]], array[text[3], 3], ">9s", ["a", "bc", "def"]),
        (MyEnum, MyEnum, ">i", MyEnum.B),
    ],
)
def test_create_field(py_type: type, field_type: type | Annotated, fmt: str, value: Any) -> None:
    pack_context = Context(root={"test": value})
    fld = Field._create_field(field_type, name="test")
    fld.pack(pack_context)
    assert fmt == pack_context.struct_format
    assert py_type == fld.type
    if value is not None:
        # Roundtrip test.
        unpack_context = Context(data=pack_context.pack())
        fld.unpack(unpack_context)
        unpack_context.unpack()
        assert unpack_context.root == pack_context.root
        assert value == unpack_context.root["test"]
