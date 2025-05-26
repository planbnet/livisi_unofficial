"""Code to handle a Livisi switches."""

from __future__ import annotations

from typing import Any
from decimal import Decimal

from homeassistant.components.light import LightEntity, ColorMode, ATTR_BRIGHTNESS
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .livisi_device import LivisiDevice

from .const import (
    DIM_LEVEL,
    DOMAIN,
    LIVISI_STATE_CHANGE,
    LOGGER,
    ON_STATE,
    SWITCH_DEVICE_TYPES,
    DIMMING_DEVICE_TYPES,
)
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
        shc_devices: list[LivisiDevice] | None = coordinator.data
        if shc_devices is None:
            return
        entities: list[LightEntity] = []
        for device in shc_devices:
            if device.id not in known_devices:
                light = None
                if device.type in SWITCH_DEVICE_TYPES:
                    switch_type = device.tag_category
                    if switch_type == "TCLightId":
                        capability_id = "SwitchActuator"
                        light = LivisiSwitchLight(
                            config_entry, coordinator, device, capability_id
                        )
                if device.type in DIMMING_DEVICE_TYPES:
                    switch_type = device.tag_category
                    if switch_type == "TCLightId":
                        capability_id = "DimmerActuator"
                        light = LivisiDimmerLight(
                            config_entry, coordinator, device, capability_id
                        )

                if light is not None:
                    LOGGER.debug("Include device type: %s as light", device.type)
                    coordinator.devices.add(device.id)
                    known_devices.add(device.id)
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
        device: LivisiDevice,
        capability_id: str,
    ) -> None:
        """Initialize the Livisi light."""
        super().__init__(config_entry, coordinator, device, capability_id)
        self._attr_name = None
        self._attr_supported_color_modes = [ColorMode.ONOFF]
        self._attr_color_mode = ColorMode.ONOFF

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        response = await self.coordinator.aiolivisi.async_get_value(
            self.capability_id, ON_STATE
        )
        if response is None:
            self.update_reachability(False)
        else:
            self.update_reachability(True)
            self.update_states(response)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self.capability_id}_{ON_STATE}",
                self.update_states,
            )
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        success = await self.aio_livisi.async_set_state(
            self.capability_id, key=ON_STATE, value=True
        )

        if not success:
            self.update_reachability(False)
            raise HomeAssistantError(f"Failed to turn on {self._attr_name}")

        self._attr_is_on = True
        self.update_reachability(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        success = await self.aio_livisi.async_set_state(
            self.capability_id, key=ON_STATE, value=False
        )
        if not success:
            self.update_reachability(False)
            raise HomeAssistantError(f"Failed to turn off {self._attr_name}")

        self._attr_is_on = False
        self.async_write_ha_state()

    @callback
    def update_states(self, state: bool) -> None:
        """Update the state of the switch device."""
        self._attr_is_on = state
        self.async_write_ha_state()


class LivisiDimmerLight(LivisiEntity, LightEntity):
    """Represents a Livisi Light (currently only switches with the light category)."""

    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: LivisiDevice,
        capability_id: str,
    ) -> None:
        """Initialize the Livisi Dimmer light."""
        super().__init__(config_entry, coordinator, device, capability_id)
        self._attr_name = None
        self._attr_brightness = 255

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        response = await self.coordinator.aiolivisi.async_get_value(
            self.capability_id, DIM_LEVEL
        )
        if response is not None:
            self.update_brightness(response)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self.capability_id}_{DIM_LEVEL}",
                self.update_brightness,
            )
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on. With Brightness."""
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
            level = int(round((float(brightness) * 100) / 255))
            success = await self.aio_livisi.async_set_state(
                self.capability_id, key=DIM_LEVEL, value=level
            )
            if not success:
                self.update_reachability(False)
                raise HomeAssistantError(f"Failed to turn on {self._attr_name}")

            self._attr_is_on = True
            self._attr_brightness = brightness
            self.update_reachability(True)
            self.async_write_ha_state()
        else:
            success = await self.aio_livisi.async_set_state(
                self.capability_id, key=DIM_LEVEL, value=100
            )
            if not success:
                self.update_reachability(False)
                raise HomeAssistantError(f"Failed to turn on {self._attr_name}")

            self._attr_is_on = True
            self._attr_brightness = 255
            self.update_reachability(True)
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        success = await self.aio_livisi.async_set_state(
            self.capability_id, key=DIM_LEVEL, value=0
        )
        if not success:
            self.update_reachability(False)
            raise HomeAssistantError(f"Failed to turn off {self._attr_name}")

        self._attr_is_on = False
        self.async_write_ha_state()

    @callback
    def update_brightness(self, dim_level: Decimal) -> None:
        """Update the level of the dimmer device."""
        level = int(round((float(dim_level) / 100) * 255))
        if level is None:
            self._attr_is_on = False
            self.update_reachability(False)
        if level == 0:
            self._attr_is_on = False
            self.update_reachability(True)
            self._attr_brightness = 0
        else:
            self.update_reachability(True)
            self._attr_is_on = True
            self._attr_brightness = level
        self.async_write_ha_state()
