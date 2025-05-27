"""Code to handle a Livisi buttons."""

from __future__ import annotations

from homeassistant.components.button import (
    ButtonEntity,
    ButtonDeviceClass,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from custom_components.livisi.livisi_const import (
    COMMAND_RESTART,
    CONTROLLER_DEVICE_TYPES,
)

from .livisi_device import LivisiDevice

from .const import DOMAIN, LOGGER
from .coordinator import LivisiDataUpdateCoordinator
from .entity import LivisiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button devices."""
    coordinator: LivisiDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    known_devices = set()

    @callback
    def handle_coordinator_update() -> None:
        """Add button."""
        shc_devices: list[LivisiDevice] | None = coordinator.data
        if shc_devices is None:
            return
        entities: list[ButtonEntity] = []
        for device in shc_devices:
            if device.id not in known_devices:
                switch = None
                if device.type in CONTROLLER_DEVICE_TYPES:
                    description = ButtonEntityDescription(
                        device_class=ButtonDeviceClass.RESTART, key="reboot"
                    )
                    switch = LivisiButton(
                        config_entry, coordinator, device, description
                    )

                if switch is not None:
                    LOGGER.debug("Include SHC reboot button")
                    coordinator.devices.add(device.id)
                    known_devices.add(device.id)
                    entities.append(switch)

        async_add_entities(entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(handle_coordinator_update)
    )


class LivisiButton(LivisiEntity, ButtonEntity):
    """Represents the Livisi Button."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: LivisiDevice,
        entity_desc: ButtonEntityDescription,
    ) -> None:
        """Initialize the Livisi button."""
        super().__init__(config_entry, coordinator, device, "Reboot")
        self._attr_device_class = entity_desc.device_class
        self._attr_unique_id = device.id + "_" + entity_desc.key
        self.entity_description = entity_desc
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)}
        )

    async def async_press(self) -> None:
        """Handle the button press."""
        success = await self.aio_livisi.async_send_device_command(
            self.capability_id,
            COMMAND_RESTART,
            namespace="core.RWE",
            params={
                "reason": {
                    "type": "Constant",
                    "value": "User requested to restart smarthome controller.",
                }
            },
        )

        if not success:
            raise HomeAssistantError(f"Failed to restart SHC {self._attr_unique_id}")
