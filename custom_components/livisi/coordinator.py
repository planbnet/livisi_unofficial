"""Code to manage fetching LIVISI data API."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .livisi_errors import LivisiException
from .livisi_device import LivisiDevice
from .livisi_connector import LivisiConnection, connect as livisi_connect
from .livisi_websocket import LivisiWebsocketEvent
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
    """Manage polling plus WebSocket push updates for Livisi."""

    config_entry: ConfigEntry
    aiolivisi: LivisiConnection

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            LOGGER,
            name="Livisi devices",
            update_interval=timedelta(seconds=DEVICE_POLLING_DELAY),
        )
        self.config_entry = config_entry
        self.hass = hass
        self.devices: set[str] = set()
        self.websocket_connected = False
        self.shutdown = False
        self._capability_to_device: dict[str, str] = {}
        self._reconnect_attempts = 0  # consecutive WS failures without data
        self._recover_from_error = False

    # ---------------------------------------------------------------------
    # HA lifecycle
    # ---------------------------------------------------------------------
    async def async_setup(self) -> None:
        """Initialise connection to the Livisi controller."""
        self.aiolivisi = await livisi_connect(
            self.config_entry.data[CONF_HOST],
            self.config_entry.data[CONF_PASSWORD],
        )
        self.shutdown = False

    async def _async_update_data(self) -> list[LivisiDevice]:
        """Poll the controller for device configuration."""
        try:
            LOGGER.debug("Fetching Livisi data")
            return await self.async_get_devices()
        except Exception as exc:
            LOGGER.error("Error fetching Livisi data: %s", exc)
            LOGGER.debug("Marking all devices unreachable due to error")
            for device_id in self.devices:
                self._async_dispatcher_send(
                    LIVISI_REACHABILITY_CHANGE, device_id, False
                )
            self._recover_from_error = True
            raise UpdateFailed(exc) from exc

    # ---------------------------------------------------------------------
    # Dispatcher helpers
    # ---------------------------------------------------------------------
    def _async_dispatcher_send(
        self, event: str, source: str, data: Any, property_name: str | None = None
    ) -> None:
        if data is None:
            return
        topic = f"{event}_{source}"
        if property_name:
            topic += f"_{property_name}"
        async_dispatcher_send(self.hass, topic, data)

    def publish_state(
        self, event_data: LivisiWebsocketEvent, property_name: str
    ) -> bool:
        """Publish a single state property from a WebSocket event."""
        data = event_data.properties.get(property_name)
        if data is None:
            return False
        self._async_dispatcher_send(
            LIVISI_STATE_CHANGE, event_data.source, data, property_name
        )
        return True

    # ---------------------------------------------------------------------
    # Polling
    # ---------------------------------------------------------------------
    async def async_get_devices(self) -> list[LivisiDevice]:
        """Retrieve devices, map capabilities and ensure WS connection."""
        LOGGER.debug("Fetching devices from Livisi API")
        devices = await self.aiolivisi.async_get_devices()
        capability_mapping: dict[str, str] = {}

        for device in devices:
            for cap_id in device.capabilities.values():
                capability_mapping[cap_id] = device.id
            # Mark devices as unreachable if indicated by the API
            # Re-reachability is normally handled by webservice updates
            # (as some devices like WDS incorrectly report as reachable
            # which leads to flapping state when trying to get the current value)
            if device.unreachable or self._recover_from_error:
                self._async_dispatcher_send(
                    LIVISI_REACHABILITY_CHANGE, device.id, not device.unreachable
                )

        self._capability_to_device = capability_mapping

        self._recover_from_error = False

        # (Re-)establish WS if needed
        if not self.websocket_connected:
            LOGGER.info("Not connected, scheduling Livisi WebSocket connection")
            await self.ws_connect()

        return devices

    # ---------------------------------------------------------------------
    # WebSocket event callbacks
    # ---------------------------------------------------------------------
    def on_websocket_data(self, event_data: LivisiWebsocketEvent) -> None:
        """Handle a single event from the Livisi WebSocket."""
        # Any data means connection was good -> reset failure counter
        self._reconnect_attempts = 0

        if event_data.type == LIVISI_EVENT_BUTTON_PRESSED:
            device_id = self._capability_to_device.get(event_data.source)
            if device_id:
                ev = {
                    "device_id": device_id,
                    "type": EVENT_BUTTON_PRESSED,
                    "button_index": event_data.properties.get("index", 0),
                    "press_type": event_data.properties.get("type", "ShortPress"),
                }
                self.hass.bus.async_fire(LIVISI_EVENT, ev)
                self._async_dispatcher_send(LIVISI_EVENT, event_data.source, ev)

        elif event_data.type == LIVISI_EVENT_MOTION_DETECTED:
            device_id = self._capability_to_device.get(event_data.source)
            if device_id:
                ev = {"device_id": device_id, "type": EVENT_MOTION_DETECTED}
                self.hass.bus.async_fire(LIVISI_EVENT, ev)
                self._async_dispatcher_send(LIVISI_EVENT, event_data.source, ev)

        elif event_data.type == LIVISI_EVENT_STATE_CHANGED:
            if IS_REACHABLE in event_data.properties:
                self._async_dispatcher_send(
                    LIVISI_REACHABILITY_CHANGE,
                    event_data.source,
                    event_data.properties[IS_REACHABLE],
                )
            for prop in STATE_PROPERTIES:
                self.publish_state(event_data, prop)

    async def on_websocket_close(self) -> None:
        """Log WebSocket close."""
        LOGGER.debug("Livisi WebSocket on close handler called.")

    # ---------------------------------------------------------------------
    # WebSocket management
    # ---------------------------------------------------------------------
    async def ws_connect(self) -> None:
        """Create the background task that runs the WebSocket loop."""
        self.config_entry.async_create_background_task(
            self.hass, self.ws_loop(), name="livisi_ws"
        )

    async def ws_loop(self) -> None:
        """
        Run the WebSocket listener.

        * Tries one immediate reconnect after a failure.
        * Stops after two consecutive failures without receiving any data.
        * Next successful poll will schedule a fresh connection.
        """
        while True:
            try:
                LOGGER.info(
                    "Connecting to Livisi WebSocket (consecutive failures: %d)",
                    self._reconnect_attempts,
                )
                self.websocket_connected = True

                # Blocks until server closes or raises.
                await self.aiolivisi.listen_for_events(
                    self.on_websocket_data,
                    self.on_websocket_close,
                )
                LOGGER.info("Livisi WebSocket closed by server.")

            except asyncio.CancelledError:
                await self.aiolivisi.websocket.disconnect()
                raise

            except Exception as err:  # unexpected disconnect or connect failure
                LOGGER.warning("WebSocket error: %s", err, exc_info=True)

            # At this point the connection is gone
            self.websocket_connected = False

            # if homeassistant is shutting down, we don't want to reconnect
            if self.shutdown or self.hass.is_stopping:
                self._reconnect_attempts = 0
                LOGGER.info("Livisi WebSocket loop stopped due to shutdown.")
                return

            self._reconnect_attempts += 1
            if self._reconnect_attempts >= 2:
                LOGGER.warning(
                    "Two consecutive WebSocket failures – will wait for next "
                    "successful poll before reconnecting."
                )
                break

            LOGGER.info("Retrying Livisi WebSocket connection shortly…")
            await asyncio.sleep(0.2)
