# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
import struct
from collections.abc import Mapping
from itertools import chain, islice
from typing import Annotated, Any, Iterable, Iterator, TypeVar, Union

from structclasses.base import Context, Field
from structclasses.decorator import fields, is_structclass

type PrimitiveType = bytes | int | bool | float | str
# PrimitiveTypeT = TypeVar("PrimitiveTypeT", bound=PrimitiveType)


class PrimitiveField(Field):
    type_map = {
        int: "i",
        bool: "?",
        float: "f",
    }

    @classmethod
    def _create(cls, field_type: type) -> Field:
        return cls(field_type)

    def __init__(self, field_type: type[PrimitiveType], fmt: str | None = None, **kwargs) -> None:
        try:
            if fmt is None:
                fmt = self.type_map[field_type]
        except KeyError as e:
            raise TypeError(
                f"structclasses: {field_type=} is not incompatible with {self.__class__.__name__}."
            ) from e

        super().__init__(field_type, fmt, **kwargs)

    def prepack(self, value: PrimitiveType, context: Context) -> Iterable[PrimitiveType]:
        assert isinstance(value, self.type)
        return (value,)

    def postunpack(self, values: Iterator[PrimitiveType], context: Context) -> PrimitiveType:
        value = next(values)
        assert isinstance(value, self.type)
        return value


int8 = Annotated[int, PrimitiveField(int, "b")]
uint8 = Annotated[int, PrimitiveField(int, "B")]
int16 = Annotated[int, PrimitiveField(int, "h")]
uint16 = Annotated[int, PrimitiveField(int, "H")]
int32 = Annotated[int, PrimitiveField(int, "i")]
uint32 = Annotated[int, PrimitiveField(int, "I")]
int64 = Annotated[int, PrimitiveField(int, "q")]
uint64 = Annotated[int, PrimitiveField(int, "Q")]
long = Annotated[int, PrimitiveField(int, "l")]
ulong = Annotated[int, PrimitiveField(int, "L")]
double = Annotated[float, PrimitiveField(float, "d")]


class BytesField(PrimitiveField):
    type_map = {
        bytes: "{length}s",
        str: "{length}s",
    }

    def __init__(
        self, field_type: type[str | bytes], fmt: str | None = None, length: Any = None, **kwargs
    ) -> None:
        self.length = length
        if not isinstance(length, int):
            fmt = "|"
        super().__init__(field_type, fmt, length=length, **kwargs)

    def get_format(self, context: Context) -> str:
        if self.fmt != "|":
            return self.fmt
        return f"{self.lookup(self.length, context)}s"

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


class RecordField(Field):
    def __init__(self, field_type: type, fields: Mapping[str, Field]) -> None:
        super().__init__(field_type, "".join(fld.fmt for fld in fields.values()))
        self.fields = fields

    @classmethod
    def _create(cls, field_type: type) -> Field:
        if is_structclass(field_type):
            return cls(field_type, dict(fields(field_type)))
        return super()._create(field_type)

    def _get(self, value: Any, key: str) -> Any:
        if isinstance(value, Mapping):
            return value.get(key)
        else:
            return getattr(value, key, None)

    def prepack(self, value: Any, context: Context) -> Iterable[PrimitiveType]:
        assert isinstance(value, self.type)
        return chain.from_iterable(
            fld.prepack(self._get(value, name), context) for name, fld in self.fields.items()
        )

    def postunpack(self, values: Iterator[Any], context: Context) -> Any:
        kwargs = {name: fld.postunpack(values, context) for name, fld in self.fields.items()}
        if issubclass(self.type, Mapping):
            return kwargs
        else:
            return self.type(**kwargs)


ElemT = TypeVar("ElemT", bound=type)


class record:
    def __class_getitem__(cls, arg: tuple[ElemT, tuple[str, type], ...]) -> ElemT:
        container, *field_types = arg
        fields = {name: Field._create_field(field_type) for name, field_type in field_types}
        return Annotated[container, RecordField(container, fields)]


class ArrayField(Field):
    def __init__(self, field_type: type, length: int | str) -> None:
        self.elem_field = Field._create_field(field_type)
        self.length = length
        fmt = "|"
        if isinstance(length, int):
            try:
                if self.is_packing_bytes:
                    fmt = f"{self.elem_field.size * length}s"
                elif self.elem_field.fmt != "|":
                    fmt = f"{length}{self.elem_field.fmt}"
            except struct.error:
                # struct.calcsize chokes on any | formats
                pass
        super().__init__(list, fmt)

    @property
    def is_packing_bytes(self) -> bool:
        return len(self.elem_field.fmt) > 1

    def get_format(self, context: Context) -> str:
        if self.is_packing_bytes:
            return f"{self.elem_field.size * self.get_length(context)}s"
        elif self.fmt == "|":
            return f"{self.get_length(context)}{self.elem_field.fmt}"
        else:
            return self.fmt

    def get_length(self, context: Context) -> int:
        if isinstance(self.length, int):
            return self.length
        if isinstance(context.obj, Mapping) and self.length in context.obj:
            return int(context.obj[self.length])
        elif isinstance(self.length, str) and hasattr(context.obj, self.length):
            return int(getattr(context.obj, self.length))
        else:
            raise ValueError(
                f"structclasses: array length points at unknown field: {self.length!r}"
            )

    def prepack(self, value: Any, context: Context) -> Iterable[PrimitiveType]:
        length = self.get_length(context)
        elem_it = chain(value or [], (self.elem_field.type() for _ in range(length)))
        values_it = chain.from_iterable(
            self.elem_field.prepack(elem, context) for elem in islice(elem_it, length)
        )
        if self.is_packing_bytes:
            return (
                struct.pack(
                    context.params.byte_order.value + length * self.elem_field.fmt, *values_it
                ),
            )
        else:
            return tuple(values_it)

    def postunpack(self, values: Iterator[Any], context: Context) -> Any:
        length = self.get_length(context)
        if self.is_packing_bytes:
            values_it = (
                iter(v)
                for v in struct.iter_unpack(
                    context.params.byte_order.value + self.elem_field.fmt, next(values)
                )
            )
        else:
            values_it = length * (values,)
        return [self.elem_field.postunpack(v, context) for v in values_it]


class array:
    def __class_getitem__(cls, arg: tuple[ElemT, int]) -> list[ElemT]:
        elem_type, length = arg
        return Annotated[list[ElemT], ArrayField(elem_type, length)]


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
        key = self.lookup(self.selector, context)
        if key not in self.fields:
            raise ValueError(f"structclasses: union does not have a field type for {key=}.")
        return self.fields[key]

    def get_format(self, context: Context) -> str:
        return self.get_field(context).get_format(context)


class union:
    def __class_getitem__(cls, arg: tuple[str, tuple[Any, ElemT], ...]) -> Union[ElemT, ...]:
        selector, *options = arg
        fields = {value: Field._create_field(elem_type) for value, elem_type in options}
        return Annotated[Union[*(t for _, t in options)], UnionField(selector, fields)]
