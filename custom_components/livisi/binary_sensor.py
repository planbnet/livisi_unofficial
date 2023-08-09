"""Code to handle a Livisi Binary Sensor."""
from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    BATTERY_POWERED_DEVICES,
    DOMAIN,
    LIVISI_STATE_CHANGE,
    LOGGER,
    WDS_DEVICE_TYPE,
    SMOKE_DETECTOR_DEVICE_TYPES,
)
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
        """Add Window Sensor."""
        shc_devices: list[dict[str, Any]] = coordinator.data
        entities: list[BinarySensorEntity] = []
        for device in shc_devices:
            if device["id"] not in known_devices:
                known_devices.add(device["id"])
                if device["type"] == WDS_DEVICE_TYPE:
                    livisi_binary: BinarySensorEntity = LivisiWindowDoorSensor(
                        config_entry, coordinator, device
                    )
                    LOGGER.debug(
                        "Include device type: %s as contact sensor", device["type"]
                    )
                    coordinator.devices.add(device["id"])
                    entities.append(livisi_binary)
                if device["type"] in SMOKE_DETECTOR_DEVICE_TYPES:
                    livisi_smoke: BinarySensorEntity = LivisiSmokeSensor(
                        config_entry, coordinator, device
                    )
                    LOGGER.debug(
                        "Include device type: %s as smoke detector", device["type"]
                    )
                    coordinator.devices.add(device["id"])
                    entities.append(livisi_smoke)
                if device["type"] in BATTERY_POWERED_DEVICES:
                    livisi_binary: BinarySensorEntity = LivisiBatteryLowSensor(
                        config_entry, coordinator, device
                    )
                    LOGGER.debug("Include battery sensor for: %s", device["type"])
                    coordinator.devices.add(device["id"])
                    entities.append(livisi_binary)

        async_add_entities(entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(handle_coordinator_update)
    )


class LivisiBinarySensor(LivisiEntity, BinarySensorEntity):
    """Represents a Livisi Binary Sensor."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: dict[str, Any],
        capability_name: str,
        property_name: str,
    ) -> None:
        """Initialize the Livisi sensor."""
        super().__init__(config_entry, coordinator, device)
        self._capability_id = self.capabilities[capability_name]
        self._property_name = property_name

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self._capability_id}",
                self.update_states,
            )
        )

        response = await self.coordinator.async_get_device_state(
            self._capability_id, self._property_name
        )
        if response is None:
            self._attr_available = False
        else:
            self._attr_is_on = response

    @callback
    def update_states(self, state: bool) -> None:
        """Update the state of the device."""
        self._attr_is_on = state
        self.async_write_ha_state()


class LivisiBatteryLowSensor(LivisiEntity, BinarySensorEntity):
    """Represents the Battery Low state as a Binary Sensor Entity."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the Livisi window/door sensor."""
        super().__init__(config_entry, coordinator, device, battery=True)
        self._attr_device_class = BinarySensorDeviceClass.BATTERY
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        device = next(
            (
                device
                for device in self.coordinator.data
                if device["id"] + "_battery" == self.unique_id
            ),
            None,
        )

        if device is not None:
            self._attr_is_on = device.get("batteryLow", False)


class LivisiWindowDoorSensor(LivisiBinarySensor):
    """Represents a Livisi Window/Door Sensor as a Binary Sensor Entity."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the Livisi window/door sensor."""
        super().__init__(
            config_entry, coordinator, device, "WindowDoorSensor", "isOpen"
        )

        self._attr_device_class = (
            BinarySensorDeviceClass.DOOR
            if (device.get("tags", {}).get("typeCategory") == "TCDoorId")
            else BinarySensorDeviceClass.WINDOW
        )


class LivisiSmokeSensor(LivisiBinarySensor):
    """Represents a Livisi Window/Door Sensor as a Binary Sensor Entity."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the Livisi window/door sensor."""
        super().__init__(
            config_entry, coordinator, device, "SmokeDetectorSensor", "isSmokeAlarm"
        )
        self._attr_device_class = BinarySensorDeviceClass.SMOKE
