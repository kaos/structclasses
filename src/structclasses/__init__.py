# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
"""Boost your `dataclass` objects with suport for binary serialization."""
__version__ = "0.2"

from structclasses.base import Field
from structclasses.decorator import ByteOrder, structclass
from structclasses.field import (
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
    union,
)

__all__ = [
    "ByteOrder",
    "Field",
    "array",
    "binary",
    "double",
    "int16",
    "int32",
    "int64",
    "int8",
    "long",
    "record",
    "structclass",
    "text",
    "uint16",
    "uint32",
    "uint64",
    "uint8",
    "ulong",
    "union",
]
