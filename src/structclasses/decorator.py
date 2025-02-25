# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
import inspect
import struct
from dataclasses import dataclass
from dataclasses import fields as dataclass_fields
from io import BufferedIOBase

from typing_extensions import Self

from structclasses.base import ByteOrder, Context, Field, Params
from structclasses.field.meta import get_field_metadata

_FIELDS = "__structclass_fields__"
_PARAMS = "__structclass_params__"


def is_structclass(obj) -> bool:
    cls = obj if isinstance(obj, type) else type(obj)
    return hasattr(cls, _FIELDS)


def fields(obj) -> tuple[Field, ...]:
    try:
        fields = getattr(obj, _FIELDS)
    except AttributeError:
        raise TypeError("must be called with a structclass type or instance") from None

    return tuple(fields.values())


def structclass(
    cls=None, /, alignment: int | None = None, byte_order: ByteOrder | None = None, **kwargs
):
    def wrap(cls):
        return _process_class(
            dataclass(cls, **kwargs),
            alignment=alignment,
            byte_order=byte_order or ByteOrder.get_default(),
        )

    if cls is None:
        return wrap

    return wrap(cls)


def _process_class(cls, alignment: int | None, byte_order: ByteOrder):
    annotations = inspect.get_annotations(cls, eval_str=True)
    field_meta = {fld.name: get_field_metadata(fld) for fld in dataclass_fields(cls)}
    fields = dict(getattr(cls, _FIELDS, {}))
    align = alignment or 0
    for name, type in annotations.items():
        field = Field._create_field(type, name=name)
        if field is not None:
            field._register(name, fields, field_meta, cls=cls)
            if field.align > align:
                align = field.align

    setattr(cls, _FIELDS, fields)
    setattr(cls, _PARAMS, Params(align, byte_order))
    setattr(cls, "_format", _format(cls=cls))
    setattr(cls, "_pack", _pack)
    setattr(cls, "_unpack", _unpack)
    setattr(cls, "__len__", _len)
    setattr(cls, "__bool__", _bool)
    setattr(cls, "write", _write)
    setattr(cls, "read", _read)

    cls = _register_classlength(cls)

    return cls


def _bool(self) -> bool:
    return True


def _format(cls):
    def _do_format(self=None) -> str:
        if self is not None:
            meth = "pack"
            obj = self
        else:
            meth = "unpack"
            obj = {}
        context = Context(getattr(cls, _PARAMS), obj)
        for fld in getattr(cls, _FIELDS).values():
            getattr(fld, meth)(context)
        return context.struct_format

    return _do_format


# Structclass method.
def _pack(self) -> bytes:
    context = Context(getattr(self, _PARAMS), self)
    for fld in getattr(self, _FIELDS).values():
        fld.pack(context)
    data = context.pack()
    return data


# Structclass method.
@classmethod
def _unpack(cls: type[Self], data: bytes) -> Self:
    context = Context(getattr(cls, _PARAMS), {}, data)
    for fld in getattr(cls, _FIELDS).values():
        fld.unpack(context)
    context.unpack()
    return cls(**context.root)


# Structclass method
def _len(self) -> int:
    return struct.calcsize(self._format())


# Structclass method
def _write(self, io: BufferedIOBase) -> int | None:
    return io.write(self._pack())


# Structclass method
@classmethod
def _read(cls: type[Self], io: BufferedIOBase) -> Self:
    return cls._unpack(io.read())


def _register_classlength(cls) -> type:
    length = struct.calcsize(cls._format())
    meta = type(cls)

    class StructclassType(meta):
        def __len__(self) -> int:
            return length

    return StructclassType(cls.__name__, (cls,), {})
