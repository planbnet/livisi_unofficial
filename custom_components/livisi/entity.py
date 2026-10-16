"""Code to handle a Livisi entity."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntity

from livisi import LivisiDevice

from .const import (
    CONF_HOST,
    DOMAIN,
    LIVISI_REACHABILITY_CHANGE,
    LIVISI_STATE_CHANGE,
    LOGGER,
)
from .coordinator import LivisiConfigEntry, LivisiDataUpdateCoordinator

# Returned by LivisiEntity.async_fetch_value when the value read from the
# controller is outdated (a push update arrived or the device became
# unreachable while the request was in flight) and must not be applied.
STALE_VALUE: Any = object()


def create_device_info(config_entry, device, device_name=None, controller_registry_id=None):
    """Create device info for the livisi device."""

    if device_name is None:
        device_name = device.name or "Unknown"

    device_info = DeviceInfo(
        identifiers={(DOMAIN, device.id)},
        manufacturer=device.manufacturer,
        model=device.type,
        sw_version=device.version,
        name=device_name,
        suggested_area=device.room,
        configuration_url=f"http://{config_entry.data[CONF_HOST]}/#/device/{device.id}",
    )
    # via_device_id must be the internal device registry UUID of the SHC hub,
    # not a (DOMAIN, ...) identifier tuple. Only set it if we know the hub UUID.
    if controller_registry_id is not None:
        device_info["via_device_id"] = controller_registry_id
    return device_info


class LivisiEntity(CoordinatorEntity[LivisiDataUpdateCoordinator]):
    """Represents a base livisi entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: LivisiConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: LivisiDevice,
        capability_name: str = None,
        *,
        suffix: str = "",
        battery: bool = False,
        use_room_as_device_name: bool = False,
    ) -> None:
        """Initialize the common properties of a Livisi device."""
        self.aio_livisi = coordinator.aiolivisi
        self.capabilities = device.capabilities
        self.capability_id = None
        self.capability_name = capability_name
        self.device_id = device.id

        if capability_name is not None:
            self.capability_id = self.capabilities.get(capability_name)

        if battery:
            self._attr_name = "Battery Low"
            unique_id = self.device_id + "_battery"
        else:
            if self.capability_id is not None:
                unique_id = self.capability_id + suffix
            else:
                unique_id = self.device_id + suffix

        self._attr_available = not device.unreachable
        self._attr_unique_id = unique_id
        # Number of push updates received per "<capability>_<property>" topic
        # and number of times the device became unreachable. Used to detect
        # that a value read from the controller got outdated while in flight.
        self._push_revisions: dict[str, int] = {}
        self._unreachable_revision = 0
        # Set when a command was rejected, so the entity is refreshed once the
        # next poll reports the device as reachable again.
        self._recover_after_command_failure = False

        device_name = device.name or "Unknown"

        room_name: str | None = device.room
        # For livisi climate entities, the device should have the room name from
        # the livisi setup, as each livisi room gets exactly one VRCC device. The livisi
        # device name will always be some localized value of "Climate", so the full element
        # name of climate entities will be in the form of "Bedroom Climate"
        # for sensors, don't set the name (as they will be named "Temperature" or "Humidity")
        if use_room_as_device_name and room_name is not None:
            if not isinstance(self, SensorEntity) and not isinstance(
                self, BinarySensorEntity
            ):
                self._attr_name = device_name
            device_name = room_name

        self._attr_device_info = create_device_info(
            config_entry,
            device,
            device_name,
            getattr(coordinator, "controller_registry_id", None),
        )
        super().__init__(coordinator)

    async def async_added_to_hass(self) -> None:
        """Register callback for reachability."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_REACHABILITY_CHANGE}_{self.device_id}",
                self.update_reachability,
            )
        )

    def subscribe_state(
        self,
        capability_id: str,
        property_name: str,
        handler: Callable[[Any], None],
    ) -> None:
        """Subscribe to push updates of a capability property."""
        key = f"{capability_id}_{property_name}"

        @callback
        def _handle_push(value: Any) -> None:
            self._push_revisions[key] = self._push_revisions.get(key, 0) + 1
            handler(value)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, f"{LIVISI_STATE_CHANGE}_{key}", _handle_push
            )
        )

    async def async_fetch_value(self, capability_id: str, property_name: str) -> Any:
        """Read a capability property from the controller.

        Returns STALE_VALUE if a push update for the same property arrived or
        the device became unreachable while the request was in flight, so a
        slow read never overwrites newer information.
        """
        key = f"{capability_id}_{property_name}"
        push_revision = self._push_revisions.get(key, 0)
        unreachable_revision = self._unreachable_revision
        value = await self.coordinator.aiolivisi.async_get_value(
            capability_id, property_name
        )
        if (
            self._push_revisions.get(key, 0) != push_revision
            or self._unreachable_revision != unreachable_revision
        ):
            LOGGER.debug("Discarding outdated value of %s", key)
            return STALE_VALUE
        return value

    @callback
    def command_failed(self, message: str) -> HomeAssistantError:
        """Mark the entity unavailable after a rejected command.

        The entity is refreshed again once a poll reports the device as
        reachable. Returns the error to raise.
        """
        self._attr_available = False
        self._recover_after_command_failure = True
        self.async_write_ha_state()
        return HomeAssistantError(message)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Retry entities whose last command failed once the device is reachable."""
        if (
            self._recover_after_command_failure
            and self.coordinator.last_update_success
            and self._device_reported_reachable()
        ):
            self._recover_after_command_failure = False
            # skip if a push update already confirmed that the device works
            if not self._attr_available:
                if hasattr(self, "async_update_value"):
                    LOGGER.debug(
                        "Device %s: refreshing value after failed command",
                        self.device_id,
                    )
                    self._schedule_value_update(retry_after_command_failure=True)
                else:
                    self._attr_available = True
        super()._handle_coordinator_update()

    def _device_reported_reachable(self) -> bool:
        """Return whether the last poll reported the device as reachable."""
        for device in self.coordinator.data or []:
            if device.id == self.device_id:
                return not device.unreachable
        return False

    @callback
    def _schedule_value_update(self, *, retry_after_command_failure: bool) -> None:
        """Refresh the entity value from the controller in the background."""

        async def _try_update_value():
            try:
                # async_update_value will also set _attr_available to True
                # if the update was successful
                await self.async_update_value()
            except Exception as err:
                LOGGER.warning(
                    "Device %s: async_update_value failed: %s",
                    self.device_id,
                    err,
                )
            if retry_after_command_failure and not self._attr_available:
                # try again after the next poll
                self._recover_after_command_failure = True
            self.async_write_ha_state()

        self.hass.async_create_task(_try_update_value())

    @callback
    def update_reachability(self, is_reachable: bool) -> None:
        """Update the reachability of the device."""
        if not is_reachable:
            # invalidate value reads that are currently in flight
            self._unreachable_revision += 1
        if is_reachable and not self._attr_available:
            # if self has a func "async def async_update_value(self)" call it to update the value
            if hasattr(self, "async_update_value"):
                LOGGER.debug(
                    "Device %s is reachable again, request value update", self.device_id
                )
                self._schedule_value_update(retry_after_command_failure=False)
            else:
                # This entity has no value to fetch, so being reachable again
                # is the only information we get. Without this the entity would
                # stay unavailable forever after a single controller outage
                # (e.g. the controller sensors, the restart button and all
                # event entities).
                self._attr_available = True
                self.async_write_ha_state()
                LOGGER.debug("Device %s is reachable again", self.device_id)
        elif not is_reachable and self._attr_available:
            LOGGER.debug("Device %s became unreachable", self.device_id)
            self._attr_available = False
            self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # use the attribute because CoordinatorEntity just uses coordinator.last_update_success
        return self._attr_available
