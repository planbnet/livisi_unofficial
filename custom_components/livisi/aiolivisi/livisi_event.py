"""Class for a livisi event, probably we should drop this."""

from dataclasses import dataclass
from pydantic import BaseModel


@dataclass(init=False)
class LivisiEvent(BaseModel):
    """Encapuses a livisi event, probably we should drop this."""

    namespace: str
    properties: dict | None
    source: str
    onState: bool | None
    vrccData: float | None
    luminance: int | None
    isReachable: bool | None
    sequenceNumber: str | None
    type: str | None
    timestamp: str | None
    isOpen: bool | None
    keyIndex: int | None
    isLongKeyPress: bool | None
