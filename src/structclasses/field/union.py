# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from __future__ import annotations

import struct
from collections.abc import Callable, Mapping
from typing import Annotated, Any, Iterable, Iterator, Union

from structclasses.base import Context, Field, NestedFieldMixin
from structclasses.field.primitive import PrimitiveType


class UnionFieldError(Exception):
    pass


class UnionValueNotActiveError(AttributeError, UnionFieldError):
    pass


class UnionFieldSelectorMapError(UnionFieldError):
    pass


class UnionField(Field, NestedFieldMixin):
    """Union's are a special breed. At the core, it's like a record, but with only one field at a
    time. Which field though, is the crux. It operates in one of two flavours. Either, the various
    fields is merely an intrepretation of a single binary value, or the various fields result in
    different binary values and only one of them may be used at a time.

    The former mode of operation reflects the standard way of treating unions in C, where as the latter requires a
    additional field outside the union to indicate which union member that is the right one for each case, and the
    encoded size of the union reflects that particular type only, rather then the largest size of all possible values.

    When operating in standard C mode, there's just the data and the fields interpret that data and present it.

    When opertaing with a single dedicated field at a time, there's a "selector" field, used to indicate which field
    is the one to apply at the time. Reading another field is an error, and assigning a value to another field clears
    the data and updates the value of this "selector" field to reflect the change of active field.
    """

    def __class_getitem__(cls, fields: Mapping[str, Field]) -> type[UnionField]:
        ns = dict(fields=fields)
        return cls._create_specialized_class(f"{cls.__name__}__{len(fields)}", ns, unique=True)

    def __init__(
        self,
        field_type: type,
        fields: Mapping[str, Field] | None = None,
        **kwargs,
    ) -> None:
        if fields is not None:
            self.fields = fields
        assert isinstance(self.fields, Mapping)
        self.align = max(fld.align for fld in self.fields.values())
        self.configure()
        super().__init__(Union, **kwargs)

    def _register(
        self, name: str, fields: dict[str, Field], field_meta: dict[str, dict], cls: type, **kwargs
    ) -> None:
        super()._register(name, fields, field_meta, cls=cls, **kwargs)
        # The UnionPrioperty is on the object instance, not the class type, so
        # the descriptor protocol does not kick in here.
        self.property = UnionProperty(self)
        self.property.__set_name__(cls, name)
        setattr(cls, name, self.property)

    def configure(
        self,
        selector: str | None = None,
        field_selector_map: Mapping[str, Any] | None = None,
        **kwargs,
    ) -> UnionField:
        self.selector = selector
        self.field_selector_map = field_selector_map
        size = max(fld.size() for fld in self.fields.values())
        self.fmt = f"{size}s"
        return super().configure(**kwargs)

    def select(self, fld: Field, context: Context) -> None:
        if self.selector is None:
            return
        if self.field_selector_map:
            for field_name, value in self.field_selector_map.items():
                if field_name == fld.name:
                    selected = value
                    break
            else:
                raise UnionFieldSelectorMapError(
                    f"union field {fld.name!r} is missing in field selector map"
                )
        else:
            selected = fld.name
        context.set(self.selector, selected, upsert=True)

    def selected(self, context: Context) -> Field:
        selected = None
        if self.selector is not None:
            selected = context.get(self.selector)
            if self.field_selector_map:
                for field_name, value in self.field_selector_map.items():
                    if value == selected:
                        selected = field_name
                        break
                else:
                    raise UnionFieldSelectorMapError(
                        f"union selector value {selected!r} is missing in field selector map"
                    )
            elif not isinstance(selected, str):
                raise UnionFieldSelectorMapError(
                    f"union selector value {selected!r} must be translated to a union field name using a  field selector map"
                )
        for fld in self.fields.values():
            if selected is None or selected == fld.name:
                return fld
        raise UnionFieldError(f"unknown union member field: {selected!r}")

    def struct_format(self, context: Context) -> str:
        fld = self.selected(context)
        with context.scope(self.name):
            size = fld.size(context)
        return f"{size}s"

    def unpack(self, context: Context) -> None:
        """Registers this field to be included in the unpack process."""
        if self.selector is not None:
            if context.data:
                context.unpack()
            if (vs := context.get(self.selector, default=None)) is None or (
                isinstance(vs, tuple)
                and isinstance(self.selector, (tuple, list))
                and len(vs) == len(self.selector)
                and all(v is None for v in vs)
            ):
                context.add(self, struct_format=self.fmt)
                return

        super().unpack(context)

    def pack_value(self, context: Context, value: Any) -> Iterable[PrimitiveType]:
        if not self.fields:
            return (b"",)
        assert isinstance(value, UnionPropertyValue)
        ctx = context.new(root=value)
        self.selected(context).pack(ctx)
        return (ctx.pack(),)

    def unpack_value(self, context: Context, values: Iterator[PrimitiveType]) -> Any:
        # The unpacking is a little different, as we preserve the binary representation to be unpacked for each
        # union field individually.
        value = next(values)
        assert isinstance(value, bytes)
        return value


