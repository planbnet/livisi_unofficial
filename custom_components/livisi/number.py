"""Code to handle a Livisi Number Sensor."""
from __future__ import annotations
import platform


from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.components.number import RestoreNumber

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import (
    Platform,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.helpers.entity import DeviceInfo


from .livisi_device import LivisiDevice

from .const import CONF_HOST, DOMAIN, LOGGER, MOTION_DEVICE_TYPES
from .coordinator import LivisiDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    coordinator: LivisiDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    known_devices = set()

    @callback
    def handle_coordinator_update() -> None:
        """Add Motion Sensor Config Entities."""
        shc_devices: list[LivisiDevice] = coordinator.data

        entities: list[NumberEntity] = []
        for device in shc_devices:
            if device.id not in known_devices:
                known_devices.add(device.id)
                if device.type in MOTION_DEVICE_TYPES:
                    livisi_motion_duration: NumberEntity = NoopConfigNumber(
                        config_entry,
                        device,
                        NumberEntityDescription(
                            key="duration",
                            name="Duration",
                            entity_category=EntityCategory.CONFIG,
                            native_max_value=65535,
                            native_min_value=0,
                            native_step=1,
                            native_unit_of_measurement="s",
                        ),
                    )
                    LOGGER.debug("Include number sensor device type: %s", device.type)
                    coordinator.devices.add(device.id)
                    entities.append(livisi_motion_duration)
        async_add_entities(entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(handle_coordinator_update)
    )


class NoopConfigNumber(RestoreNumber):
    """Represents a NumberEntity without effects on the livisi system (for internal use)."""

    _attr_has_entity_name = True

    number: float | None = 20

    def __init__(
        self,
        config_entry: ConfigEntry,
        device: LivisiDevice,
        entity_desc: NumberEntityDescription,
    ) -> None:
        """Initialize the Livisi sensor."""
        self.entity_description = entity_desc
        unique_id = device.id + "_" + entity_desc.key + "_number"
        self._attr_unique_id = unique_id
        self.device_id = device.id
        self._attr_translation_key = entity_desc.key
        self.entity_id = str.lower(
            Platform.NUMBER + "." + device.name + "_" + entity_desc.key
        )

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.id)},
            manufacturer=device.manufacturer,
            model=device.type,
            sw_version=device.version,
            name=device.name,
            suggested_area=device.room,
            configuration_url=f"http://{config_entry.data[CONF_HOST]}/#/device/{device.id}",
            via_device=(DOMAIN, config_entry.entry_id),
        )
        super().__init__()

    async def async_added_to_hass(self) -> None:
        """Restore last state."""
        await super().async_added_to_hass()

        # Set to default Value first as the calls to retrieve the state
        # are awaiting endlessly when the entity is initialized for the first time
        if self._attr_native_value is None:
            self._attr_native_value = 20

        if (last_state := await self.async_get_last_state()) and (
            last_number_data := await self.async_get_last_number_data()
        ):
            if last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                self._attr_native_value = last_number_data.native_value

    async def async_set_native_value(self, value: float) -> None:
        """Set sensor config."""
        self._attr_native_value = value
