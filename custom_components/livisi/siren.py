"""Code to handle a Livisi switches."""

from __future__ import annotations

from typing import Any

from homeassistant.components.siren import SirenEntity
from homeassistant.components.siren.const import SirenEntityFeature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .livisi_device import LivisiDevice

from .const import (
    ACTIVE_CHANNEL,
    LIVISI_STATE_CHANGE,
    LOGGER,
    ON_STATE,
    SMOKE_DETECTOR_DEVICE_TYPES,
    SIREN_DEVICE_TYPES,
)
from .coordinator import LivisiConfigEntry, LivisiDataUpdateCoordinator
from .entity import LivisiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LivisiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up a smoke detecor device."""
    coordinator: LivisiDataUpdateCoordinator = config_entry.runtime_data
    known_devices = set()

    @callback
    def handle_coordinator_update() -> None:
        """Add switch."""
        shc_devices: list[LivisiDevice] | None = coordinator.data
        if shc_devices is None:
            return
        entities: list[SirenEntity] = []
        for device in shc_devices:
            if (
                device.id not in known_devices
                and device.type in SMOKE_DETECTOR_DEVICE_TYPES
            ):
                livisi_siren: SirenEntity = LivisiSmoke(
                    config_entry, coordinator, device
                )
                LOGGER.debug("Include device type: %s as siren", device.type)
                coordinator.devices.add(device.id)
                known_devices.add(device.id)
                entities.append(livisi_siren)
            if device.id not in known_devices and device.type in SIREN_DEVICE_TYPES:
                livisi_siren: SirenEntity = LivisiSiren(
                    config_entry, coordinator, device
                )
                LOGGER.debug("Include device type: %s as siren", device.type)
                coordinator.devices.add(device.id)
                known_devices.add(device.id)
                entities.append(livisi_siren)
        async_add_entities(entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(handle_coordinator_update)
    )


class LivisiSmoke(LivisiEntity, SirenEntity):
    """Represents the Livisi Sirens."""

    _attr_supported_features = SirenEntityFeature.TURN_OFF | SirenEntityFeature.TURN_ON

    def __init__(
        self,
        config_entry: LivisiConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: LivisiDevice,
    ) -> None:
        """Initialize the Livisi siren."""
        super().__init__(config_entry, coordinator, device, "AlarmActuator")
        self._attr_name = None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        success = await self.aio_livisi.async_set_state(
            self.capability_id, key=ON_STATE, value=True
        )
        if not success:
            self._attr_available = False
            raise HomeAssistantError(f"Failed to turn on {self._attr_name}")

        self._attr_is_on = True
        self._attr_available = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        success = await self.aio_livisi.async_set_state(
            self.capability_id, key=ON_STATE, value=False
        )
        if not success:
            self._attr_available = False
            raise HomeAssistantError(f"Failed to turn off {self._attr_name}")
        self._attr_available = True

        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self.capability_id}_{ON_STATE}",
                self.update_states,
            )
        )
        await self.async_update_value()

    async def async_update_value(self):
        """Update the on/off state from the controller."""
        try:
            response = await self.coordinator.aiolivisi.async_get_value(
                self.capability_id, ON_STATE
            )
        except Exception:
            self._attr_available = False
            return
        if response is None:
            self._attr_available = False
        else:
            self._attr_is_on = response
            self._attr_available = True

    @callback
    def update_states(self, state: bool) -> None:
        """Update the state of the siren device."""
        self._attr_is_on = state
        self.async_write_ha_state()


class LivisiSiren(LivisiEntity, SirenEntity):
    """Represents the Livisi Sirens."""

    _attr_supported_features = SirenEntityFeature.TURN_OFF | SirenEntityFeature.TURN_ON

    def __init__(
        self,
        config_entry: LivisiConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: LivisiDevice,
    ) -> None:
        """Initialize the Livisi siren."""
        super().__init__(config_entry, coordinator, device, "SirenActuator")
        self._attr_name = None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        success = await self.aio_livisi.async_set_state(
            self.capability_id, key="activeChannel", value="Alarm"
        )
        if not success:
            self._attr_available = False
            raise HomeAssistantError(f"Failed to turn on {self._attr_name}")

        self._attr_is_on = True
        self._attr_available = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        success = await self.aio_livisi.async_set_state(
            self.capability_id, key="activeChannel", value="None"
        )
        if not success:
            self._attr_available = False
            raise HomeAssistantError(f"Failed to turn off {self._attr_name}")
        self._attr_available = True

        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self.capability_id}_{ON_STATE}",
                self.update_state,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self.capability_id}_{ACTIVE_CHANNEL}",
                self.update_active_channel,
            )
        )
        await self.async_update_value()

    async def async_update_value(self):
        """Refresh the active channel value from the controller."""
        try:
            response = await self.coordinator.aiolivisi.async_get_value(
                self.capability_id, ACTIVE_CHANNEL
            )
        except Exception:
            self._attr_available = False
            return
        if response is None:
            self._attr_available = False
        elif response == "Alarm":
            self._attr_is_on = True
            self._attr_available = True
        else:
            self._attr_is_on = False
            self._attr_available = True

    @callback
    def update_state(self, state: bool) -> None:
        """Update the state of the siren device."""
        self._attr_is_on = state
        self.async_write_ha_state()

    @callback
    def update_active_channel(self, active_channel: str) -> None:
        """Update the state of the siren device."""
        self._attr_is_on = active_channel == "Alarm"
        self.async_write_ha_state()
