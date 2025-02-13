# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Annotated, Any, Iterable, Iterator, Union

from structclasses.base import Context, Field
from structclasses.field.primitive import PrimitiveType


class UnionField(Field):
    def __class_getitem__(cls, arg: tuple[str | Callable, Mapping[Any, Field]]) -> type[UnionField]:
        selector, fields = arg
        ns = dict(selector=selector, fields=fields)
        return cls._create_specialized_class(f"{cls.__name__}__{selector}__{len(fields)}", ns)

    def __init__(
        self,
        field_type: type,
        selector: str | None = None,
        fields: Mapping[Any, Field] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(Union, fmt="|", **kwargs)
        if selector is not None:
            self.selector = selector
        if fields is not None:
            self.fields = fields
        assert isinstance(self.selector, (str, Callable))
        assert isinstance(self.fields, Mapping)

    def union_field(self, context: Context) -> Field:
        return self.fields[context.get(self.selector)]

    def pack(self, context: Context) -> None:
        """Registers this field to be included in the pack process."""
        fld = self.union_field(context)
        with context.scope(self.name):
            fld.pack(context)

    def unpack(self, context: Context) -> None:
        """Registers this field to be included in the unpack process."""
        if isinstance(self.selector, str):
            if context.data:
                context.unpack()
            if not context.get(None):
                context.add(self)
                return

        fld = self.union_field(context)
        with context.scope(self.name):
            fld.unpack(context)

    def pack_value(self, context: Context, value: Any) -> Iterable[PrimitiveType]:
        return self.union_field(context).pack_value(context, value)

    def unpack_value(self, context: Context, values: Iterator[PrimitiveType]) -> Any:
        return self.union_field(context).unpack_value(context, values)


class union:
    def __class_getitem__(cls, arg: tuple[str | Callable, tuple[Any, type], ...]) -> Union:
        selector, *options = arg
        fields = {value: Field._create_field(elem_type) for value, elem_type in options}
        # This works in py2.12, but not in py2.10... :/
        # return Annotated[Union[*(t for _, t in options)], UnionField(selector, fields)]
        # Dummy type for now, as we're not running type checking yet any way...
        return Annotated[type, UnionField[selector, fields]]
