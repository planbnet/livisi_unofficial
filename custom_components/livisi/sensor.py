"""Code to handle a Livisi Sensor."""

from __future__ import annotations
from decimal import Decimal
import math

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
            key=CAPABILITY_LUMINANCE_SENSOR + "_" + LUMINANCE,
            translation_key=LUMINANCE,
            device_class=SensorDeviceClass.ILLUMINANCE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=LIGHT_LUX,
        ),
    ],
    CAPABILITY_TEMPERATURE_SENSOR: [
        SensorEntityDescription(
            key=CAPABILITY_TEMPERATURE_SENSOR + "_" + TEMPERATURE,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        )
    ],
    CAPABILITY_ROOM_TEMPERATURE: [
        SensorEntityDescription(
            key=CAPABILITY_ROOM_TEMPERATURE + "_" + TEMPERATURE,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        )
    ],
    CAPABILITY_HUMIDITY_SENSOR: [
        SensorEntityDescription(
            key=CAPABILITY_HUMIDITY_SENSOR + "_" + HUMIDITY,
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
        )
    ],
    CAPABILITY_ROOM_HUMIDITY: [
        SensorEntityDescription(
            key=CAPABILITY_ROOM_HUMIDITY + "_" + HUMIDITY,
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
        )
    ],
    CAPABILITY_POWER_SENSOR: [
        SensorEntityDescription(
            key=CAPABILITY_POWER_SENSOR + "_" + POWER_CONSUMPTION,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.WATT,
        )
    ],
    CAPABILITY_METER_2WAY_POWER: [
        SensorEntityDescription(
            key=CAPABILITY_METER_2WAY_POWER + "_" + METER_POWER,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.WATT,
        )
    ],
    CAPABILITY_METER_GENERATION_POWER: [
        SensorEntityDescription(
            key=CAPABILITY_METER_GENERATION_POWER + "_" + METER_POWER,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.WATT,
        )
    ],
    CAPABILITY_METER_GENERATION_ENERGY: [
        SensorEntityDescription(
            key=CAPABILITY_METER_GENERATION_ENERGY + "_" + METER_ENERGY_PER_DAY,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ),
        SensorEntityDescription(
            key=CAPABILITY_METER_GENERATION_ENERGY + "_" + METER_ENERGY_PER_MONTH,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ),
        SensorEntityDescription(
            key=CAPABILITY_METER_GENERATION_ENERGY + "_" + METER_ENERGY_TOTAL,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ),
    ],
    CAPABILITY_METER_2WAY_ENERGY_IN: [
        SensorEntityDescription(
            key=CAPABILITY_METER_2WAY_ENERGY_IN + "_" + METER_ENERGY_PER_DAY,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ),
        SensorEntityDescription(
            key=CAPABILITY_METER_2WAY_ENERGY_IN + "_" + METER_ENERGY_PER_MONTH,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ),
        SensorEntityDescription(
            key=CAPABILITY_METER_2WAY_ENERGY_IN + "_" + METER_ENERGY_TOTAL,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ),
    ],
    CAPABILITY_METER_2WAY_ENERGY_OUT: [
        SensorEntityDescription(
            key=CAPABILITY_METER_2WAY_ENERGY_OUT + "_" + METER_ENERGY_PER_DAY,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ),
        SensorEntityDescription(
            key=CAPABILITY_METER_2WAY_ENERGY_OUT + "_" + METER_ENERGY_PER_MONTH,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        ),
        SensorEntityDescription(
            key=CAPABILITY_METER_2WAY_ENERGY_OUT + "_" + METER_ENERGY_TOTAL,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
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
        shc_devices: list[LivisiDevice] | None = coordinator.data
        if shc_devices is None:
            return
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
                            unique = len(properties) == 1
                            for prop in properties:
                                LOGGER.debug(
                                    "Generate property %s as %s",
                                    prop.key,
                                    prop.state_class,
                                )
                                sensor: SensorEntity = LivisiSensor(
                                    config_entry,
                                    coordinator,
                                    device,
                                    prop,
                                    capability_name=capability_name,
                                    suffix=("" if unique else "_" + prop.key),
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
        *,
        suffix="",
    ) -> None:
        """Initialize the Livisi sensor."""
        super().__init__(
            config_entry,
            coordinator,
            device,
            capability_name,
            use_room_as_device_name=(device.type in VRCC_DEVICE_TYPES),
            suffix=suffix,
        )
        self.entity_description = entity_desc
        if entity_desc.translation_key is None:
            self._attr_translation_key = entity_desc.key.lower()

        self.property_name = entity_desc.key.removeprefix(capability_name + "_")

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self.capability_id}_{self.property_name}",
                self.update_states,
            )
        )

        await self.async_update_value()

    async def async_update_value(self):
        response = await self.coordinator.aiolivisi.async_get_value(
            self.capability_id, self.property_name
        )
        if response is None:
            self._attr_available = False
            self.async_write_ha_state()
        else:
            self._attr_native_value = self.convert_to_hass(response)
            self._attr_available = True
            self.async_write_ha_state()

    def convert_to_hass(self, number: Decimal):
        """Convert livisi value to hass value."""
        if number is None:
            return None
        if self.entity_description.native_unit_of_measurement == LIGHT_LUX:
            # brightness sensors report % values in livisi but hass does not support this.
            # Unfortunately, the percentage does not scale lineary but exponentially.
            # So I measured with another sensor for a day and came up with a few data
            # points (rounded)
            # Between 0 and 50 percent, the sensor seems to be very sensitive, so
            # this is best approximated with 3 linear functions.
            # Above that, the exact values don't matter that much and I searched for
            # an exponental fit.
            if number < 4:  # seems to be capped, 3 is the lowest i have seen
                return 0
            elif number <= 10:  # measured 1 lx at 10%
                return int(number / 10)
            elif number <= 50:  # measured 60 lux at 50%
                return int(1.4 * number) - 10
            else:  # exp function derived from the rest of the measurements
                a = 0.1576567663834781
                b = 0.11891850473620913
                return int(a * math.exp(b * number))

        return number

    @callback
    def update_states(self, state: Decimal) -> None:
        """Update the state of the device."""
        self._attr_available = True
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
        shc_devices: list[LivisiDevice] | None = self.coordinator.data
        if shc_devices is None:
            return None
        for device in shc_devices:
            if device.is_shc:
                return device.state.get(self.entity_description.key, {}).get(
                    "value", None
                )
