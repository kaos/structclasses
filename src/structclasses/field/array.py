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
        arg_type, length = arg
        elem_type, elem_field_type = cls._get_field_type_and_class(arg_type)
        if elem_field_type is not None:
            elem_field = elem_field_type(elem_type)
        else:
            elem_field = Field._create_field(elem_type)
        ns = dict(elem_field=elem_field, length=length)
        return cls._create_specialized_class(
            f"{cls.__name__}__{length}x__{type(elem_field).__name__}", ns
        )

    def __init__(self, field_type: type, length: int | str | None = None, **kwargs) -> None:
        if not hasattr(self, "elem_field"):
            self.elem_field = Field._create_field(field_type)
        self.align = self.elem_field.align
        self.pack_length = None
        self.unpack_length = None
        if length is not None:
            self.length = length
        if isinstance(self.length, int):
            if self.is_packing_bytes:
                kwargs["fmt"] = f"{self.length * self.elem_field.size()}s"
            else:
                kwargs["fmt"] = f"{self.length}{self.elem_field.fmt}"
        else:
            assert isinstance(self.length, str)
        super().__init__(field_type, **kwargs)

    def configure(
        self,
        pack_length: str | None = None,
        unpack_length: str | None = None,
        **kwargs,
    ) -> ArrayField:
        self.pack_length = pack_length
        self.unpack_length = unpack_length
        return super().configure(**kwargs)

    @property
    def is_packing_bytes(self) -> bool:
        return len(self.elem_field.fmt) != 1

    def struct_format(self, context: Context) -> str:
        # Unpack length is always correct at this point, also when packing.
        length = self.get_length(context, self.unpack_length)
        if self.is_packing_bytes:
            with context.scope(self.name):
                size = 0
                for idx in range(length):
                    with context.scope(idx):
                        size += self.elem_field.size(context)
            return f"{size}s"
        else:
            return f"{length}{self.elem_field.struct_format(context)}"

    def get_length(self, context: Context, length: str | int | None) -> int:
        if length is None:
            length = self.length
        if isinstance(length, str):
            length = context.get(length)
        if not isinstance(length, int):
            length = len(length)
        if isinstance(self.length, int) and self.length < length:
            raise ValueError(f"{self.name}: field value too long ( {length} > {self.length} )")
        return length

    def pack(self, context: Context) -> None:
        """Registers this field to be included in the pack process."""
        if isinstance(self.unpack_length, str):
            # Update unpack length field when packing.
            context.set(self.unpack_length, self.get_length(context, self.pack_length))
        context.add(self)

    def unpack(self, context: Context) -> None:
        """Registers this field to be included in the unpack process."""
        if isinstance(self.unpack_length or self.length, str):
            if context.data:
                context.unpack()
            if context.get(self.unpack_length or self.length, default=None) is None:
                context.add(self, struct_format=self.fmt)
                return

        context.add(self)

    def pack_value(self, context: Context, value: Any) -> Iterable[PrimitiveType]:
        length = self.get_length(context, self.pack_length)
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
        length = self.get_length(context, self.unpack_length)
        if self.is_packing_bytes:
            ctx = Context(context.params, length * [MISSING], next(values))
            for idx in range(length):
                with ctx.scope(idx):
                    self.elem_field.unpack(ctx)
            return ctx.unpack()
        else:
            return [self.elem_field.unpack_value(context, values) for _ in range(length)]


T = TypeVar("T")


class array:
    def __class_getitem__(cls, arg: tuple[type[T], int]) -> list[T]:
        elem_type, length = arg
        return Annotated[list[elem_type], ArrayField[elem_type, length]]
