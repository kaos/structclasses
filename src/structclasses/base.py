# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
import struct
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import Enum
from typing import Annotated, Any, Iterable, Iterator, get_origin

from typing_extensions import Self


class ByteOrder(Enum):
    NATIVE = "@"
    NATIVE_STANDARD = "="
    LITTLE_ENDIAN = "<"
    BIG_ENDIAN = ">"
    NETWORK = "!"


@dataclass(frozen=True, slots=True)
class Params:
    byte_order: ByteOrder = ByteOrder.BIG_ENDIAN


@dataclass(frozen=True)
class Context:
    params: Params
    obj: Any


class Field(ABC):
    fmt: str
    type: type

    def __init__(self, field_type: type, fmt: str, **kwargs) -> None:
        self.type = field_type

        try:
            self.fmt = fmt.format(**kwargs)
        except KeyError as e:
            raise TypeError(f"structclasses: missing field type option: {e}") from e

    def __repr__(self) -> str:
        field_type = self.type
        fmt = self.fmt
        return f"<{self.__class__.__name__} {field_type=} {fmt=}>"

    def get_format(self, context: Context) -> str:
        return self.fmt

    def get_size(self, context: Context) -> int:
        return struct.calcsize(self.get_format(context))

    @property
    def size(self) -> int:
        return struct.calcsize(self.fmt)

    @abstractmethod
    def prepack(self, value: Any, context: Context) -> Iterable[Any]:
        """Pre-process `value` for pack'ing."""

    @abstractmethod
    def postunpack(self, values: Iterator[Any], context: Context) -> Any:
        """Post-process unpack'ed values for this field."""

    @classmethod
    def _create(cls: type[Self], field_type: type) -> Self:
        raise TypeError(
            f"this may be overridden in a subclass to add support for {field_type=} fields."
        )

    @classmethod
    def _create_field(cls: type[Self], field_type: type | None = None) -> Self:
        if field_type is None:
            field_type = cls

        if (origin_type := get_origin(field_type)) is Annotated:
            for meta in field_type.__metadata__:
                if isinstance(meta, Field):
                    return meta
            return cls._create_field(field_type.__origin__)

        if origin_type is not None:
            raise NotImplementedError(f"generic types not handled yet, got: {field_type}")

        # Try all Field subclasses if there's an implementation for this field type.
        if field_type != cls:
            for sub in Field.__subclasses__():
                try:
                    return sub._create(field_type)
                except TypeError:
                    pass

        raise TypeError(f"structclasses: no field type implementation for {field_type=}")

    @classmethod
    def lookup(cls, key: Any, context: Context) -> Any:
        if callable(key):
            return key(context)
        if isinstance(context.obj, Mapping) and key in context.obj:
            return context.obj[key]
        elif isinstance(key, str):
            if hasattr(context.obj, key):
                return getattr(context.obj, key)
            if "." in key:
                for key_part in key.split("."):
                    context = replace(context, obj=cls.lookup(key_part, context))
                return context.obj
        raise ValueError(f"structclasses: {cls.__name__} can not lookup {key=}.")
