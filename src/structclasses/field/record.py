# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from __future__ import annotations

from collections.abc import Mapping
from itertools import chain
from typing import Annotated, Any, Iterable, Iterator, TypeVar

from structclasses.base import Context, Field
from structclasses.decorator import fields, is_structclass


class RecordField(Field):
    def __init__(self, field_type: type, fields: Mapping[str, Field]) -> None:
        super().__init__(field_type, "".join(fld.fmt for fld in fields.values()))
        self.fields = fields

    @classmethod
    def _create(cls, field_type: type) -> Field:
        if is_structclass(field_type):
            return cls(field_type, dict(fields(field_type)))
        return super()._create(field_type)

    def _get(self, value: Any, key: str) -> Any:
        if isinstance(value, Mapping):
            return value.get(key)
        else:
            return getattr(value, key, None)

    def prepack(self, value: Any, context: Context) -> Iterable[PrimitiveType]:
        assert isinstance(value, self.type)
        return chain.from_iterable(
            fld.prepack(self._get(value, name), context) for name, fld in self.fields.items()
        )

    def postunpack(self, values: Iterator[Any], context: Context) -> Any:
        kwargs = {name: fld.postunpack(values, context) for name, fld in self.fields.items()}
        if issubclass(self.type, Mapping):
            return kwargs
        else:
            return self.type(**kwargs)


ElemT = TypeVar("ElemT", bound=type)


class record:
    def __class_getitem__(cls, arg: tuple[ElemT, tuple[str, type], ...]) -> ElemT:
        container, *field_types = arg
        fields = {name: Field._create_field(field_type) for name, field_type in field_types}
        return Annotated[container, RecordField(container, fields)]
