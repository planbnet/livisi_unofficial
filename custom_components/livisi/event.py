"""Code to handle a Livisi Events (motion and button presses)."""
from __future__ import annotations
from typing import Any

from homeassistant.components.event import (
    EventEntity,
    EventEntityDescription,
    EventDeviceClass
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, LOGGER, MOTION_DEVICE_TYPES, LIVISI_EVENT, EVENT_MOTION_DETECTED
from .coordinator import LivisiDataUpdateCoordinator
from .entity import LivisiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up event device."""
    coordinator: LivisiDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    known_devices = set()

    @callback
    def handle_coordinator_update() -> None:
        """Add events."""
        shc_devices: list[dict[str, Any]] = coordinator.data
        entities: list[EventEntity] = []
        for device in shc_devices:
            if (
                device["id"] not in known_devices
                and device["type"] in MOTION_DEVICE_TYPES
            ):
                event: EventEntity = LivisiEvent(
                    config_entry,
                    coordinator,
                    device,
                    EventEntityDescription(
                    key="motion",
                    device_class=EventDeviceClass.MOTION,
                    event_types=[EVENT_MOTION_DETECTED]
                    ),
                    "MotionDetectionSensor",
                )
                LOGGER.debug("Include motion sensor device type: %s", device["type"])
                coordinator.devices.add(device["id"])
                known_devices.add(device["id"])
                entities.append(event)
        async_add_entities(entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(handle_coordinator_update)
    )


class LivisiEvent(LivisiEntity, EventEntity):
    """Represents a Livisi Event."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: dict[str, Any],
        entity_desc: EventEntityDescription,
        capability_name: str,
    ) -> None:
        """Initialize the Livisi event."""
        super().__init__(config_entry, coordinator, device)
        self._capability_id = self.capabilities[capability_name]
        self.entity_description = entity_desc

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_EVENT}_{self._capability_id}",
                self.trigger_event,
            )
        )


    @callback
    def trigger_event(self, event_data: Any) -> None:
        """Trigger the event."""
        self._trigger_event(event_data["type"], event_data)
        self.async_write_ha_state()
