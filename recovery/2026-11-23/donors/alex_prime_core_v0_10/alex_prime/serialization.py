from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any


def to_jsonable(value: Any) -> Any:
    """Recursively convert dataclasses/enums into JSON-safe structures.

    Dataclasses and nested enums need deterministic export for audit bundles, roles, commands, and test fixtures.
    """
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: to_jsonable(val) for key, val in asdict(value).items()}
    if isinstance(value, dict):
        return {str(to_jsonable(key)): to_jsonable(val) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]
    return value
