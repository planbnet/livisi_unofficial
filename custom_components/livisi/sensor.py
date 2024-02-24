"""Code to handle a Livisi Sensor."""

from __future__ import annotations
from decimal import Decimal


from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.components.sensor.const import SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    LIGHT_LUX,
    UnitOfTemperature,
    UnitOfPower,
    UnitOfEnergy,
    EntityCategory,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .livisi_device import LivisiDevice

from .const import (
    CAPABILITY_HUMIDITY_SENSOR,
    CAPABILITY_LUMINANCE_SENSOR,
    CAPABILITY_ROOM_HUMIDITY,
    CAPABILITY_ROOM_TEMPERATURE,
    CAPABILITY_TEMPERATURE_SENSOR,
    CAPABILITY_POWER_SENSOR,
    CAPABILITY_METER_2WAY_ENERGY_OUT,
    CAPABILITY_METER_2WAY_ENERGY_IN,
    CAPABILITY_METER_2WAY_POWER,
    CAPABILITY_METER_GENERATION_POWER,
    CAPABILITY_METER_GENERATION_ENERGY,
    DOMAIN,
    HUMIDITY,
    LIVISI_STATE_CHANGE,
    LOGGER,
    LUMINANCE,
    METER_ENERGY_PER_DAY,
    METER_ENERGY_PER_MONTH,
    METER_ENERGY_TOTAL,
    METER_POWER,
    TEMPERATURE,
    VRCC_DEVICE_TYPES,
    POWER_CONSUMPTION,
)
from .coordinator import LivisiDataUpdateCoordinator
from .entity import LivisiEntity

