# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from __future__ import annotations

from typing import Annotated, Any, Iterable, Iterator

from structclasses.base import Context, Field, IncompatibleFieldTypeError, PrimitiveType


class PrimitiveField(Field):
    type_map = {
        int: "i",
        bool: "?",
        float: "f",
    }

    def __class_getitem__(cls, arg: tuple[PrimitiveType, str]) -> type[PrimitiveField]:
        ns = dict(type_map=dict((arg,)))
        return cls._create_specialized_class(f"{cls.__name__}__{arg[0].__name__}__{arg[1]}", ns)

    @classmethod
    def _create(cls, field_type: type, **kwargs) -> Field:
        return cls(field_type, **kwargs)

    def __init__(self, field_type: type[PrimitiveType], fmt: str | None = None, **kwargs) -> None:
        try:
            if fmt is None:
                fmt = self.type_map[field_type]
        except KeyError as e:
            raise IncompatibleFieldTypeError(
                f"structclasses: {field_type=} is not compatible with {self.__class__.__name__}."
            ) from e

        super().__init__(field_type, fmt=fmt, **kwargs)

    def pack_value(self, context: Context, value: Any) -> Iterable[PrimitiveType]:
        assert isinstance(value, self.type)
        return (value,)

    def unpack_value(self, context: Context, values: Iterator[PrimitiveType]) -> Any:
        value = next(values)
        assert isinstance(value, self.type)
        return value


int8 = Annotated[int, PrimitiveField[int, "b"]]
uint8 = Annotated[int, PrimitiveField[int, "B"]]
int16 = Annotated[int, PrimitiveField[int, "h"]]
uint16 = Annotated[int, PrimitiveField[int, "H"]]
int32 = Annotated[int, PrimitiveField[int, "i"]]
uint32 = Annotated[int, PrimitiveField[int, "I"]]
int64 = Annotated[int, PrimitiveField[int, "q"]]
uint64 = Annotated[int, PrimitiveField[int, "Q"]]
long = Annotated[int, PrimitiveField[int, "l"]]
ulong = Annotated[int, PrimitiveField[int, "L"]]
double = Annotated[float, PrimitiveField[float, "d"]]
