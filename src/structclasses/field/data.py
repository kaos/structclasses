# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from __future__ import annotations

from typing import Annotated, Any, Iterable, Iterator

from structclasses.base import Context, Field
from structclasses.field.primitive import PrimitiveField


class BytesField(PrimitiveField):
    align: int = 1
    type_map = {
        bytes: "{length}s",
        str: "{length}s",
    }

    def __class_getitem__(cls, arg: tuple[type[str, bytes], str | int]) -> type[BytesField]:
        field_type, length = arg
        ns = dict(type_map={field_type: "{length}s"}, length=length)
        return cls._create_specialized_class(f"{cls.__name__}__{field_type.__name__}__{length}", ns)

    def __init__(self, field_type: type[str | bytes], length: Any = None, **kwargs) -> None:
        if length is not None:
            self.length = length
        self.pack_length = None
        self.unpack_length = None
        if not isinstance(self.length, int):
            kwargs["fmt"] = ""
        super().__init__(field_type, length=self.length, **kwargs)

    def configure(
        self, pack_length: str | None = None, unpack_length: str | None = None, **kwargs
    ) -> BytesField:
        if unpack_length and not isinstance(unpack_length, (str, int)):
            unpack_length = self._create_field(unpack_length)
        self.pack_length = pack_length
        self.unpack_length = unpack_length
        return super().configure(**kwargs)

    def struct_format(self, context: Context) -> str:
        if isinstance(self.unpack_length, Field):
            # Encode the length value to be packed into the data stream.
            prefix = self.unpack_length.struct_format(context)
        else:
            prefix = ""
        # Unpack length is always correct at this point, also when packing.
        return f"{prefix}{self.get_length(context, self.unpack_length)}s"

    def get_length(self, context: Context, length: str | int | None) -> int:
        if length is None:
            length = self.length
        if isinstance(length, str):
            length = context.get(length)
        elif isinstance(length, Field):
            length = len(context.get(self.name))
        if not isinstance(length, int):
            length = len(length)
        if isinstance(self.length, int) and self.length < length:
            raise ValueError(f"{self.name}: field value too long ( {length} > {self.length} )")
        return length

    def pack(self, context: Context) -> None:
        """Registers this field to be included in the pack process."""
        if isinstance(self.unpack_length, str):
            # Update unpack length field when packing.
            context.set(self.unpack_length, self.get_length(context, self.pack_length))
        context.add(self)

    def unpack(self, context: Context) -> None:
        """Registers this field to be included in the unpack process."""
        if isinstance(self.unpack_length or self.length, str):
            if context.data:
                context.unpack()
            if context.get(self.unpack_length or self.length, default=None) is None:
                context.add(self, struct_format=self.fmt)
                return

        if isinstance(self.unpack_length, Field):
            fmt = self.unpack_length.struct_format(context)
        else:
            # Our struct_format gives both the length fmt and our data fmt, but
            # when unpacking, we need to unpack the length first, or we won't
            # know how much of data there is.
            fmt = self.struct_format(context)
        context.add(self, struct_format=fmt)

    def pack_value(self, context: Context, value: Any) -> Iterable[bytes]:
        assert isinstance(value, self.type)
        if isinstance(value, str):
            value = value.encode()
        if isinstance(self.unpack_length, Field):
            return (*self.unpack_length.pack_value(context, len(value)), value)
        else:
            return (value,)

    def unpack_value(self, context: Context, values: Iterator[bytes]) -> Any:
        if isinstance(self.unpack_length, Field):
            length = next(values)
            value = next(context.unpack_next(f"{length}s"))
        else:
            value = next(values)
        if issubclass(self.type, str):
            value = value.decode().split("\0", 1)[0]
        assert isinstance(value, self.type)
        return value


class text:
    def __class_getitem__(cls, arg) -> str:
        length = arg
        return Annotated[str, BytesField[str, length]]


class binary:
    def __class_getitem__(cls, arg) -> bytes:
        length = arg
        return Annotated[bytes, BytesField[bytes, length]]
