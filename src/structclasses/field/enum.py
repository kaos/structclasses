# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from __future__ import annotations

from enum import Enum
from typing import Any, Iterable, Iterator

from structclasses.base import Context, Field


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
