# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, Iterable, Iterator

from structclasses.base import Context, Field, PrimitiveType
from structclasses.decorator import fields, is_structclass


class RecordField(Field):
    fmt: str = ""

    def __class_getitem__(cls, fields: tuple[Field, ...]) -> type[RecordField]:
        assert all(isinstance(fld, Field) for fld in fields)
        ns = dict(fields=fields)
        return cls._create_specialized_class(f"{cls.__name__}__{len(fields)}_fields", ns)

    def __init__(self, field_type: type, fields: Iterable[Field] | None = None, **kwargs) -> None:
        if fields is not None:
            self.fields = tuple(fields)
        assert hasattr(self, "fields")
        super().__init__(field_type, **kwargs)

    # @property
    # def fmt(self) -> str:
    #     return "".join(fld.fmt for fld in self.fields)

    # def struct_format(self, context: Context) -> str:
    #     return ""

    @classmethod
    def _create(cls, field_type: type, **kwargs) -> Field:
        if is_structclass(field_type):
            return cls(field_type, fields(field_type), **kwargs)
        return super()._create(field_type, **kwargs)

    def pack(self, context: Context) -> None:
        """Registers this field to be included in the pack process."""
        # No value/processing needed for the container itself.
        # context.add(self)
        with context.scope(self.name):
            for fld in self.fields:
                fld.pack(context)

    def unpack(self, context: Context) -> None:
        """Registers this field to be included in the unpack process."""
        context.get(self.name, default={})
        with context.scope(self.name):
            for fld in self.fields:
                fld.unpack(context)
        # Unpack container last, so we can transform the primitive fields into
        # the container object.
        context.add(self)

    def unpack_value(self, context: Context, values: Iterator[PrimitiveType]) -> Any:
        with context.scope(self.name):
            kwargs = {fld.name: context.get(fld.name) for fld in self.fields}
        return self.type(**kwargs)


class record:
    def __class_getitem__(cls, arg: tuple[type[Mapping], tuple[str, type], ...]) -> type[Mapping]:
        container, *field_types = arg
        fields = tuple(
            Field._create_field(field_type, name=name) for name, field_type in field_types
        )
        return Annotated[container, RecordField[fields]]
