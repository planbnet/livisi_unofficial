"""Code to handle a Livisi Sensor."""
from __future__ import annotations
from decimal import Decimal


from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTemperature, UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .livisi_device import LivisiDevice

from .const import (
    CAPABILITY_HUMIDITY_SENSOR,
    CAPABILITY_LUMINANCE_SENSOR,
    CAPABILITY_ROOM_HUMIDITY,
    CAPABILITY_ROOM_TEMPERATURE,
    CAPABILITY_TEMPERATURE_SENSOR,
    CAPABILITY_POWER_SENSOR,
    DOMAIN,
    HUMIDITY,
    LIVISI_STATE_CHANGE,
    LOGGER,
    LUMINANCE,
    TEMPERATURE,
    VRCC_DEVICE_TYPE,
    POWER_CONSUMPTION,
)
from .coordinator import LivisiDataUpdateCoordinator
from .entity import LivisiEntity

SENSOR_TYPES = {
    CAPABILITY_LUMINANCE_SENSOR: SensorEntityDescription(
        key=LUMINANCE,
        device_class=SensorDeviceClass.ILLUMINANCE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    CAPABILITY_TEMPERATURE_SENSOR: SensorEntityDescription(
        key=TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CAPABILITY_ROOM_TEMPERATURE: SensorEntityDescription(
        key=TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    CAPABILITY_HUMIDITY_SENSOR: SensorEntityDescription(
        key=HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    CAPABILITY_ROOM_HUMIDITY: SensorEntityDescription(
        key=HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    CAPABILITY_POWER_SENSOR: SensorEntityDescription(
        key=POWER_CONSUMPTION,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary_sensor device."""
    coordinator: LivisiDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    known_devices = set()

    @callback
    def handle_coordinator_update() -> None:
        """Add Sensors."""
        shc_devices: list[LivisiDevice] = coordinator.data
        entities: list[SensorEntity] = []
        for device in shc_devices:
            if device.id not in known_devices:
                known_devices.add(device.id)
                for capability_name in SENSOR_TYPES:
                    if capability_name in device.capabilities:
                        sensor: SensorEntity = LivisiSensor(
                            config_entry,
                            coordinator,
                            device,
                            SENSOR_TYPES.get(capability_name),
                            capability_name=capability_name,
                        )
                        LOGGER.debug(
                            "Include device type: %s as %s",
                            device.type,
                            capability_name,
                        )
                        coordinator.devices.add(device.id)
                        entities.append(sensor)
        async_add_entities(entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(handle_coordinator_update)
    )


class LivisiSensor(LivisiEntity, SensorEntity):
    """Represents a Livisi Sensor."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: LivisiDevice,
        entity_desc: SensorEntityDescription,
        capability_name: str,
    ) -> None:
        """Initialize the Livisi sensor."""
        super().__init__(
            config_entry,
            coordinator,
            device,
            capability_name,
            use_room_as_device_name=(device.type == VRCC_DEVICE_TYPE),
        )
        self.entity_description = entity_desc
        self._attr_translation_key = entity_desc.key

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self.capability_id}",
                self.update_states,
            )
        )

        response = await self.coordinator.aiolivisi.async_get_device_state(
            self.capability_id, self.entity_description.key
        )
        if response is None:
            self.update_reachability(False)
        else:
            self._attr_native_value = response
            self.update_reachability(True)

    @callback
    def update_states(self, state: Decimal) -> None:
        """Update the state of the device."""
        self._attr_native_value = state
        self.async_write_ha_state()
