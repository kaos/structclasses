# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from __future__ import annotations

from collections.abc import Mapping
from contextlib import nullcontext
from typing import Annotated, Any, Iterable, Iterator

from structclasses.base import Context, Field, PrimitiveType
from structclasses.decorator import fields, is_structclass, params


class RecordField(Field):
    fmt: str = ""

    def __class_getitem__(cls, fields: tuple[Field, ...]) -> type[RecordField]:
        assert all(isinstance(fld, Field) for fld in fields)
        ns = dict(fields=fields)
        return cls._create_specialized_class(
            f"{cls.__name__}__{len(fields)}_fields", ns, unique=True
        )

    def __init__(
        self,
        field_type: type,
        fields: Iterable[Field] | None = None,
        packed: bool = False,
        **kwargs,
    ) -> None:
        if fields is not None:
            self.fields = tuple(fields)
        assert hasattr(self, "fields")
        self.align = max(fld.align for fld in self.fields)
        self.packed = packed
        super().__init__(field_type, **kwargs)

    @classmethod
    def _create(cls, field_type: type, **kwargs) -> Field:
        if is_structclass(field_type):
            return cls(field_type, fields(field_type), packed=params(field_type).packed, **kwargs)
        return super()._create(field_type, **kwargs)

    def size(self, context: Context | None = None) -> int:
        cm = context.scope(self.name, packed=self.packed) if context is not None else nullcontext()
        with cm:
            if self.packed:
                return sum(fld.size(context) for fld in self.fields)
            size = 0
            for fld in self.fields:
                if size % fld.align != 0:
                    size += fld.align - (size % fld.align)
                size += fld.size(context)
            if size % self.align != 0:
                size += self.align - (size % self.align)
            return size

    def pack(self, context: Context) -> None:
        """Registers this field to be included in the pack process."""
        # No value/processing needed for the container itself, besides ensuring
        # proper alignment around the record data.
        context.align(self.align)
        with context.scope(self.name, packed=self.packed):
            for fld in self.fields:
                fld.pack(context)
        context.align(self.align)

    def unpack(self, context: Context) -> None:
        """Registers this field to be included in the unpack process."""
        context.align(self.align)
        context.get(self.name, default={})
        with context.scope(self.name, packed=self.packed):
            for fld in self.fields:
                fld.unpack(context)
        # Unpack container last, so we can transform the primitive fields into
        # the container object. This also adds alignment padding as needed.
        context.add(self, align=1 if self.packed else self.align)

    def unpack_value(self, context: Context, values: Iterator[PrimitiveType]) -> Any:
        with context.scope(self.name, packed=self.packed):
            kwargs = {fld.name: context.get(fld.name) for fld in self.fields}
        return self.type(**kwargs)


class record:
    def __class_getitem__(cls, arg: tuple[type[Mapping], tuple[str, type], ...]) -> type[Mapping]:
        container, *field_types = arg
        fields = tuple(
            Field._create_field(field_type, name=name) for name, field_type in field_types
        )
        return Annotated[container, RecordField[fields]]
