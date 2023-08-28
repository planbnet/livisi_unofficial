"""Code for communication with the Livisi application websocket."""
from collections.abc import Callable
import urllib.parse
from dataclasses import dataclass, fields

import json
import websockets

from .aiolivisi import AioLivisi
from .const import AVATAR_PORT, LOGGER


@dataclass
class LivisiWebsocketEvent:
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
                parsed_json = json.loads(message)
                # Only include keys that are fields in the LivisiWebsocketEvent dataclass
                event_data_dict = {
                    f.name: parsed_json.get(f.name)
                    for f in fields(LivisiWebsocketEvent)
                }
                event_data = LivisiWebsocketEvent(**event_data_dict)
            except json.JSONDecodeError:
                LOGGER.warning("Cannot decode websocket message", exc_info=True)
                continue

            if event_data.properties is None:
                continue

            # remove the url prefix and use just the id (which is unqiue)
            event_data.source = event_data.source.removeprefix("/device/")
            event_data.source = event_data.source.removeprefix("/capability/")

            on_data(event_data)
