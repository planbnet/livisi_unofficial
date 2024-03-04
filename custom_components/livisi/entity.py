"""Code to handle a Livisi entity."""

from __future__ import annotations


from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntity

from .livisi_device import LivisiDevice

from .const import CONF_HOST, DOMAIN, LIVISI_REACHABILITY_CHANGE
from .coordinator import LivisiDataUpdateCoordinator


class LivisiEntity(CoordinatorEntity[LivisiDataUpdateCoordinator]):
    """Represents a base livisi entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        config_entry: ConfigEntry,
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
        self.device_id = device.id

        device_name = device.name or "Unknown"

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

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device_id)},
            manufacturer=device.manufacturer,
            model=device.type,
            sw_version=device.version,
            name=device_name,
            suggested_area=room_name,
            configuration_url=f"http://{config_entry.data[CONF_HOST]}/#/device/{device.id}",
            via_device=(DOMAIN, config_entry.entry_id),
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

    @callback
    def update_reachability(self, is_reachable: bool) -> None:
        """Update the reachability of the device."""
        self._attr_available = is_reachable
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # use the attribute because CoordinatorEntity just uses coordinator.last_update_success
        return self._attr_available
