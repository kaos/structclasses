# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from structclasses.base import Context
from structclasses.field.data import BytesField
from structclasses.field.primitive import uint32


def test_text_field_with_length_prefix() -> None:
    fld = BytesField(str, length=32)
    fld.configure(unpack_length=uint32)

    ctx = Context(root="abcdef")
    fld.pack(ctx)
    assert b"\x06\0\0\0abcdef" == ctx.pack()

    ctx = Context(data=ctx.data)
    fld.unpack(ctx)
    assert "abcdef" == ctx.unpack()
