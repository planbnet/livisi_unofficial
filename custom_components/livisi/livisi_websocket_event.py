"""LivisiWebsocketEvent."""
from dataclasses import dataclass


@dataclass
class LivisiWebsocketEvent:
    """Encapuses a livisi event sent via the websocket."""

    namespace: str
    type: str | None
    source: str
    timestamp: str | None
    properties: dict | None
