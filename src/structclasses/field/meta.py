# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
from collections.abc import Mapping
from dataclasses import Field as DataclassField
from dataclasses import field as dataclass_field
from typing import Any

_META_KEY = "__structclass_fieldmeta__"


def field(
    pack_length: str | None = None, unpack_length: str | None = None, **kwargs
) -> DataclassField:
    scope = locals()
    metadata = kwargs.setdefault("metadata", {})
    metadata[_META_KEY] = {
        key: scope[key] for key in ("pack_length", "unpack_length") if scope[key] is not None
    }
    return dataclass_field(**kwargs)


def get_field_metadata(field: DataclassField) -> Mapping[str, Any]:
    return field.metadata.get(_META_KEY, {})
