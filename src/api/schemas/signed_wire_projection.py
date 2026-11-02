"""Preserve producer field presence when serializing a signed JSON envelope.

Adding reader defaults changes the hash of a case whose signature commits the
complete wire object. Values are still serialized by Pydantic; only defaults
which were absent from the authenticated envelope are omitted.
"""

from collections.abc import Mapping

from pydantic import BaseModel


def signed_wire_fields(model: object, serialized: object) -> object:
    if isinstance(model, BaseModel) and isinstance(serialized, Mapping):
        return {
            key: signed_wire_fields(getattr(model, key), value)
            for key, value in serialized.items()
            if key in model.model_fields_set
        }
    if isinstance(model, Mapping) and isinstance(serialized, Mapping):
        return {key: signed_wire_fields(model.get(key), value) for key, value in serialized.items()}
    if isinstance(model, (list, tuple)) and isinstance(serialized, list):
        return [signed_wire_fields(item, value) for item, value in zip(model, serialized)]
    return serialized
