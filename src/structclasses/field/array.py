# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from __future__ import annotations

from contextlib import nullcontext

# from collections.abc import Mapping
from typing import Annotated, TypeVar

from structclasses.base import MISSING, Context, Field


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
        assert isinstance(self.length, (int, str))
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

    def size(self, context: Context | None = None) -> int:
        if context is None:
            if not isinstance(self.length, int):
                return 0
            else:
                length = self.length
            cm = nullcontext()
        else:
            # Unpack length is always correct at this point, also when packing.
            length = self.get_length(context, self.unpack_length)
            cm = context.scope(self.name)
        with cm:
            size = 0
            for idx in range(length):
                im = context.scope(idx) if context is not None else nullcontext()
                with im:
                    size += self.elem_field.size(context)
        return size

    def get_length(self, context: Context, length: str | int | None) -> int:
        if length is None:
            length = self.length
        if isinstance(length, str):
            length = context.get(
                length, default=self.length, set_default=isinstance(self.length, int)
            )
        if not isinstance(length, int):
            length = len(length)
        if isinstance(self.length, int) and self.length < length:
            raise ValueError(f"{self.name}: field value too long ( {length} > {self.length} )")
        return length

    def pack(self, context: Context) -> None:
        """Registers this field to be included in the pack process."""
        length = self.get_length(context, self.pack_length)
        if isinstance(self.unpack_length, str):
            # Update unpack length field when packing.
            context.set(self.unpack_length, length)
        for idx in range(length):
            with context.scope(self.name, idx):
                self.elem_field.pack(context)

    def unpack(self, context: Context) -> None:
        """Registers this field to be included in the unpack process."""
        if isinstance(self.unpack_length or self.length, str):
            if context.data:
                context.unpack()
            if context.get(self.unpack_length or self.length, default=None) is None:
                if not isinstance(self.length, int):
                    return

        length = self.get_length(context, self.unpack_length)
        context.get(self.name, default=[MISSING] * length)
        for idx in range(length):
            with context.scope(self.name, idx):
                self.elem_field.unpack(context)


T = TypeVar("T")


class array:
    def __class_getitem__(cls, arg: tuple[type[T], int]) -> list[T]:
        elem_type, length = arg
        return Annotated[list[elem_type], ArrayField[elem_type, length]]
