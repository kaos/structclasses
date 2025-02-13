# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from __future__ import annotations

import struct
from abc import ABC, abstractmethod
from collections.abc import Mapping, MutableMapping, MutableSequence, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from itertools import chain
from typing import Annotated, Any, Iterable, Iterator, Type, get_origin

from typing_extensions import Self

# Marker value to indicate a fields length should be inherited from a superclass.
INHERIT = object()
MISSING = object()


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


def lookup(obj: Any, attr: str | int, *attrs: str | int) -> Any:
    if isinstance(obj, (Mapping, Sequence)):
        obj = obj[attr]
    elif isinstance(attr, str):
        obj = getattr(obj, attr)
    else:
        raise ValueError(f"can not lookup {attr=} in {obj=}.")
    if obj is MISSING:
        raise KeyError(f"{attr=} is missing in {obj=}.")
    if attrs:
        return lookup(obj, *attrs)
    else:
        return obj


@dataclass
class Context:
    @dataclass(frozen=True)
    class FieldContext:
        field: Field
        struct_format: str
        scope: tuple[str, ...]

    params: Params = field(default_factory=Params)
    root: Any = field(default_factory=dict)
    data: bytes = field(default=b"")
    fields: list[FieldContext] = field(default_factory=list, init=False)
    offset: int = field(init=False, default=0)
    _scope: tuple[str, ...] = field(init=False, default=())

    @contextmanager
    def scope(self, *scope: str) -> None:
        scope = [s for s in scope if s is not None]
        if not scope:
            yield
            return

        try:
            self._scope = (*self._scope, *scope)
            yield
        finally:
            self._scope = self._scope[:-1]

    @property
    def struct_format(self) -> str:
        fmt = "".join(fx.struct_format for fx in self.fields)
        return f"{self.params.byte_order.value}{fmt}"

    def add(self, field: Field, **kwargs) -> None:
        if "struct_format" not in kwargs:
            kwargs["struct_format"] = field.struct_format(self)
        kwargs["scope"] = (*self._scope, *kwargs.get("scope", ()))
        self.fields.append(Context.FieldContext(field, **kwargs))

    def pack(self) -> bytes:
        if self.fields:
            values_it = chain.from_iterable(self._pack_field(fx) for fx in self.fields)
            self.data += struct.pack(self.struct_format, *values_it)
            self.fields = []
        return self.data

    def _pack_field(self, fx: FieldContext) -> Iterable[PrimitiveType]:
        with self.scope(*fx.scope):
            if fx.field.name or self._scope:
                value = self.get(fx.field.name)
            else:
                value = self.root
            return fx.field.pack_value(self, value)

    def unpack(self) -> Any:
        if self.fields:
            fmt = self.struct_format
            values_it = iter(struct.unpack_from(fmt, self.data, self.offset))
            self.offset += struct.calcsize(fmt)
            fields = self.fields
            self.fields = []
            for fx in fields:
                with self.scope(*fx.scope):
                    if (
                        (value := fx.field.unpack_value(self, values_it)) is not None
                        and fx.field.name
                        or self._scope
                    ):
                        self.set(fx.field.name, value, upsert=True)
        return self.root

    def get(self, key: Any, default: Any = MISSING, set_default: bool | None = None) -> Any:
        if callable(key):
            return key()
        if isinstance(key, str):
            attrs = key.split(".")
        elif key is not None:
            attrs = (key,)
        else:
            attrs = ()
        try:
            if not attrs and not self._scope:
                return self.root
            else:
                return lookup(self.root, *self._scope, *attrs)
        except (AttributeError, IndexError, KeyError) as e:
            if default is not MISSING and set_default is not False:
                if set_default is True or default is not None:
                    self.set(key, default, upsert=True)
                return default
            raise ValueError(
                f"structclasses: can not lookup {key=} in current context.\n{self=}\n{type(e).__name__}: {e}"
            )

    def set(self, key: Any, value: Any, upsert: bool = False) -> None:
        if callable(key):
            key(self, value)
            return
        scope = self._scope
        if isinstance(key, str):
            attrs = key.split(".")
        elif key is not None:
            attrs = (key,)
        else:
            assert self._scope
            scope = self._scope[:-2]
            attrs = self._scope[-2:]
        if scope or len(attrs) > 1:
            obj = lookup(self.root, *scope, *attrs[:-1])
        else:
            obj = self.root
        attr = attrs[-1]
        if isinstance(obj, (MutableMapping, MutableSequence)) and (attr in obj or upsert):
            if not upsert:
                assert isinstance(value, type(obj[attr]))
            obj[attr] = value
            return
        elif hasattr(obj, attr) or upsert:
            if not upsert:
                assert isinstance(value, type(getattr(obj, attr)))
            setattr(obj, attr, value)
            return
        raise ValueError(
            f"structclasses: can not set {key=} to {value=} in current context.\n{self=}"
        )


