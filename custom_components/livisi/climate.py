"""Code to handle a Livisi Virtual Climate Control."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .livisi_device import LivisiDevice

from .const import (
    DOMAIN,
    HUMIDITY,
    LIVISI_STATE_CHANGE,
    LOGGER,
    MAX_TEMPERATURE,
    MIN_TEMPERATURE,
    OPERATION_MODE,
    POINT_TEMPERATURE,
    SETPOINT_TEMPERATURE,
    TEMPERATURE,
    VRCC_DEVICE_TYPES,
)

from .coordinator import LivisiDataUpdateCoordinator
from .entity import LivisiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate device."""
    coordinator: LivisiDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    known_devices = set()

    @callback
    def handle_coordinator_update() -> None:
        """Add climate device."""
        shc_devices: list[LivisiDevice] | None = coordinator.data
        if shc_devices is None:
            return
        entities: list[ClimateEntity] = []
        for device in shc_devices:
            if device.type in VRCC_DEVICE_TYPES and device.id not in known_devices:
                known_devices.add(device.id)
                livisi_climate: ClimateEntity = LivisiClimate(
                    config_entry, coordinator, device
                )
                LOGGER.debug("Include device type: %s", device.type)
                coordinator.devices.add(device.id)
                entities.append(livisi_climate)
        async_add_entities(entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(handle_coordinator_update)
    )


