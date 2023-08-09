"""The Livisi Smart Home integration."""
from __future__ import annotations

from typing import Final

from aiohttp import ClientConnectorError

from homeassistant import core
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client, device_registry as dr

from homeassistant.helpers.entity_registry import async_migrate_entries

from .aiolivisi.aiolivisi import AioLivisi
from .aiolivisi.const import CAPABILITY_MAP
from .const import DOMAIN, LOGGER
from .coordinator import LivisiDataUpdateCoordinator


PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.EVENT,
    Platform.SIREN,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: core.HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Livisi Smart Home from a config entry."""
    web_session = aiohttp_client.async_get_clientsession(hass)
    aiolivisi = AioLivisi(web_session)
    coordinator = LivisiDataUpdateCoordinator(hass, entry, aiolivisi)
    try:
        await coordinator.async_setup()
        await coordinator.async_set_all_rooms()
    except ClientConnectorError as exception:
        raise ConfigEntryNotReady from exception

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=coordinator.serial_number,
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer="Livisi",
        name=f"SHC {coordinator.controller_type} {coordinator.serial_number}",
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_config_entry_first_refresh()
    entry.async_create_background_task(
        hass, coordinator.ws_connect(), "livisi-ws_connect"
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    unload_success = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await coordinator.websocket.disconnect()
    if unload_success:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_success


async def async_migrate_entry(hass, config_entry):
    """Migrate old entry."""
    LOGGER.debug("Migrating from version %s", config_entry.version)

    # Load devices with a temporary coordinator
    web_session = aiohttp_client.async_get_clientsession(hass)
    aiolivisi = AioLivisi(web_session)
    coordinator = LivisiDataUpdateCoordinator(hass, config_entry, aiolivisi)
    try:
        await coordinator.async_setup()
        devices = await coordinator.async_get_devices()
    except ClientConnectorError as exception:
        LOGGER.error(exception)
        return False
    finally:
        await web_session.close()

    # list of capabilities where unique id of entities will be changed
    # from device id to capability id
    migrate_capabilities = [
        "SwitchActuator",
        "BooleanStateActuator",
        "WindowDoorSensor",
        "SmokeDetectorSensor",
        "LuminanceSensor",
        "AlarmActuator",
    ]

    update_ids: dict[str, str] = {}
    for device in devices:
        deviceid = device["id"]
        if CAPABILITY_MAP not in device:
            break
        caps = device[CAPABILITY_MAP]
        for cap_name in migrate_capabilities:
            if cap_name in caps:
                update_ids[deviceid] = caps[cap_name].replace("/capability/", "")
                break

    if config_entry.version == 1:
        # starting with version 2, most entities are uniquely identified by capability id
        # not device id, so one device can have multiple entities

        @callback
        def update_unique_id(entity_entry):
            """Update unique ID of entity entry."""
            oldid = entity_entry.unique_id
            newid = update_ids.get(oldid)
            if newid is not None:
                return {"new_unique_id": newid}
            else:
                return {}

        await async_migrate_entries(hass, config_entry.entry_id, update_unique_id)
        config_entry.version = 2

    LOGGER.info("Migration to version %s successful", config_entry.version)

    return True
