"""Code to handle a Livisi Binary Sensor."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import CALLBACK_TYPE
from homeassistant.helpers import event as evt, entity_registry as er

from homeassistant.const import (
    Platform,
)
from .livisi_device import LivisiDevice
from datetime import datetime, timezone

from .const import (
    BATTERY_POWERED_DEVICES,
    DOMAIN,
    IS_OPEN,
    IS_SMOKE_ALARM,
    LIVISI_STATE_CHANGE,
    LOGGER,
    LIVISI_EVENT,
    MOTION_DEVICE_TYPES,
    WDS_DEVICE_TYPES,
    SMOKE_DETECTOR_DEVICE_TYPES,
)
from .coordinator import LivisiConfigEntry, LivisiDataUpdateCoordinator
from .entity import LivisiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LivisiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary_sensor device."""
    coordinator: LivisiDataUpdateCoordinator = config_entry.runtime_data
    known_devices = set()

    @callback
    def handle_coordinator_update() -> None:
        """Add Window Sensor."""
        shc_devices: list[LivisiDevice] | None = coordinator.data
        if shc_devices is None:
            return
        entities: list[BinarySensorEntity] = []
        for device in shc_devices:
            if device.id not in known_devices:
                known_devices.add(device.id)
                if device.type in WDS_DEVICE_TYPES:
                    device_class = (
                        BinarySensorDeviceClass.DOOR
                        if (device.tag_category == "TCDoorId")
                        else BinarySensorDeviceClass.WINDOW
                    )
                    livisi_contact: BinarySensorEntity = LivisiBinarySensor(
                        config_entry,
                        coordinator,
                        device,
                        BinarySensorEntityDescription(
                            key=IS_OPEN, device_class=device_class
                        ),
                        capability_name="WindowDoorSensor",
                    )
                    LOGGER.debug(
                        "Include device type: %s as contact sensor", device.type
                    )
                    coordinator.devices.add(device.id)
                    entities.append(livisi_contact)
                if device.type in SMOKE_DETECTOR_DEVICE_TYPES:
                    livisi_smoke: BinarySensorEntity = LivisiBinarySensor(
                        config_entry,
                        coordinator,
                        device,
                        BinarySensorEntityDescription(
                            key=IS_SMOKE_ALARM,
                            device_class=BinarySensorDeviceClass.SMOKE,
                        ),
                        capability_name="SmokeDetectorSensor",
                    )
                    LOGGER.debug(
                        "Include device type: %s as smoke detector", device.type
                    )
                    coordinator.devices.add(device.id)
                    entities.append(livisi_smoke)
                if device.type in BATTERY_POWERED_DEVICES:
                    livisi_binary: BinarySensorEntity = LivisiBatteryLowSensor(
                        config_entry, coordinator, device
                    )
                    LOGGER.debug("Include battery sensor for: %s", device.type)
                    coordinator.devices.add(device.id)
                    entities.append(livisi_binary)
                if device.type in MOTION_DEVICE_TYPES:
                    livisi_motion: BinarySensorEntity = LivisiMotionSensor(
                        config_entry,
                        coordinator,
                        device,
                        BinarySensorEntityDescription(
                            key="motionDetectedCount",
                            device_class=BinarySensorDeviceClass.MOTION,
                        ),
                        capability_name="MotionDetectionSensor",
                    )
                    LOGGER.debug("Include motion sensor device type: %s", device.type)
                    coordinator.devices.add(device.id)
                    entities.append(livisi_motion)
        async_add_entities(entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(handle_coordinator_update)
    )


class LivisiBinarySensor(LivisiEntity, BinarySensorEntity):
    """Represents a Livisi Binary Sensor."""

    def __init__(
        self,
        config_entry: LivisiConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: LivisiDevice,
        entity_desc: BinarySensorEntityDescription,
        capability_name: str,
    ) -> None:
        """Initialize the Livisi sensor."""
        super().__init__(config_entry, coordinator, device, capability_name)
        self.entity_description = entity_desc

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()
        property_name: str = self.entity_description.key
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self.capability_id}_{property_name}",
                self.update_states,
            )
        )
        await self.async_update_value()

    async def async_update_value(self):
        """Retrieve the latest value from the controller."""
        try:
            response = await self.coordinator.aiolivisi.async_get_value(
                self.capability_id, self.entity_description.key
            )
        except Exception:
            self._attr_available = False
            return
        if response is None:
            if self.capability_name == "WindowDoorSensor":
                self._attr_available = True
                self._attr_is_on = None
            else:
                self._attr_available = False
        else:
            self._attr_available = True
            self._attr_is_on = response
        self.async_write_ha_state()

    @callback
    def update_states(self, state: bool) -> None:
        """Update the state of the device."""
        if not isinstance(state, bool):
            return
        self._attr_available = True
        self._attr_is_on = state
        self.async_write_ha_state()


