"""Code to manage fetching LIVISI data API."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from aiohttp import ClientConnectorError

from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .livisi_device import LivisiDevice
from .livisi_connector import LivisiConnection, connect as livisi_connect
from .livisi_websocket import LivisiWebsocketEvent

from .livisi_errors import (
    IncorrectIpAddressException,
    ShcUnreachableException,
    WrongCredentialException,
)


from .const import (
    CONF_HOST,
    CONF_PASSWORD,
    EVENT_BUTTON_PRESSED,
    EVENT_MOTION_DETECTED,
    LIVISI_EVENT,
    LIVISI_REACHABILITY_CHANGE,
    LIVISI_STATE_CHANGE,
    LOGGER,
    DEVICE_POLLING_DELAY,
    STATE_PROPERTIES,
)

from .livisi_const import (
    LIVISI_EVENT_BUTTON_PRESSED,
    LIVISI_EVENT_MOTION_DETECTED,
    LIVISI_EVENT_STATE_CHANGED,
    IS_REACHABLE,
)


class LivisiDataUpdateCoordinator(DataUpdateCoordinator[list[LivisiDevice]]):
    """Class to manage fetching LIVISI data API."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        """Initialize my coordinator."""
        super().__init__(
            hass,
            LOGGER,
            name="Livisi devices",
            update_interval=timedelta(seconds=DEVICE_POLLING_DELAY),
        )
        self.config_entry = config_entry
        self.hass = hass
        self.aiolivisi: LivisiConnection
        self.devices: set[str] = set()
        self._capability_to_device: dict[str, str] = {}

    async def async_setup(self) -> None:
        """Set up the Livisi Smart Home Controller."""
        try:
            self.aiolivisi = await livisi_connect(
                self.config_entry.data[CONF_HOST],
                self.config_entry.data[CONF_PASSWORD],
            )
        except ShcUnreachableException as exception:
            raise ConfigEntryNotReady from exception
        except WrongCredentialException as exception:
            raise ConfigEntryNotReady from exception
        except IncorrectIpAddressException as exception:
            raise ConfigEntryNotReady from exception

    async def _async_update_data(self) -> list[LivisiDevice]:
        """Get device configuration from LIVISI."""
        try:
            return await self.async_get_devices()
        except ClientConnectorError as exc:
            raise UpdateFailed("Failed to get livisi devices from controller") from exc

    def _async_dispatcher_send(self, event: str, source: str, data: Any) -> None:
        if data is not None:
            async_dispatcher_send(self.hass, f"{event}_{source}", data)

    def publish_state(
        self, event_data: LivisiWebsocketEvent, property_name: str
    ) -> bool:
        """Publish a state from the given websocket event property."""
        data = event_data.properties.get(property_name, None)
        if data is None:
            return False
        self._async_dispatcher_send(LIVISI_STATE_CHANGE, event_data.source, data)
        return True

    async def async_get_devices(self) -> list[LivisiDevice]:
        """Set the discovered devices list."""
        devices = await self.aiolivisi.async_get_devices()
        capability_mapping = {}

        for device in devices:
            for capability_id in device.capabilities.values():
                capability_mapping[capability_id] = device.id
            if device.unreachable:
                self._async_dispatcher_send(
                    LIVISI_REACHABILITY_CHANGE, device.id, False
                )

        self._capability_to_device = capability_mapping
        return devices

    def on_websocket_data(self, event_data: LivisiWebsocketEvent) -> None:
        """Define a handler to fire when the data is received."""
        if event_data.type == LIVISI_EVENT_BUTTON_PRESSED:
            device_id = self._capability_to_device.get(event_data.source)
            if device_id is not None:
                livisi_event_data = {
                    "device_id": device_id,
                    "type": EVENT_BUTTON_PRESSED,
                    "button_index": event_data.properties.get("index", 0),
                    "press_type": event_data.properties.get("type", "ShortPress"),
                }
                self.hass.bus.async_fire(LIVISI_EVENT, livisi_event_data)
                self._async_dispatcher_send(
                    LIVISI_EVENT, event_data.source, livisi_event_data
                )
        elif event_data.type == LIVISI_EVENT_MOTION_DETECTED:
            device_id = self._capability_to_device.get(event_data.source)
            if device_id is not None:
                livisi_event_data = {
                    "device_id": device_id,
                    "type": EVENT_MOTION_DETECTED,
                }
                self.hass.bus.async_fire(LIVISI_EVENT, livisi_event_data)
                self._async_dispatcher_send(
                    LIVISI_EVENT, event_data.source, livisi_event_data
                )
        elif event_data.type == LIVISI_EVENT_STATE_CHANGED:
            if IS_REACHABLE in event_data.properties:
                self._async_dispatcher_send(
                    LIVISI_REACHABILITY_CHANGE,
                    event_data.source,
                    event_data.properties.get(IS_REACHABLE),
                )
            for prop in STATE_PROPERTIES:
                self.publish_state(event_data, prop)

    async def on_websocket_close(self) -> None:
        """Define a handler to fire when the websocket is closed."""

        try:
            await self.aiolivisi.listen_for_events(
                self.on_websocket_data, self.on_websocket_close
            )
        except Exception as reconnect_error:
            for device_id in self.devices:
                self._async_dispatcher_send(
                    LIVISI_REACHABILITY_CHANGE, device_id, False
                )
            raise reconnect_error

    async def ws_connect(self) -> None:
        """Connect the websocket."""
        await self.aiolivisi.listen_for_events(
            self.on_websocket_data, self.on_websocket_close
        )
