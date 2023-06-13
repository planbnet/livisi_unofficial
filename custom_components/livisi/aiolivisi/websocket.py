"""Code for communication with the Livisi application websocket."""
from collections.abc import Callable
import urllib.parse

import websockets
from pydantic import ValidationError

from .aiolivisi import AioLivisi
from .livisi_event import LivisiEvent

from .const import (
    AVATAR_PORT,
    IS_REACHABLE,
    ON_STATE,
    VALUE,
    IS_OPEN,
    SET_POINT_TEMPERATURE,
    POINT_TEMPERATURE,
    HUMIDITY,
    TEMPERATURE,
    LUMINANCE,
    KEY_INDEX,
    KEY_PRESS_LONG,
    KEY_PRESS_TYPE,
    EVENT_BUTTON_PRESSED,
    EVENT_STATE_CHANGED,
)


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
                event_data = LivisiEvent.parse_raw(message)
            except ValidationError:
                continue

            if "device" in event_data.source:
                event_data.source = event_data.source.replace("/device/", "")
            if event_data.properties is None:
                continue

            if event_data.type == EVENT_STATE_CHANGED:
                if ON_STATE in event_data.properties:
                    event_data.onState = event_data.properties.get(ON_STATE)
                elif VALUE in event_data.properties and isinstance(
                    event_data.properties.get(VALUE), bool
                ):
                    event_data.onState = event_data.properties.get(VALUE)
                if SET_POINT_TEMPERATURE in event_data.properties:
                    event_data.vrccData = event_data.properties.get(
                        SET_POINT_TEMPERATURE
                    )
                elif POINT_TEMPERATURE in event_data.properties:
                    event_data.vrccData = event_data.properties.get(POINT_TEMPERATURE)
                elif TEMPERATURE in event_data.properties:
                    event_data.vrccData = event_data.properties.get(TEMPERATURE)
                elif HUMIDITY in event_data.properties:
                    event_data.vrccData = event_data.properties.get(HUMIDITY)
                if LUMINANCE in event_data.properties:
                    event_data.luminance = event_data.properties.get(LUMINANCE)
                if IS_REACHABLE in event_data.properties:
                    event_data.isReachable = event_data.properties.get(IS_REACHABLE)
                if IS_OPEN in event_data.properties:
                    event_data.isOpen = event_data.properties.get(IS_OPEN)
            elif event_data.type == EVENT_BUTTON_PRESSED:
                if KEY_INDEX in event_data.properties:
                    event_data.keyIndex = event_data.properties.get(KEY_INDEX)
                    event_data.isLongKeyPress = (
                        event_data.properties.get(KEY_PRESS_TYPE) == KEY_PRESS_LONG
                    )
            on_data(event_data)