class union:
    def __class_getitem__(cls, arg: tuple[tuple[str, type], ...]) -> UnionProperty:
        fields = {name: Field._create_field(elem_type, name=name) for name, elem_type in arg}
        # This works in py2.12, but not in py2.10... :/
        # return Annotated[Union[*(t for _, t in options)], UnionField(selector, fields)]
        # Dummy type for now, as we're not running type checking yet any way...
        return Annotated[UnionProperty, UnionField[fields]]


class UnionPropertyValue:
    __slots__ = ("__union", "__context", "__data", "__values", "__selected")

    def __init__(self, union_field: UnionField, context: Context) -> None:
        object.__setattr__(self, "_UnionPropertyValue__union", union_field)
        object.__setattr__(self, "_UnionPropertyValue__context", context)
        object.__setattr__(self, "_UnionPropertyValue__values", {})
        object.__setattr__(self, "_UnionPropertyValue__selected", None)

    def __repr__(self) -> str:
        return f"{self.__union.name}[{self.__kind__}]<{self.__value__}>"

    def __eq__(self, other) -> bool:
        if not isinstance(other, UnionPropertyValue):
            return False
        if self.__union != other.__union:
            return False
        if self.__kind__ != other.__kind__:
            return False
        if self.__value__ != other.__value__:
            return False
        return True

    @property
    def __kind__(self) -> str | None:
        if self.__union.selector:
            return self.__union.selected(self.__context).name
        else:
            return None

    @property
    def __value__(self) -> Any:
        fld = self.__union.selected(self.__context)
        return getattr(self, fld.name)

    @__value__.setter
    def __value__(self, value: Any) -> None:
        fld = self.__union.selected(self.__context)
        setattr(self, fld.name, value)

    @property
    def __data__(self) -> bytes:
        return self.__data

    @__data__.setter
    def __data__(self, data: bytes) -> None:
        assert isinstance(data, bytes)
        self.__data = data
        self.__values.clear()
        self.__selected = self.__kind__

    def __getattr__(self, name) -> Any:
        if name.startswith("__"):
            return object.__getattribute__(self, name)

        if self.__kind__ not in (name, None):
            raise UnionValueNotActiveError(name)

        fld = self.__union.fields.get(name)
        if fld is None:
            raise AttributeError(name)

        if name not in self.__values:
            if self.__selected != self.__kind__:
                # Reset data if kind changes, to avoid parsing data from unrelated types.
                self.__data__ = b"\0" * fld.size()
            ctx = self.__context.new(root={}, data=self.__data)
            fld.unpack(ctx)
            self.__values[name] = ctx.unpack()[fld.name]

        return self.__values[name]

    def __setattr__(self, name, value) -> None:
        if fld := self.__union.fields.get(name):
            assert isinstance(value, fld.type)
            self.__union.select(fld, self.__context)
            self.__values[name] = value
            ctx = self.__context.new(root=self)
            fld.pack(ctx)
            if self.__union.selector is None:
                size = self.__union.size(self.__context)
            else:
                size = fld.size(ctx)
            self.__data__ = struct.pack(f"{size}s", ctx.pack())
        else:
            super().__setattr__(name, value)


class UnionProperty:
    def __init__(self, union_field: UnionField):
        self.union = union_field

    @property
    def value_attr(self) -> str:
        return f"__union_{self.name}_value"

    def __set_name__(self, owner, name) -> None:
        self.name = name

    def __get__(self, obj, objtype=None) -> UnionPropertyValue:
        if obj is None:
            return self
        else:
            prop = getattr(obj, self.value_attr, None)
            if prop is None:
                prop = UnionPropertyValue(self.union, Context.from_obj(obj))
                setattr(obj, self.value_attr, prop)
            return prop

    def __set__(self, obj, value):
        if isinstance(value, Mapping):
            assert len(value) == 1
            for select, val in value.items():
                setattr(self.__get__(obj), select, val)
        else:
            assert isinstance(value, bytes)
            prop = self.__get__(obj)
            prop.__data__ = value

    def __delete__(self, obj) -> None:
        prop = self.__get__(obj)
        prop.__data__ = b"\0" * len(prop.__data__)
