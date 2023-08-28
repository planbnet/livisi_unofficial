"""Code for communication with the Livisi application websocket."""
from collections.abc import Callable
import urllib.parse
from dataclasses import dataclass

import websockets
from pydantic import BaseModel, ValidationError

from .aiolivisi import AioLivisi
from .const import AVATAR_PORT


@dataclass(init=False)
class LivisiWebsocketEvent(BaseModel):
    """Encapuses a livisi event sent via the websocket."""

    namespace: str
    type: str | None
    source: str
    timestamp: str | None
    properties: dict | None


class Websocket:
    """Represents the websocket class."""

    def __init__(self, aiolivisi: AioLivisi) -> None:
        """Initialize the websocket."""
        self.aiolivisi = aiolivisi
        self.connection_url: str = None

    async def connect(self, on_data, on_close, port: int) -> None:
        """Connect to the socket."""
        if port == AVATAR_PORT:
            token = urllib.parse.quote(self.aiolivisi.token)
        else:
            token = self.aiolivisi.token
        ip_address = self.aiolivisi.livisi_connection_data["ip_address"]
        self.connection_url = f"ws://{ip_address}:{port}/events?token={token}"
        try:
            async with websockets.connect(
                self.connection_url, ping_interval=10, ping_timeout=10
            ) as websocket:
                try:
                    self._websocket = websocket
                    await self.consumer_handler(websocket, on_data)
                except Exception:
                    await on_close()
                    return
        except Exception:
            await on_close()
            return

    async def disconnect(self) -> None:
        """Close the websocket."""
        await self._websocket.close(code=1000, reason="Handle disconnect request")

    async def consumer_handler(self, websocket, on_data: Callable):
        """Parse data transmitted via the websocket."""
        async for message in websocket:
            try:
                event_data = LivisiWebsocketEvent.parse_raw(message)
            except ValidationError:
                continue

            # remove the url prefix and use just the id (which is unqiue)
            event_data.source = event_data.source.removeprefix("/device/")
            event_data.source = event_data.source.removeprefix("/capability/")

            if event_data.properties is None:
                continue

            on_data(event_data)
