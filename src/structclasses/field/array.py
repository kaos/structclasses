# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from __future__ import annotations

import struct
from collections.abc import Mapping
from enum import Enum
from itertools import chain, islice
from typing import Annotated, Any, Iterable, Iterator

from structclasses.base import Context, Field
from structclasses.field.record import ElemT


class ArrayField(Field):
    def __init__(self, field_type: type, length: int | str) -> None:
        self.elem_field = Field._create_field(field_type)
        self.length = length
        fmt = "|"
        if isinstance(length, int):
            try:
                if self.is_packing_bytes:
                    fmt = f"{self.elem_field.size * length}s"
                elif self.elem_field.fmt != "|":
                    fmt = f"{length}{self.elem_field.fmt}"
            except struct.error:
                # struct.calcsize chokes on any | formats
                pass
        super().__init__(list, fmt)

    @property
    def is_packing_bytes(self) -> bool:
        return len(self.elem_field.fmt) > 1

    def get_format(self, context: Context) -> str:
        if self.is_packing_bytes:
            return f"{self.elem_field.size * self.get_length(context)}s"
        elif self.fmt == "|":
            return f"{self.get_length(context)}{self.elem_field.fmt}"
        else:
            return self.fmt

    def get_length(self, context: Context) -> int:
        if isinstance(self.length, int):
            return self.length
        if isinstance(context.obj, Mapping) and self.length in context.obj:
            return int(context.obj[self.length])
        elif isinstance(self.length, str) and hasattr(context.obj, self.length):
            return int(getattr(context.obj, self.length))
        else:
            raise ValueError(
                f"structclasses: array length points at unknown field: {self.length!r}"
            )

    def prepack(self, value: Any, context: Context) -> Iterable[PrimitiveType]:
        length = self.get_length(context)
        elem_it = chain(value or [], (self.elem_field.type() for _ in range(length)))
        values_it = chain.from_iterable(
            self.elem_field.prepack(elem, context) for elem in islice(elem_it, length)
        )
        if self.is_packing_bytes:
            return (
                struct.pack(
                    context.params.byte_order.value + length * self.elem_field.fmt, *values_it
                ),
            )
        else:
            return tuple(values_it)

    def postunpack(self, values: Iterator[Any], context: Context) -> Any:
        length = self.get_length(context)
        if self.is_packing_bytes:
            values_it = (
                iter(v)
                for v in struct.iter_unpack(
                    context.params.byte_order.value + self.elem_field.fmt, next(values)
                )
            )
        else:
            values_it = length * (values,)
        return [self.elem_field.postunpack(v, context) for v in values_it]


class array:
    def __class_getitem__(cls, arg: tuple[ElemT, int]) -> list[ElemT]:
        elem_type, length = arg
        return Annotated[list[ElemT], ArrayField(elem_type, length)]


class EnumField(Field):
    @classmethod
    def _create(cls, field_type: type) -> Field:
        if issubclass(field_type, Enum):
            return cls(field_type)
        else:
            return super()._create(field_type)

    def __init__(self, field_type: type[Enum]) -> None:
        self.member_type_field = Field._create_field(type(next(iter(field_type)).value))
        super().__init__(field_type, self.member_type_field.fmt)

    def prepack(self, value: Enum, context: Context) -> Iterable[PrimitiveType]:
        assert isinstance(value, self.type)
        return self.member_type_field.prepack(value.value, context)

    def postunpack(self, values: Iterator[Any], context: Context) -> Any:
        return self.type(self.member_type_field.postunpack(values, context))
