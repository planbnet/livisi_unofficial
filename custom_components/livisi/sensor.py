"""Code to handle a Livisi Sensor."""
from __future__ import annotations
from decimal import Decimal

from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LIVISI_STATE_CHANGE, LOGGER, LUMINANCE, MOTION_DEVICE_TYPES
from .coordinator import LivisiDataUpdateCoordinator
from .entity import LivisiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary_sensor device."""
    coordinator: LivisiDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    known_devices = set()

    @callback
    def handle_coordinator_update() -> None:
        """Add Sensors."""
        shc_devices: list[dict[str, Any]] = coordinator.data
        entities: list[SensorEntity] = []
        for device in shc_devices:
            if device["id"] not in known_devices:
                known_devices.add(device["id"])
                if device["type"] in MOTION_DEVICE_TYPES:
                    # The motion devices all have a luminance sensor
                    luminance_sensor: SensorEntity = LivisiSensor(
                        config_entry,
                        coordinator,
                        device,
                        SensorEntityDescription(
                            key=LUMINANCE,
                            device_class=SensorDeviceClass.ILLUMINANCE,
                            state_class=SensorStateClass.MEASUREMENT,
                            native_unit_of_measurement=PERCENTAGE,
                        ),
                        capability_name="LuminanceSensor",
                    )
                    LOGGER.debug("Include device type: %s", device["type"])
                    coordinator.devices.add(device["id"])
                    entities.append(luminance_sensor)
        async_add_entities(entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(handle_coordinator_update)
    )


class LivisiSensor(LivisiEntity, SensorEntity):
    """Represents a Livisi Sensor."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: dict[str, Any],
        entity_desc: SensorEntityDescription,
        capability_name: str,
    ) -> None:
        """Initialize the Livisi sensor."""
        super().__init__(config_entry, coordinator, device, capability_name)
        self.entity_description = entity_desc

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self.capability_id}",
                self.update_states,
            )
        )

        response = await self.coordinator.async_get_device_state(
            self.capability_id, self.entity_description.key
        )
        if response is None:
            self._attr_available = False
        else:
            self._attr_native_value = response

    @callback
    def update_states(self, state: Decimal) -> None:
        """Update the state of the device."""
        self._attr_native_value = state
        self.async_write_ha_state()
