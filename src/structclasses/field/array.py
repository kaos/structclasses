# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from __future__ import annotations

import struct
from dataclasses import replace

# from collections.abc import Mapping
from itertools import chain, islice
from typing import Annotated, Any, Iterable, Iterator, TypeVar

from structclasses.base import MISSING, Context, Field
from structclasses.field.primitive import PrimitiveType


class ArrayField(Field):
    fmt: str = ""

    def __class_getitem__(cls, arg: tuple[type, int | str]) -> type[ArrayField]:
        elem_type, length = arg
        elem_field = Field._create_field(elem_type)
        ns = dict(elem_field=elem_field, length=length)
        return cls._create_specialized_class(f"{cls.__name__}__{elem_type.__name__}__{length}", ns)

    def __init__(self, field_type: type, length: int | str | None = None, **kwargs) -> None:
        super().__init__(field_type, **kwargs)
        if not hasattr(self, "elem_field"):
            self.elem_field = Field._create_field(field_type)
        if length is not None:
            self.length = length
        assert isinstance(self.length, (str, int))

    # @property
    # def fmt(self) -> str:
    #     if isinstance(self.length, int):
    #         try:
    #             if self.is_packing_bytes:
    #                 return f"{self.elem_field.size * self.length}s"
    #             elif self.elem_field.fmt != "|":
    #                 return f"{self.length}{self.elem_field.fmt}"
    #         except struct.error:
    #             # struct.calcsize chokes on any | formats
    #             pass
    #     return "|"

    @property
    def is_packing_bytes(self) -> bool:
        return len(self.elem_field.fmt) != 1

    def get_elem_ctx(self, context: Context) -> Context:
        c = replace(context)
        self.elem_field.pack(c)
        return c

    def pack(self, context: Context) -> None:
        """Registers this field to be included in the pack process."""
        length = self.get_length(context)
        if self.is_packing_bytes:
            size = struct.calcsize(self.get_elem_ctx(context).struct_format)
            context.add(self, struct_format=f"{length*size}s")
        else:
            context.add(self, struct_format=f"{length}{self.elem_field.fmt}")

    def unpack(self, context: Context) -> None:
        """Registers this field to be included in the unpack process."""
        if not isinstance(self.length, int):
            if context.data:
                context.unpack()
            if not context.get(None):
                context.add(self, struct_format="|")
                return

        self.pack(context)

    def pack_value(self, context: Context, value: Any) -> Iterable[PrimitiveType]:
        length = self.get_length(context)
        elem_it = islice(
            chain(value or [], (self.elem_field.type() for _ in range(length))),
            length,
        )
        if self.is_packing_bytes:
            ctx = Context(context.params, tuple(elem_it))
            for idx in range(length):
                with ctx.scope(idx):
                    self.elem_field.pack(ctx)
            yield ctx.pack()
        else:
            values_it = chain.from_iterable(
                self.elem_field.pack_value(context, elem) for elem in elem_it
            )
            yield from values_it

    def unpack_value(self, context: Context, values: Iterator[PrimitiveType]) -> Any:
        length = self.get_length(context)
        if self.is_packing_bytes:
            ctx = Context(context.params, length * [MISSING], next(values))
            for idx in range(length):
                with ctx.scope(idx):
                    self.elem_field.unpack(ctx)
            return ctx.unpack()
        else:
            return [self.elem_field.unpack_value(context, values) for _ in range(length)]

    def get_length(self, context: Context) -> int:
        if isinstance(self.length, int):
            return self.length
        else:
            return context.get(self.length)


T = TypeVar("T")


class array:
    def __class_getitem__(cls, arg: tuple[type[T], int]) -> list[T]:
        elem_type, length = arg
        return Annotated[list[elem_type], ArrayField[elem_type, length]]