CONTROLLER_SENSORS = {
    "cpuUsage": SensorEntityDescription(
        key="cpuUsage",
        translation_key="cpu_usage",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "CPULoad": SensorEntityDescription(
        key="CPULoad",
        translation_key="cpu_usage",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "diskUsage": SensorEntityDescription(
        key="diskUsage",
        translation_key="disk_usage",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "memoryUsage": SensorEntityDescription(
        key="memoryUsage",
        translation_key="ram_usage",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
    "memoryLoad": SensorEntityDescription(
        key="memoryLoad",
        translation_key="ram_usage",
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
    ),
}

CAPABILITY_SENSORS = {
    CAPABILITY_LUMINANCE_SENSOR: [
        SensorEntityDescription(
            key=LUMINANCE,
            device_class=SensorDeviceClass.ILLUMINANCE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=LIGHT_LUX,
        )
    ],
    CAPABILITY_TEMPERATURE_SENSOR: [
        SensorEntityDescription(
            key=TEMPERATURE,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        )
    ],
    CAPABILITY_ROOM_TEMPERATURE: [
        SensorEntityDescription(
            key=TEMPERATURE,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        )
    ],
    CAPABILITY_HUMIDITY_SENSOR: [
        SensorEntityDescription(
            key=HUMIDITY,
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
        )
    ],
    CAPABILITY_ROOM_HUMIDITY: [
        SensorEntityDescription(
            key=HUMIDITY,
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
        )
    ],
    CAPABILITY_POWER_SENSOR: [
        SensorEntityDescription(
            key=POWER_CONSUMPTION,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.WATT,
        )
    ],
    CAPABILITY_METER_2WAY_POWER: [
        SensorEntityDescription(
            key=METER_POWER,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.WATT,
        )
    ],
    CAPABILITY_METER_GENERATION_POWER: [
        SensorEntityDescription(
            key=METER_POWER,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.WATT,
        )
    ],
    CAPABILITY_METER_GENERATION_ENERGY: [
        SensorEntityDescription(
            key=METER_ENERGY_PER_DAY,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ),
        SensorEntityDescription(
            key=METER_ENERGY_PER_MONTH,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ),
        SensorEntityDescription(
            key=METER_ENERGY_TOTAL,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ),
    ],
    CAPABILITY_METER_2WAY_ENERGY_IN: [
        SensorEntityDescription(
            key=METER_ENERGY_PER_DAY,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ),
        SensorEntityDescription(
            key=METER_ENERGY_PER_MONTH,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ),
        SensorEntityDescription(
            key=METER_ENERGY_TOTAL,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ),
    ],
    CAPABILITY_METER_2WAY_ENERGY_OUT: [
        SensorEntityDescription(
            key=METER_ENERGY_PER_DAY,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ),
        SensorEntityDescription(
            key=METER_ENERGY_PER_MONTH,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ),
        SensorEntityDescription(
            key=METER_ENERGY_TOTAL,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ),
    ],
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
                if device.is_shc:
                    for sensor_name in CONTROLLER_SENSORS:
                        if sensor_name in device.state:
                            sensor: SensorEntity = LivisiControllerSensor(
                                config_entry,
                                coordinator,
                                device,
                                CONTROLLER_SENSORS.get(sensor_name),
                            )
                            coordinator.devices.add(device.id)
                            LOGGER.debug("Include SHC sensor %s", sensor_name)
                            entities.append(sensor)
                else:
                    for capability_name in CAPABILITY_SENSORS:
                        if capability_name in device.capabilities:
                            properties = CAPABILITY_SENSORS.get(capability_name)
                            LOGGER.debug(
                                "Include device type: %s as %s",
                                device.type,
                                capability_name,
                            )
                            for prop in properties:
                                sensor: SensorEntity = LivisiSensor(
                                    config_entry,
                                    coordinator,
                                    device,
                                    prop,
                                    capability_name=capability_name,
                                )
                                entities.append(sensor)
                            coordinator.devices.add(device.id)
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
            use_room_as_device_name=(device.type in VRCC_DEVICE_TYPES),
        )
        self.entity_description = entity_desc
        if entity_desc.translation_key is None:
            self._attr_translation_key = entity_desc.key

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

        response = await self.coordinator.aiolivisi.async_get_value(
            self.capability_id, self.entity_description.key
        )
        if response is None:
            self.update_reachability(False)
        else:
            self._attr_native_value = self.convert_to_hass(response)
            self.update_reachability(True)

    def convert_to_hass(self, number: Decimal):
        """Convert livisi value to hass value."""
        if number is None:
            return None
        if self.entity_description.native_unit_of_measurement == LIGHT_LUX:
            # brightness sensors report % values in livisi but hass does not support this
            # so we just assume a max brighness (100%) of 400lx and scale accordingly
            # unfortunately, this value does not scale lineary. So i measured a few
            # data points and approximate with 3 linear functions.
            # for more info on the sensor see (though this isn't too helpful for
            # converting the percentage values livisi provides):
            # https://github.com/Peter-matic/HM-Sec-MDIR_WMD/blob/main/README.md

            if number < 4:  # seems to be capped, 3 is the lowest i have seen
                return 0
            elif number <= 10:  # measured 1 lx at 10%
                return int(number / 10)
            elif number <= 50:
                return int(1.4 * number) - 10  # measured 60 lux at 50%
            else:
                return int(number * 6.8 - 280)  # scale the rest up to 100% = 400lx
        return number

    @callback
    def update_states(self, state: Decimal) -> None:
        """Update the state of the device."""
        self._attr_native_value = self.convert_to_hass(state)
        self.async_write_ha_state()


class LivisiControllerSensor(LivisiEntity, SensorEntity):
    """Represents a Livisi SHC Sensor."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: LivisiDevice,
        entity_desc: SensorEntityDescription,
    ) -> None:
        """Initialize the Livisi sensor."""
        super().__init__(
            config_entry,
            coordinator,
            device,
        )
        self._attr_translation_key = entity_desc.translation_key
        self._attr_unique_id = device.id + "_" + entity_desc.key
        self.entity_description = entity_desc

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)}
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        shc_devices: list[LivisiDevice] = self.coordinator.data
        for device in shc_devices:
            if device.is_shc:
                return device.state.get(self.entity_description.key, {}).get(
                    "value", None
                )
