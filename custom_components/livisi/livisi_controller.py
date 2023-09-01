"""Code to represent a livisi device."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class LivisiController:
    """Stores the livisi controller data."""

    controller_type: str
    serial_number: str
    os_version: str

    gateway: dict[str, Any]

    is_v2: bool
