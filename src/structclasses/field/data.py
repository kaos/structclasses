# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from __future__ import annotations

from typing import Annotated, Any, Iterable, Iterator

from structclasses.base import Context
from structclasses.field.primitive import PrimitiveField


class BytesField(PrimitiveField):
    type_map = {
        bytes: "{length}s",
        str: "{length}s",
    }

    def __init__(
        self, field_type: type[str | bytes], fmt: str | None = None, length: Any = None, **kwargs
    ) -> None:
        self.length = length
        if not isinstance(length, int):
            fmt = "|"
        super().__init__(field_type, fmt, length=length, **kwargs)

    def get_format(self, context: Context) -> str:
        if self.fmt != "|":
            return self.fmt
        return f"{self.lookup(self.length, context)}s"

    def prepack(self, value: str | bytes, context: Context) -> Iterable[bytes]:
        assert isinstance(value, self.type)
        if isinstance(value, str):
            value = value.encode()
        return (value,)

    def postunpack(self, values: Iterator[bytes], context: Context) -> str | bytes:
        value = next(values)
        if issubclass(self.type, str):
            value = value.decode().split("\0", 1)[0]
        assert isinstance(value, self.type)
        return value


class text:
    def __class_getitem__(cls, arg) -> str:
        return Annotated[str, BytesField(str, length=arg)]


class binary:
    def __class_getitem__(cls, arg) -> bytes:
        return Annotated[bytes, BytesField(bytes, length=arg)]
