# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from __future__ import annotations

import struct
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, replace
from enum import Enum
from typing import Annotated, Any, Iterable, Iterator, get_origin

from typing_extensions import Self

# Marker value to indicate a fields length should be inherited from a superclass.
INHERIT = object()


class IncompatibleFieldTypeError(TypeError):
    pass


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

    @property
    def is_packing(self) -> bool:
        return not isinstance(self.obj, dict)

    def get(self, key: Any) -> Any:
        if callable(key):
            return key(self)
        if isinstance(self.obj, Mapping) and key in self.obj:
            return self.obj[key]
        elif isinstance(key, str):
            if hasattr(self.obj, key):
                return getattr(self.obj, key)
            if "." in key:
                context = self
                for key_part in key.split("."):
                    context = replace(context, obj=context.get(key_part))
                return context.obj
        raise ValueError(f"structclasses: can not lookup {key=} in current context.")

    def set(self, key: Any, value: Any) -> None:
        if callable(key):
            key(self, value)
        if isinstance(self.obj, Mapping) and key in self.obj:
            assert isinstance(value, type(self.obj[key]))
            self.obj[key] = value
        elif isinstance(key, str):
            if hasattr(self.obj, key):
                assert isinstance(value, type(getattr(self.obj, key)))
                setattr(self.obj, key, value)
                return
            if "." in key:
                context = self
                keys = key.split(".")
                for key_part in keys[:-1]:
                    context = replace(context, obj=context.get(key_part))
                context.set(keys[-1], value)
                return
        raise ValueError(f"structclasses: can not set {key=} to {value=} in current context.")


class Field(ABC):
    name: str
    fmt: str
    type: type

    def __init__(self, field_type: type, fmt: str, **kwargs) -> None:
        self.name = "<undef>"
        self.type = field_type

        try:
            self.fmt = fmt.format(**kwargs)
        except KeyError as e:
            raise TypeError(f"structclasses: missing field type option: {e}") from e

    def _register(self, name: str, fields: dict[str, Field], field_meta: dict[str, dict]) -> None:
        self.name = name
        if getattr(self, "length", None) is INHERIT:
            assert (
                name in fields
            ), f"Can not inherit field length for {name=}. No such field found in base class."
            self.length = fields[name].length
        fields[name] = self
        if meta := field_meta[name]:
            self.configure(**meta)

    def __repr__(self) -> str:
        name = self.name
        field_type = self.type
        fmt = self.fmt
        return f"<{self.__class__.__name__} {name=} {field_type=} {fmt=}>"

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
        raise IncompatibleFieldTypeError(
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
                except IncompatibleFieldTypeError:
                    pass

        raise TypeError(f"structclasses: no field type implementation for {field_type=}")

    def configure(self, **kwargs) -> None:
        """Field specific options.

        Provided using field metadata with the `structclasses.field` function.

            from structclasses import field

            @structclass
            class MyStruct:
                foo: uint8
                example: text[8] = field(pack_length="example", unpack_length="foo")
        """
        pass

    def update_related_fieldvalues(self, context: Context) -> None:
        """Called when about to pack data, before the actual prepack calls."""
        pass
