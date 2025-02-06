# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any, Iterable, Iterator, Union

from structclasses.base import Context, Field
from structclasses.field.record import ElemT


class UnionField(Field):
    def __init__(self, selector: str, fields: Mapping[Any, Field]) -> None:
        self.selector = selector
        self.fields = fields
        super().__init__(Union, "|")

    def prepack(self, value: Any, context: Context) -> Iterable[PrimitiveType]:
        return self.get_field(context).prepack(value, context)

    def postunpack(self, values: Iterator[Any], context: Context) -> Any:
        return self.get_field(context).postunpack(values, context)

    def get_field(self, context: Context) -> Field:
        key = context.get(self.selector)
        if key not in self.fields:
            raise ValueError(f"structclasses: union does not have a field type for {key=}.")
        return self.fields[key]

    def get_format(self, context: Context) -> str:
        return self.get_field(context).get_format(context)


class union:
    def __class_getitem__(cls, arg: tuple[str, tuple[Any, ElemT], ...]) -> ElemT | ...:
        selector, *options = arg
        fields = {value: Field._create_field(elem_type) for value, elem_type in options}
        # This works in py2.12, but not in py2.10... :/
        # return Annotated[Union[*(t for _, t in options)], UnionField(selector, fields)]
        # Dummy type for now, as we're not running type checking yet any way...
        return Annotated[ElemT, UnionField(selector, fields)]
