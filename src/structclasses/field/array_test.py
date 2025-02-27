# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
import pytest

from structclasses.field.array import array
from structclasses.field.primitive import uint16, uint32


@pytest.mark.parametrize(
    "atype, field_type_name",
    [
        (array[uint16, 3], "ArrayField__3x__PrimitiveField__int__H"),
        (array[uint32, 3], "ArrayField__3x__PrimitiveField__int__I"),
    ],
)
def test_array_field_class_name(atype: type, field_type_name: str) -> None:
    field_type = atype.__metadata__[0]
    assert field_type_name == field_type.__name__