PrimitiveType = Type[bytes | int | bool | float | str]


class Field(ABC):
    name: str | None
    type: type
    fmt: str

    def __init__(self, field_type: type, **kwargs) -> None:
        self.name = kwargs.get("name")
        self.type = field_type
        if "fmt" in kwargs:
            try:
                self.fmt = kwargs["fmt"].format(**kwargs)
            except KeyError as e:
                raise TypeError(f"structclasses: missing field type option: {e}") from e
        # May provide `fmt` as a property.
        assert hasattr(self, "fmt"), f"{self=} is missing `fmt`"

    def struct_format(self, context: Context) -> str:
        return self.fmt

    def configure(self, **kwargs) -> Field:
        """Field specific options.

        Provided using field metadata with the `structclasses.field` function.

            from structclasses import field

            @structclass
            class MyStruct:
                foo: uint8
                example: text[8] = field(pack_length="example", unpack_length="foo")
        """
        return self

    @property
    def size(self) -> int:
        return struct.calcsize(self.fmt)

    def pack(self, context: Context) -> None:
        """Registers this field to be included in the pack process."""
        context.add(self)

    def unpack(self, context: Context) -> None:
        """Registers this field to be included in the unpack process."""
        context.add(self)

    def pack_value(self, context: Context, value: Any) -> Iterable[PrimitiveType]:
        """Return value according to the field's struct format string."""
        raise NotImplementedError

    @abstractmethod
    def unpack_value(self, context: Context, values: Iterator[PrimitiveType]) -> Any:
        """Update context with the unpacked field value."""
        raise NotImplementedError

    @classmethod
    def _create(cls: type[Self], field_type: type, **kwargs) -> Self:
        raise IncompatibleFieldTypeError(
            f"this may be overridden in a subclass to add support for {field_type=} fields."
        )

    def _register(self, name: str, fields: dict[str, Field], field_meta: dict[str, dict]) -> None:
        assert self.name in [None, name]
        self.name = name
        if getattr(self, "length", None) is INHERIT:
            assert (
                self.name in fields
            ), f"Can not inherit field length for {name=}. No such field found in base class."
            self.length = fields[self.name].length
        fields[self.name] = self
        if meta := field_meta[self.name]:
            self.configure(**meta)

    def __repr__(self) -> str:
        name = self.name
        field_type = self.type
        fmt = self.fmt
        return f"<{self.__class__.__name__} {name=} {field_type=} {fmt=}>"

    @classmethod
    def _create_field(cls: type[Self], field_type: type | None = None, **kwargs) -> Self:
        if field_type is None:
            field_type = cls

        if (origin_type := get_origin(field_type)) is Annotated:
            for meta in field_type.__metadata__:
                if isinstance(meta, type) and issubclass(meta, Field):
                    return meta(field_type.__origin__, **kwargs)
            return cls._create_field(field_type.__origin__, **kwargs)

        if origin_type is not None:
            raise NotImplementedError(f"generic types not handled yet, got: {field_type}")

        # Try all Field subclasses if there's an implementation for this field type.
        if field_type != cls:
            for sub in Field.__subclasses__():
                try:
                    return sub._create(field_type, **kwargs)
                except IncompatibleFieldTypeError:
                    pass

        raise TypeError(f"structclasses: no field type implementation for {field_type=}")

    __specialized_classes__ = {}

    @classmethod
    def _create_specialized_class(cls, name: str, ns: Mapping[str, Any]) -> type:
        if name not in Field.__specialized_classes__:
            Field.__specialized_classes__[name] = type(name, (cls,), ns)
        return Field.__specialized_classes__[name]
