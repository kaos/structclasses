# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from __future__ import annotations

from typing import Annotated, Generic, Iterable, Iterator, Type, TypeVar

from structclasses.base import Context, Field, IncompatibleFieldTypeError
from structclasses.field.array import array

PrimitiveType = Type[bytes | int | bool | float | str]
T = TypeVar("T", bound=PrimitiveType)


class PrimitiveField(Field, array):
    type_map = {
        int: "i",
        bool: "?",
        float: "f",
    }

    @classmethod
    def _create(cls, field_type: type) -> Field:
        return cls(field_type)

    def __init__(self, field_type: type[T], fmt: str | None = None, **kwargs) -> None:
        try:
            if fmt is None:
                fmt = self.type_map[field_type]
        except KeyError as e:
            raise IncompatibleFieldTypeError(
                f"structclasses: {field_type=} is not compatible with {self.__class__.__name__}."
            ) from e

        super().__init__(field_type, fmt, **kwargs)

    def prepack(self, value: T, context: Context) -> Iterable[T]:
        assert isinstance(value, self.type)
        return (value,)

    def postunpack(self, values: Iterator[T], context: Context) -> T:
        value = next(values)
        assert isinstance(value, self.type)
        return value


int8 = Annotated[int, PrimitiveField(int, "b")]
uint8 = Annotated[int, PrimitiveField(int, "B")]
int16 = Annotated[int, PrimitiveField(int, "h")]
uint16 = Annotated[int, PrimitiveField(int, "H")]
int32 = Annotated[int, PrimitiveField(int, "i")]
uint32 = Annotated[int, PrimitiveField(int, "I")]
int64 = Annotated[int, PrimitiveField(int, "q")]
uint64 = Annotated[int, PrimitiveField(int, "Q")]
long = Annotated[int, PrimitiveField(int, "l")]
ulong = Annotated[int, PrimitiveField(int, "L")]
double = Annotated[float, PrimitiveField(float, "d")]
