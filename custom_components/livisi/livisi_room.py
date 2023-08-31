"""Code to represent a livisi room."""
from __future__ import annotations
from typing import Any

from dataclasses import dataclass


@dataclass
class LivisiRoom:
    """Stores the livisi room data."""

    id: str
    config: dict[str, Any]