class LivisiBatteryLowSensor(LivisiEntity, BinarySensorEntity):
    """Represents the Battery Low state as a Binary Sensor Entity."""

    def __init__(
        self,
        config_entry: LivisiConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: LivisiDevice,
    ) -> None:
        """Initialize the Livisi window/door sensor."""
        super().__init__(config_entry, coordinator, device, battery=True)
        self._attr_device_class = BinarySensorDeviceClass.BATTERY
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._handle_coordinator_update()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        devices = self.coordinator.data
        device = None
        if devices is not None:
            device = next(
                (dev for dev in devices if dev.id + "_battery" == self.unique_id),
                None,
            )

        if device is not None:
            self._attr_is_on = device.battery_low
            self._attr_available = True
            # hass is not yet set during first initialization
            if self.hass is not None:
                self.async_write_ha_state()


class LivisiMotionSensor(LivisiEntity, BinarySensorEntity):
    """Represents a Livisi Motion Sensor."""

    def __init__(
        self,
        config_entry: LivisiConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: LivisiDevice,
        entity_desc: BinarySensorEntityDescription,
        capability_name: str,
    ) -> None:
        """Initialize the Livisi sensor."""
        super().__init__(config_entry, coordinator, device, capability_name)
        self.entity_description = entity_desc
        self._attr_device_class: BinarySensorDeviceClass = (
            BinarySensorDeviceClass.MOTION
        )

        self._delay_listener: CALLBACK_TYPE | None = None
        self.off_delay_unique_id: str = device.id + "_duration_number"

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_EVENT}_{self.capability_id}",
                self.trigger_event,
            )
        )

        try:
            response = await self.coordinator.aiolivisi.async_get_state(
                self.capability_id, self.entity_description.key
            )
        except Exception:
            self._attr_available = False
            return
        if response is None:
            self._attr_available = False
            return

        self._attr_available = True

        off_delay = self.get_off_delay()
        if off_delay is None:
            self._attr_is_on = False
            return

        lastChange = response.get("lastChanged")
        if lastChange is None:
            self._attr_is_on = False
            return

        try:
            lastactive = datetime.fromisoformat(lastChange)
        except ValueError:
            # ignore invalid lastChange from SHC
            self._attr_is_on = False
            return

        now = datetime.now(timezone.utc)
        delta = now - lastactive

        self._attr_is_on = delta.seconds < off_delay

        @callback
        def off_delay_listener(now: Any) -> None:
            """Switch device off after a delay."""
            self._delay_listener = None
            self._attr_is_on = False
            self.async_write_ha_state()

        remaining_detected_time = off_delay - delta.seconds
        self._delay_listener = evt.async_call_later(
            self.hass, remaining_detected_time, off_delay_listener
        )

    @callback
    def trigger_event(self, event_data: Any) -> None:
        """Update the state of the device."""
        off_delay = self.get_off_delay()
        if off_delay is None:
            off_delay = 20.0

        self._attr_available = True
        self._attr_is_on = True
        self.async_write_ha_state()

        # From this example:
        # https://github.com/home-assistant/core/blob/dev/homeassistant/components/rfxtrx/binary_sensor.py#L21
        if self._delay_listener:
            self._delay_listener()
            self._delay_listener = None

        if self.is_on:

            @callback
            def off_delay_listener(now: Any) -> None:
                """Switch device off after a delay."""
                self._delay_listener = None
                self._attr_is_on = False
                self.async_write_ha_state()

            self._delay_listener = evt.async_call_later(
                self.hass, off_delay, off_delay_listener
            )

    def get_off_delay(self) -> float:
        """Get the Delay."""
        id = self.off_delay_unique_id

        entity_registry = er.async_get(self.hass)
        entity_id = entity_registry.entities.get_entity_id(
            (Platform.NUMBER, DOMAIN, id)
        )
        if entity_id is None:
            return None

        state = self.hass.states.get(entity_id)

        if state is None or state.state is None:
            return None
        return float(state.state)
