"""Code to represent a livisi device."""
from __future__ import annotations
from typing import Any

from dataclasses import dataclass


@dataclass
class LivisiDevice:
    """Stores the livisi device data."""

    id: str
    type: str
    tags: dict[str, str]
    config: dict[str, Any]
    manufacturer: str
    version: str
    cls: str
    product: str
    desc: str
    capabilities: dict[str, str]
    capability_config: dict[str, dict[str, Any]]
    room: str
    battery_low: bool
    update_available: bool
    updated: bool
    unreachable: bool

    @property
    def name(self) -> str:
        """Get name from config."""
        return self.config.get("name")

    @property
    def tag_category(self) -> str:
        """Get tag type category from config."""
        return self.tags.get("typeCategory")

    @property
    def tag_type(self) -> str:
        """Get tag type from config."""
        return self.tags.get("type")
