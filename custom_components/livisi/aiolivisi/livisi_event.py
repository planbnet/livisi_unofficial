"""Class for a livisi event, probably we should drop this."""

from dataclasses import dataclass
from pydantic import BaseModel
from typing import Optional


@dataclass(init=False)
class LivisiEvent(BaseModel):
    """Encapuses a livisi event, probably we should drop this."""

    namespace: str
    properties: Optional[dict]
    source: str
    onState: Optional[bool]
    vrccData: Optional[float]
    luminance: Optional[int]
    isReachable: Optional[bool]
    sequenceNumber: Optional[str]
    type: Optional[str]
    timestamp: Optional[str]
    isOpen: Optional[bool]
    keyIndex: Optional[int]
    isLongKeyPress: Optional[bool]
