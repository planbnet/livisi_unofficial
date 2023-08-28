"""Code to handle a Livisi switches."""
from __future__ import annotations

from typing import Any

from homeassistant.components.light import LightEntity, ColorMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LIVISI_STATE_CHANGE, LOGGER, SWITCH_DEVICE_TYPES
from .coordinator import LivisiDataUpdateCoordinator
from .entity import LivisiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up light device."""
    coordinator: LivisiDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    known_devices = set()

    @callback
    def handle_coordinator_update() -> None:
        """Add light."""
        shc_devices: list[dict[str, Any]] = coordinator.data
        entities: list[LightEntity] = []
        for device in shc_devices:
            if device["id"] not in known_devices:
                light = None
                if device["type"] in SWITCH_DEVICE_TYPES:
                    switch_type = device.get("tags", {}).get("typeCategory", "default")
                    if switch_type == "TCLightId":
                        light = LivisiSwitchLight(config_entry, coordinator, device)

                if light is not None:
                    LOGGER.debug("Include device type: %s as light", device["type"])
                    coordinator.devices.add(device["id"])
                    known_devices.add(device["id"])
                    entities.append(light)

        async_add_entities(entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(handle_coordinator_update)
    )


class LivisiSwitchLight(LivisiEntity, LightEntity):
    """Represents a Livisi Light (currently only switches with the light category)."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the Livisi light."""
        super().__init__(config_entry, coordinator, device, "SwitchActuator")
        self._attr_name = None
        self._attr_supported_color_modes = [ColorMode.ONOFF]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        response = await self.aio_livisi.async_set_onstate(
            self.capability_id, is_on=True
        )
        if response is None:
            self._attr_available = False
            raise HomeAssistantError(f"Failed to turn on {self._attr_name}")
        if response["resultCode"] == "Success":
            self._attr_is_on = True
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        response = await self.aio_livisi.async_set_onstate(
            self.capability_id, is_on=False
        )
        if response is None:
            self._attr_available = False
            raise HomeAssistantError(f"Failed to turn off {self._attr_name}")
        if response["resultCode"] == "Success":
            self._attr_is_on = False
            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        response = await self.coordinator.async_get_device_state(
            self.capability_id, "onState"
        )
        if response is None:
            self._attr_is_on = False
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
        """Update the state of the light device."""
        self._attr_is_on = state
        self.async_write_ha_state()
