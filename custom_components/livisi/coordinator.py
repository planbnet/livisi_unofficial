"""Code to manage fetching LIVISI data API."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any, TypeAlias

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from livisi import LivisiDevice
from livisi import LivisiConnection, connect as livisi_connect
from livisi import LivisiWebsocketEvent
from livisi import (
    WrongCredentialException,
    ShcUnreachableException,
    IncorrectIpAddressException,
)
from .const import (
    CONF_HOST,
    CONF_HOST_SECONDARY,
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
from livisi import (
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
        """Initialize the coordinator."""
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
        self._controller_device_id: str | None = None
        # Internal device registry UUID of the SHC hub, set during async_setup_entry.
        self.controller_registry_id: str | None = None
        self.active_host: str = config_entry.data[CONF_HOST]
        self._reconnecting: bool = False  # guard against re-entry in reconnect
        self._ws_generation: int = 0  # incremented each time ws_connect() is called

    # ---------------------------------------------------------------------
    # HA lifecycle
    # ---------------------------------------------------------------------
    async def async_setup(self) -> None:
        """Initialise connection to the Livisi controller."""
        await self._connect_any()
        self.shutdown = False

    # ---------------------------------------------------------------------
    # Failover connection logic
    # ---------------------------------------------------------------------
    async def _connect_any(self, prefer_primary: bool = True) -> None:
        """Try connecting to primary host, then secondary (if configured).

        Sets self.active_host and self.aiolivisi on success.
        Raises WrongCredentialException immediately on auth failure.
        Raises the last connectivity exception if all hosts are exhausted.
        """
        primary = self.config_entry.data[CONF_HOST]
        secondary = self.config_entry.data.get(CONF_HOST_SECONDARY)

        hosts: list[str] = [primary]
        if secondary:
            hosts.append(secondary)

        last_exc: Exception | None = None
        for host in hosts:
            try:
                connection = await livisi_connect(
                    host, self.config_entry.data[CONF_PASSWORD]
                )
                if self.active_host != host:
                    LOGGER.info(
                        "Livisi: switched active host from %s to %s",
                        self.active_host,
                        host,
                    )
                self.active_host = host
                self.aiolivisi = connection
                return
            except WrongCredentialException:
                raise  # auth error — do not attempt fallback
            except Exception as exc:
                LOGGER.debug("Livisi: cannot connect to %s: %s", host, exc)
                last_exc = exc

        raise last_exc

    # ---------------------------------------------------------------------
    # Update logic
    # ---------------------------------------------------------------------
    async def _async_update_data(self) -> list[LivisiDevice]:
        """Poll the controller for device configuration."""
        try:
            LOGGER.debug("Fetching Livisi data")
            return await self.async_get_devices()
        except WrongCredentialException as exc:
            raise ConfigEntryAuthFailed(
                "Authentication failed, please reconfigure."
            ) from exc
        except (ShcUnreachableException, IncorrectIpAddressException) as exc:
            LOGGER.debug(
                "Livisi connection lost on %s: %s — attempting host failover",
                self.active_host,
                exc,
            )
            return await self._reconnect_and_update(exc)
        except Exception as exc:
            LOGGER.error("Error fetching Livisi data: %s", exc)
            self._mark_controller_unreachable()
            self._recover_from_error = True
            raise UpdateFailed(exc) from exc

    async def _reconnect_and_update(
        self, original_exc: Exception
    ) -> list[LivisiDevice]:
        """Attempt host failover then retry the update once.

        At most one reconnect attempt per update cycle (guarded by _reconnecting).
        """
        if self._reconnecting:
            self._mark_controller_unreachable()
            self._recover_from_error = True
            raise UpdateFailed(original_exc) from original_exc

        self._reconnecting = True
        try:
            # Close the stale connection before reconnecting
            try:
                await self.aiolivisi.close()
            except Exception:
                pass
            self.websocket_connected = False

            await self._connect_any(prefer_primary=True)
            LOGGER.info(
                "Livisi: reconnect successful on %s, retrying update",
                self.active_host,
            )
            return await self.async_get_devices()
        except WrongCredentialException as exc:
            raise ConfigEntryAuthFailed(
                "Authentication failed, please reconfigure."
            ) from exc
        except Exception as exc:
            LOGGER.error(
                "Livisi: reconnect failed (tried all hosts): %s", exc
            )
            self._mark_controller_unreachable()
            self._recover_from_error = True
            raise UpdateFailed(exc) from exc
        finally:
            self._reconnecting = False

    def _mark_controller_unreachable(self) -> None:
        """Send a reachability=False event for the controller device."""
        controller_id = self._controller_device_id
        if controller_id is None and self.data is not None:
            for device in self.data:
                if device.is_shc:
                    controller_id = device.id
                    break
        if controller_id is not None:
            LOGGER.debug(
                "Marking controller %s unreachable due to error",
                controller_id,
            )
            self._async_dispatcher_send(
                LIVISI_REACHABILITY_CHANGE,
                controller_id,
                False,
            )
        else:
            LOGGER.debug(
                "Controller device id unknown, cannot mark unreachable"
            )

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
            if device.is_shc:
                self._controller_device_id = device.id
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
        self._ws_generation += 1
        self.config_entry.async_create_background_task(
            self.hass, self.ws_loop(), name="livisi_ws"
        )

    async def ws_loop(self) -> None:
        """Run the WebSocket listener.

        * Tries one immediate reconnect after a failure.
        * Stops after two consecutive failures without receiving any data.
        * Next successful poll will schedule a fresh connection.
        * Exits immediately if a newer ws_connect() call has been made
          (generation mismatch), avoiding duplicate WebSocket connections
          after a host failover.
        """
        generation = self._ws_generation
        while True:
            # Exit if a newer WebSocket loop has been started (host failover)
            if generation != self._ws_generation:
                LOGGER.debug(
                    "Livisi WebSocket loop (generation %d) superseded, exiting",
                    generation,
                )
                self.websocket_connected = False
                return

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


LivisiConfigEntry: TypeAlias = ConfigEntry[LivisiDataUpdateCoordinator]