class LivisiClimate(LivisiEntity, ClimateEntity):
    """Represents the Livisi Climate."""

    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT]
    _attr_hvac_mode = HVACMode.HEAT
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: LivisiDataUpdateCoordinator,
        device: LivisiDevice,
    ) -> None:
        """Initialize the Livisi Climate."""
        super().__init__(
            config_entry, coordinator, device, use_room_as_device_name=True
        )

        self._target_temperature_capability = self.capabilities["RoomSetpoint"]
        self._temperature_capability = self.capabilities["RoomTemperature"]
        self._humidity_capability = self.capabilities["RoomHumidity"]

        config = device.capability_config.get("RoomSetpoint", {})
        self._attr_max_temp = config.get("maxTemperature", MAX_TEMPERATURE)
        self._attr_min_temp = config.get("minTemperature", MIN_TEMPERATURE)

        capabilities = config.get("underlyingCapabilityIds")
        if capabilities is None:
            capabilities = ""
        self._thermostat_actuator_ids = [id.strip() for id in capabilities.split(",")]

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature. Overrides hass method."""
        await self.async_set_livisi_temperature(kwargs.get(ATTR_TEMPERATURE))

    async def async_set_livisi_temperature(self, target_temp) -> bool:
        """Set new target temperature."""
        success = await self.aio_livisi.async_set_state(
            self._target_temperature_capability,
            key=(
                SETPOINT_TEMPERATURE
                if self.coordinator.aiolivisi.controller.is_v2
                else POINT_TEMPERATURE
            ),
            value=target_temp,
        )
        if not success:
            self._attr_available = False
            raise HomeAssistantError(f"Failed to set temperature on {self._attr_name}")
        self._attr_available = True
        return success

    async def async_set_mode(self, auto: bool) -> bool:
        """Set new manual/auto mode."""

        # ignore if no thermostats are connected
        if len(self._thermostat_actuator_ids) == 0:
            return False

        # setting one of the thermostats is enough, livisi will sync the state
        thermostat_capability_id = self._thermostat_actuator_ids[0]

        success = await self.aio_livisi.async_set_state(
            thermostat_capability_id,
            key="operationMode",
            value=("Auto" if auto else "Manu"),
        )
        if not success:
            self._attr_available = False
            raise HomeAssistantError(f"Failed to set mode on {self._attr_name}")
        self._attr_available = True

        return success

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        await super().async_added_to_hass()

        target_temp_property = (
            SETPOINT_TEMPERATURE
            if self.coordinator.aiolivisi.controller.is_v2
            else POINT_TEMPERATURE
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self._target_temperature_capability}_{target_temp_property}",
                self.update_target_temperature,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self._temperature_capability}_{TEMPERATURE}",
                self.update_temperature,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{LIVISI_STATE_CHANGE}_{self._humidity_capability}_{HUMIDITY}",
                self.update_humidity,
            )
        )
        for thermostat_capability in self._thermostat_actuator_ids:
            self.async_on_remove(
                async_dispatcher_connect(
                    self.hass,
                    f"{LIVISI_STATE_CHANGE}_{thermostat_capability}_{OPERATION_MODE}",
                    self.update_mode,
                )
            )
        await self.async_update_value()

    async def async_update_value(self):
        """Refresh the device state from the controller."""
        target_temp_property = (
            SETPOINT_TEMPERATURE
            if self.coordinator.aiolivisi.controller.is_v2
            else POINT_TEMPERATURE
        )
        try:
            target_temperature = await self.coordinator.aiolivisi.async_get_value(
                self._target_temperature_capability,
                target_temp_property,
            )
            temperature = await self.coordinator.aiolivisi.async_get_value(
                self._temperature_capability, TEMPERATURE
            )
            humidity = await self.coordinator.aiolivisi.async_get_value(
                self._humidity_capability, HUMIDITY
            )
        except Exception:
            self._attr_available = False
            return
        if temperature is None:
            self._attr_current_temperature = None
            self._attr_available = False
        else:
            self._attr_target_temperature = target_temperature
            self._attr_current_temperature = temperature
            self._attr_current_humidity = humidity
            self._attr_available = True

        if len(self._thermostat_actuator_ids) > 0:
            try:
                mode = await self.coordinator.aiolivisi.async_get_value(
                    self._thermostat_actuator_ids[0], OPERATION_MODE
                )
                self.update_mode(mode)
            except Exception:
                self._attr_available = False

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Find a matching thermostat and use it to set the hvac mode."""
        if hvac_mode == HVACMode.OFF:
            if await self.async_set_livisi_temperature(self._attr_min_temp):
                self._attr_hvac_mode = HVACMode.OFF
        elif hvac_mode == HVACMode.AUTO:
            if await self.async_set_mode(auto=True):
                self._attr_hvac_mode = HVACMode.AUTO
        elif hvac_mode == HVACMode.HEAT:
            if await self.async_set_mode(auto=False):
                self._attr_hvac_mode = HVACMode.HEAT
        self.async_write_ha_state()

    @property
    def hvac_action(self) -> HVACAction | None:
        """Calculate current hvac state based on target and current temperature."""
        if (
            self._attr_current_temperature is None
            or self._attr_target_temperature is None
            or self._attr_hvac_mode == HVACMode.OFF
        ):
            return HVACAction.OFF
        if self._attr_target_temperature > self._attr_current_temperature:
            return HVACAction.HEATING
        if self._attr_target_temperature == self._attr_min_temp:
            return HVACAction.OFF
        return HVACAction.IDLE

    @callback
    def update_target_temperature(self, target_temperature: float) -> None:
        """Update the target temperature of the climate device."""
        self._attr_target_temperature = target_temperature
        self._attr_available = True
        self.async_write_ha_state()

    @callback
    def update_temperature(self, current_temperature: float) -> None:
        """Update the current temperature of the climate device."""
        self._attr_current_temperature = current_temperature
        self._attr_available = True
        self.async_write_ha_state()

    @callback
    def update_humidity(self, humidity: int) -> None:
        """Update the humidity of the climate device."""
        self._attr_current_humidity = humidity
        self._attr_available = True
        self.async_write_ha_state()

    @callback
    def update_mode(self, val: any) -> None:
        """Update the current mode if devices switch from manual to automatic or vice versa."""
        if val == "Auto":
            self._attr_hvac_mode = HVACMode.AUTO
        else:
            self._attr_hvac_mode = HVACMode.HEAT
        if self.hass is not None:
            self.async_write_ha_state()
