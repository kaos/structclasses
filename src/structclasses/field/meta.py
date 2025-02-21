# Copyright (c) 2025 Andreas Stenius
# This software is licensed under the MIT License.
# See the LICENSE file for details.
import inspect
from collections.abc import Mapping
from dataclasses import Field as DataclassField
from dataclasses import field as dataclass_field
from typing import Any

_META_KEY = "__structclass_fieldmeta__"


def field(
    pack_length: str | None = None,
    unpack_length: str | None = None,
    selector: str | None = None,
    field_selector_map: Mapping[str, Any] | None = None,
    **kwargs,
) -> DataclassField:
    scope = locals()
    meta_keys = [
        p.name
        for p in inspect.signature(field).parameters.values()
        if p.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
    ]
    metadata = kwargs.setdefault("metadata", {})
    metadata[_META_KEY] = {key: scope[key] for key in meta_keys if scope[key] is not None}
    return dataclass_field(**kwargs)


def get_field_metadata(field: DataclassField) -> Mapping[str, Any]:
    return field.metadata.get(_META_KEY, {})
