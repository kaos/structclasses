# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
import inspect
import struct
from collections.abc import ItemsView, Iterator
from dataclasses import dataclass
from dataclasses import fields as dataclass_fields
from dataclasses import is_dataclass
from functools import partial
from itertools import chain
from typing import Iterable

from typing_extensions import Self

from structclasses.base import ByteOrder, Context, Field, Params
from structclasses.field.meta import get_field_metadata

_FIELDS = "__structclass_fields__"
_PARAMS = "__structclass_params__"


def is_structclass(obj) -> bool:
    cls = obj if isinstance(obj, type) else type(obj)
    return hasattr(cls, _FIELDS)


def fields(obj) -> Iterable[tuple[str, Field]]:
    try:
        fields = getattr(obj, _FIELDS)
    except AttributeError:
        raise TypeError("must be called with a structclass type or instance") from None

    return tuple(fields.items())


def structclass(cls=None, /, byte_order: ByteOrder = ByteOrder.BIG_ENDIAN, **kwargs):
    def wrap(cls):
        if not is_dataclass(cls):
            cls = dataclass(cls, **kwargs)
        return _process_class(cls, byte_order=byte_order)

    if cls is None:
        return wrap

    return wrap(cls)


def _process_class(cls, byte_order: ByteOrder):
    annotations = inspect.get_annotations(cls, eval_str=True)
    field_meta = {fld.name: get_field_metadata(fld) for fld in dataclass_fields(cls)}
    fields = {}
    for name, type in annotations.items():
        field = Field._create_field(type)
        if field is not None:
            fields[name] = field
            if meta := field_meta[name]:
                field.configure(**meta)

    setattr(cls, _FIELDS, fields)
    setattr(cls, _PARAMS, Params(byte_order))
    setattr(cls, "_format", partial(_format, cls=cls))
    setattr(cls, "_pack", _pack)
    setattr(cls, "_unpack", _unpack)
    setattr(cls, "__len__", _len)
    return cls


# Structclass method. (`cls` is auto-injected, so always present and valid.)
def _format(self=None, *, cls, context: Context | None = None) -> str:
    obj = self or cls
    params = context.params if context else getattr(obj, _PARAMS)
    fmt = [params.byte_order.value]
    fields_it = getattr(obj, _FIELDS).values()
    if context is None:
        fmt.extend(fld.fmt for fld in fields_it)
    else:
        fmt.extend(fld.get_format(context) for fld in fields_it)
    return "".join(fmt)


# Structclass method.
def _pack(self) -> bytes:
    context = Context(getattr(self, _PARAMS), self)
    fields = getattr(self, _FIELDS)
    for field in fields.values():
        field.update_related_fieldvalues(context)
    values = chain.from_iterable(
        fld.prepack(getattr(self, name), context) for name, fld in fields.items()
    )
    return struct.pack(self._format(context=context), *values)


# Structclass method.
@classmethod
def _unpack(cls: type[Self], data: bytes) -> Self:
    offset = 0
    kwargs = {}
    context = Context(getattr(cls, _PARAMS), kwargs)
    for fmt, fields in _unpack_field_group(getattr(cls, _FIELDS).items(), context):
        values_it = iter(struct.unpack_from(fmt, data, offset))
        offset += struct.calcsize(fmt)
        for name, fld in fields:
            kwargs[name] = fld.postunpack(values_it, context)
    return cls(**kwargs)


def _unpack_field_group(
    fields_view: ItemsView[str, Field], context: Context
) -> Iterator[tuple[str, list[tuple[str, Field]]]]:
    fields = []
    fmt = [context.params.byte_order.value]
    for name, fld in fields_view:
        if fld.fmt == "|":
            yield ("".join(fmt), fields)
            fields.clear()
            fmt = fmt[:1]
        fields.append((name, fld))
        fmt.append(fld.get_format(context))
    if fields:
        yield ("".join(fmt), fields)


# Structclass method
def _len(self) -> int:
    context = Context(getattr(self, _PARAMS), self)
    return struct.calcsize(self._format(context=context))
