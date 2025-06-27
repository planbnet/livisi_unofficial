"""Code to handle a Livisi Number Sensor."""

from __future__ import annotations


from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.components.number import RestoreNumber

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN

from .entity import create_device_info
from livisi import LivisiDevice

from .const import LOGGER, MOTION_DEVICE_TYPES
from .coordinator import LivisiConfigEntry, LivisiDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LivisiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    coordinator: LivisiDataUpdateCoordinator = config_entry.runtime_data
    known_devices = set()

    @callback
    def handle_coordinator_update() -> None:
        """Add Motion Sensor Config Entities."""
        shc_devices: list[LivisiDevice] | None = coordinator.data
        if shc_devices is None:
            return

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
        config_entry: LivisiConfigEntry,
        device: LivisiDevice,
        entity_desc: NumberEntityDescription,
    ) -> None:
        """Initialize the Livisi sensor."""
        self.entity_description = entity_desc
        unique_id = device.id + "_" + entity_desc.key + "_number"
        self._attr_unique_id = unique_id
        self.device_id = device.id
        self._attr_translation_key = entity_desc.key
        self._attr_device_info = create_device_info(config_entry, device)
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

        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set sensor config."""
        self._attr_native_value = value
