"""Code for communication with the Livisi application websocket."""

import asyncio
from collections.abc import Callable
import urllib.parse

from json import JSONDecodeError
import websockets.client

from .livisi_json_util import parse_dataclass
from .livisi_const import (
    CLASSIC_WEBSOCKET_PORT,
    LIVISI_EVENT_BUTTON_PRESSED,
    LIVISI_EVENT_MOTION_DETECTED,
    LIVISI_EVENT_STATE_CHANGED,
    V2_WEBSOCKET_PORT,
    LOGGER,
)
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
        """Return whether the webservice is currently connected."""
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
                LOGGER.info("WebSocket connection established.")
                self._websocket = websocket
                await self.consumer_handler(websocket, on_data)
                self._websocket = None
        except Exception as e:
            self._websocket = None
            LOGGER.exception("Error handling websocket connection", exc_info=e)
        if not self._disconnecting:
            LOGGER.warning("WebSocket disconnected unexpectedly.")
        await on_close()

    async def disconnect(self) -> None:
        """Close the websocket."""
        self._disconnecting = True
        if self._websocket is not None:
            await self._websocket.close(code=1000, reason="Handle disconnect request")
            LOGGER.info("WebSocket connection closed.")
            self._websocket = None
        self._disconnecting = False

    async def consumer_handler(self, websocket, on_data: Callable):
        """Parse data transmitted via the websocket."""
        try:
            async for message in websocket:
                LOGGER.debug("Received WebSocket message: %s", message)

                try:
                    event_data = parse_dataclass(message, LivisiWebsocketEvent)
                except JSONDecodeError:
                    LOGGER.warning("Cannot decode WebSocket message", exc_info=True)
                    continue

                if event_data.properties is None or event_data.properties == {}:
                    LOGGER.debug("Received event with no properties, skipping.")
                    LOGGER.debug("Event data: %s", event_data)
                    if event_data.type not in [
                        LIVISI_EVENT_STATE_CHANGED,
                        LIVISI_EVENT_BUTTON_PRESSED,
                        LIVISI_EVENT_MOTION_DETECTED,
                    ]:
                        LOGGER.info(
                            "Received %s event from Livisi websocket", event_data.type
                        )
                    continue

                # Remove the URL prefix and use just the ID (which is unique)
                event_data.source = event_data.source.removeprefix("/device/")
                event_data.source = event_data.source.removeprefix("/capability/")

                try:
                    on_data(event_data)
                except Exception as e:
                    LOGGER.error("Unhandled error in on_data", exc_info=e)

        except asyncio.exceptions.CancelledError:
            LOGGER.warning("Livisi WebSocket consumer handler stopped")
        except Exception as e:
            LOGGER.error("Unhandled error in WebSocket consumer handler", exc_info=e)
