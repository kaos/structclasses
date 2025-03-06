# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
"""Boost your `dataclass` objects with suport for binary serialization."""
__version__ = "0.19"

from structclasses.base import INHERIT, Field
from structclasses.decorator import ByteOrder, fields, is_structclass, structclass
from structclasses.field.array import array
from structclasses.field.data import binary, text
from structclasses.field.enum import EnumField  # noqa: F401
from structclasses.field.meta import field

# from structclasses.field.enum import y
from structclasses.field.primitive import (
    double,
    int8,
    int16,
    int32,
    int64,
    long,
    uint8,
    uint16,
    uint32,
    uint64,
    ulong,
)
from structclasses.field.record import record
from structclasses.field.union import union

__all__ = [
    "ByteOrder",
    "Field",
    "INHERIT",
    "array",
    "binary",
    "double",
    "field",
    "fields",
    "int16",
    "int32",
    "int64",
    "int8",
    "is_structclass",
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
