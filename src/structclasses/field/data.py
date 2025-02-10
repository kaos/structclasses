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
        self.pack_length = None
        self.unpack_length = None
        if not isinstance(length, int):
            fmt = "|"
        super().__init__(field_type, fmt, length=length, **kwargs)

    def configure(
        self, pack_length: str | None = None, unpack_length: str | None = None, **kwargs
    ) -> BytesField:
        self.pack_length = pack_length
        self.unpack_length = unpack_length
        if self.pack_length or self.unpack_length:
            self.fmt = "|"
        return super().configure(**kwargs)

    def get_format(self, context: Context) -> str:
        if self.fmt != "|":
            return self.fmt
        if self.pack_length and context.is_packing:
            k = self.pack_length
        elif self.unpack_length and not context.is_packing:
            k = self.unpack_length
        else:
            k = self.length
        v = context.get(k)
        if not isinstance(v, int):
            v = len(v)
        if isinstance(self.length, int) and v > self.length:
            raise ValueError(
                f"data does not fit in field. Field size {self.length} is less than data length {v}"
            )
        return f"{v}s"

    def update_related_fieldvalues(self, context: Context) -> None:
        if not self.unpack_length:
            return
        key = self.pack_length or self.length
        if not isinstance(key, int):
            key = context.get(key)
        if not isinstance(key, int):
            key = len(key)
        context.set(self.unpack_length, key)

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
