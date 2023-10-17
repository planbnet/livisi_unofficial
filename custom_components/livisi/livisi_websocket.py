"""Code for communication with the Livisi application websocket."""
from collections.abc import Callable
import urllib.parse

from json import JSONDecodeError
import websockets.client

from .livisi_json_util import parse_dataclass
from .livisi_const import CLASSIC_WEBSOCKET_PORT, V2_WEBSOCKET_PORT, LOGGER
from .livisi_websocket_event import LivisiWebsocketEvent


class LivisiWebsocket:
    """Represents the websocket class."""

    def __init__(self, aiolivisi) -> None:
        """Initialize the websocket."""
        self.aiolivisi = aiolivisi
        self.connection_url: str = None
        self._websocket = None
        self._disconnecting = False

    def is_connected(self):
        """Return whether the webservice is currently connectd."""
        return self._websocket is not None

    async def connect(self, on_data, on_close) -> None:
        """Connect to the socket."""
        if self.aiolivisi.controller.is_v2:
            port = V2_WEBSOCKET_PORT
            token = urllib.parse.quote(self.aiolivisi.token)
        else:
            port = CLASSIC_WEBSOCKET_PORT
            token = self.aiolivisi.token
        ip_address = self.aiolivisi.host
        self.connection_url = f"ws://{ip_address}:{port}/events?token={token}"
        try:
            async with websockets.client.connect(
                self.connection_url, ping_interval=10, ping_timeout=10
            ) as websocket:
                try:
                    self._websocket = websocket
                    await self.consumer_handler(websocket, on_data)
                except Exception:
                    if not self._disconnecting:
                        await on_close()
                    return
        except Exception:
            if not self._disconnecting:
                await on_close()
            return

    async def disconnect(self) -> None:
        """Close the websocket."""
        self._disconnecting = True
        if self._websocket is not None:
            await self._websocket.close(code=1000, reason="Handle disconnect request")
            self._websocket = None
        self._disconnecting = False

    async def consumer_handler(self, websocket, on_data: Callable):
        """Parse data transmitted via the websocket."""
        async for message in websocket:
            LOGGER.debug(message)

            try:
                event_data = parse_dataclass(message, LivisiWebsocketEvent)
            except JSONDecodeError:
                LOGGER.warning("Cannot decode websocket message", exc_info=True)
                continue

            if event_data.properties is None:
                continue

            # remove the url prefix and use just the id (which is unqiue)
            event_data.source = event_data.source.removeprefix("/device/")
            event_data.source = event_data.source.removeprefix("/capability/")

            on_data(event_data)
