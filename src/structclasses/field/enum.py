# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from __future__ import annotations

from enum import Enum
from typing import Any, Iterable, Iterator

from structclasses.base import Context, Field, PrimitiveType


class EnumField(Field):
    @classmethod
    def _create(cls, field_type: type, **kwargs) -> Field:
        if issubclass(field_type, Enum):
            return cls(field_type, **kwargs)
        else:
            return super()._create(field_type, **kwargs)

    def __init__(self, field_type: type[Enum], **kwargs) -> None:
        self.member_type_field = Field._create_field(type(next(iter(field_type)).value))
        super().__init__(field_type, fmt=self.member_type_field.fmt, **kwargs)

    def pack_value(self, context: Context, value: Any) -> Iterable[PrimitiveType]:
        assert isinstance(value, self.type)
        return self.member_type_field.pack_value(context, value.value)

    def unpack_value(self, context: Context, values: Iterator[Any]) -> Any:
        return self.type(self.member_type_field.unpack_value(context, values))
