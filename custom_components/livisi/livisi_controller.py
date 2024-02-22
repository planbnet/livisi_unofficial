"""Code to represent a livisi device."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LivisiController:
    """Stores the livisi controller data."""

    controller_type: str
    serial_number: str
    os_version: str

    is_v2: bool
    is_v1: bool
