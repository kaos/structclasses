# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
import pytest

from structclasses import field, structclass, uint8
from structclasses.base import Context
from structclasses.field.data import BytesField, binary, text
from structclasses.field.primitive import uint32


def test_text_field_with_length_prefix() -> None:
    fld = BytesField(str, length=32)
    fld.name = "fld"
    fld.configure(pack_length="fld", unpack_length=uint32)

    ctx = Context(root={"fld": "abcdef"})
    fld.pack(ctx)
    assert b"\x06\0\0\0abcdef" == ctx.pack()

    ctx = Context(data=ctx.data)
    fld.unpack(ctx)
    assert {"fld": "abcdef"} == ctx.unpack()


@pytest.mark.parametrize(
    "atype, field_type_name",
    [
        (binary[8], "BytesField__bytes__8"),
        (text[8], "BytesField__str__8"),
        (text["field_a"], "BytesField__str__field_a"),
    ],
)
def test_data_field_class_name(atype: type, field_type_name: str) -> None:
    field_type = atype.__metadata__[0]
    assert field_type_name == field_type.__name__


def test_embedded_textlen_struct() -> None:
    @structclass
    class S:
        a: text[10] = field(pack_length="a", unpack_length=uint8)
        b: text[10] = field(pack_length="b", unpack_length=uint8)

    s = S("frodo", "baggins")
    assert "=2B" == S._format()
    assert "=B5sB7s" == s._format()
    assert s == S._unpack(s._pack())
