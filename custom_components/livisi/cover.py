"""Code to handle a Livisi shutters."""

from __future__ import annotations

from typing import Any
from decimal import Decimal

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from livisi import LivisiDevice

from .const import (
    LOGGER,
    LIVISI_STATE_CHANGE,
    SHUTTER_DEVICE_TYPES,
    SHUTTER_LEVEL,
)
from .coordinator import LivisiConfigEntry, LivisiDataUpdateCoordinator
from .entity import LivisiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LivisiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch device."""
    coordinator: LivisiDataUpdateCoordinator = config_entry.runtime_data
    known_devices = set()

    @callback
    def handle_coordinator_update() -> None:
        """Add cover."""
        shc_devices: list[LivisiDevice] | None = coordinator.data
        if shc_devices is None:
            return
        entities: list[CoverEntity] = []
        for device in shc_devices:
            if device.type in SHUTTER_DEVICE_TYPES and device.id not in known_devices:
                livisi_shutter: CoverEntity = LivisiShutter(
                    config_entry, coordinator, device
                )
                LOGGER.debug("Include device type: %s as cover", device.type)
                coordinator.devices.add(device.id)
                known_devices.add(device.id)
                entities.append(livisi_shutter)

        async_add_entities(entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(handle_coordinator_update)
    )


class LivisiShutter(LivisiEntity, CoverEntity):
    """Represents a livisi shutter device."""

    def __init__(
        self,
        config_entry: LivisiConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        """Initialize the cover."""
        super().__init__(config_entry, coordinator, device, "RollerShutterActuator")
        self._attr_name = None
        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the shutter."""
        success = await self.aio_livisi.async_send_capability_command(
            self.capability_id,
            "StartRamp",
            namespace="CosipDevices.RWE",
            params={"rampDirection": {"type": "Constant", "value": "RampUp"}},
        )
        if not success:
            self._attr_available = False
            self.async_write_ha_state()
            raise HomeAssistantError(f"Failed to open cover {self._attr_name}")
        self._attr_available = True
        self.async_write_ha_state()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the shutter."""
        success = await self.aio_livisi.async_send_capability_command(
            self.capability_id,
            "StartRamp",
            namespace="CosipDevices.RWE",
            params={"rampDirection": {"type": "Constant", "value": "RampDown"}},
        )
        if not success:
            self._attr_available = False
            self.async_write_ha_state()
            raise HomeAssistantError(f"Failed to close cover {self._attr_name}")
        self._attr_available = True
        self.async_write_ha_state()

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the shutter."""
        success = await self.aio_livisi.async_send_capability_command(
            self.capability_id,
            "StopRamp",
            namespace="CosipDevices.RWE",
        )
        if not success:
            self._attr_available = False
            self.async_write_ha_state()
            raise HomeAssistantError(f"Failed to stop cover {self._attr_name}")
        self._attr_available = True
        self.async_write_ha_state()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set shutter to specific position."""

        pos = kwargs[ATTR_POSITION]
        success = await self.aio_livisi.async_set_state(
            self.capability_id,
            namespace="CosipDevices.RWE",
            key=SHUTTER_LEVEL,
            value=pos,
        )
        if not success:
            self._attr_available = False
            self.async_write_ha_state()
            raise HomeAssistantError(
                f"Failed to set position of shutter {self._attr_name}"
            )
        self._attr_available = True
        self.async_write_ha_state()

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        if self._attr_current_cover_position is not None:
            return self._attr_current_cover_position <= 0
        return None

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self.capability_id}_{SHUTTER_LEVEL}",
                self.update_states,
            )
        )

        await self.async_update_value()

    async def async_update_value(self):
        """Fetch the current cover position from the controller."""
        try:
            response = await self.aio_livisi.async_get_value(
                self.capability_id, SHUTTER_LEVEL
            )
        except Exception:
            self._attr_available = False
            return
        if response is None:
            self._attr_current_cover_position = -1
            self._attr_available = False
            self.async_write_ha_state()
        else:
            self._attr_current_cover_position = response
            self._attr_available = True
            self.async_write_ha_state()

    @callback
    def update_states(self, shutter_level: Decimal) -> None:
        """Update the state of the cover device to the shutter position."""
        self._attr_current_cover_position = shutter_level
        self.async_write_ha_state()
