"""Code to handle a Livisi switches."""
from __future__ import annotations

from typing import Any

from homeassistant.components.siren import SirenEntity
from homeassistant.components.siren.const import SirenEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LIVISI_STATE_CHANGE, LOGGER, SIREN_DEVICE_TYPES
from .coordinator import LivisiDataUpdateCoordinator
from .entity import LivisiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a smoke detecor device."""
    coordinator: LivisiDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    known_devices = set()

    @callback
    def handle_coordinator_update() -> None:
        """Add switch."""
        shc_devices: list[dict[str, Any]] = coordinator.data
        entities: list[SirenEntity] = []
        for device in shc_devices:
            if (
                device["id"] not in known_devices
                and device["type"] in SIREN_DEVICE_TYPES
            ):
                livisi_siren: SirenEntity = LivisiSiren(
                    config_entry, coordinator, device
                )
                LOGGER.debug("Include device type: %s as siren", device["type"])
                coordinator.devices.add(device["id"])
                known_devices.add(device["id"])
                entities.append(livisi_siren)
        async_add_entities(entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(handle_coordinator_update)
    )


class LivisiSiren(LivisiEntity, SirenEntity):
    """Represents the Livisi Sirens."""

    _attr_supported_features = SirenEntityFeature.TURN_OFF | SirenEntityFeature.TURN_ON

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the Livisi siren."""
        super().__init__(config_entry, coordinator, device, "AlarmActuator")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        response = await self.aio_livisi.async_pss_set_state(
            self.capability_id, is_on=True
        )
        if response is None:
            self._attr_available = False
            raise HomeAssistantError(f"Failed to turn on {self._attr_name}")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        response = await self.aio_livisi.async_pss_set_state(
            self.capability_id, is_on=False
        )
        if response is None:
            self._attr_available = False
            raise HomeAssistantError(f"Failed to turn off {self._attr_name}")

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        response = await self.coordinator.async_get_device_state(
            self.capability_id, "onState"
        )
        if response is None:
            self._attr_available = False
        else:
            self._attr_is_on = response
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self.capability_id}",
                self.update_states,
            )
        )

    @callback
    def update_states(self, state: bool) -> None:
        """Update the state of the siren device."""
        self._attr_is_on = state
        self.async_write_ha_state()
