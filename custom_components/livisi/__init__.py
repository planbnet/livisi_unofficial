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
from homeassistant.helpers import entity_registry as er

from .aiolivisi import AioLivisi
from .const import DOMAIN, LOGGER, CAPABILITY_MAP, SWITCH_DEVICE_TYPES
from .coordinator import LivisiDataUpdateCoordinator


PLATFORMS: Final = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.EVENT,
    Platform.SIREN,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.LIGHT,
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
    LOGGER.info("Migrating Livisi data from version %s", config_entry.version)

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

    # list of capabilities where unique id of entities will be changed
    # from device id to capability id
    migrate_capabilities = [
        "SwitchActuator",
        "BooleanStateActuator",
        "WindowDoorSensor",
        "LuminanceSensor",
        "AlarmActuator",
    ]

    update_ids: dict[str, str] = {}
    light_switches: list[str] = []
    for device in devices:
        deviceid = device["id"]
        if CAPABILITY_MAP not in device:
            break
        caps = device[CAPABILITY_MAP]

        if (
            device["type"] in SWITCH_DEVICE_TYPES
            and device.get("tags", {}).get("typeCategory") == "TCLightId"
            and "SwitchActuator" in caps
        ):
            light_switches.append(caps["SwitchActuator"])

        for cap_name in migrate_capabilities:
            if cap_name in caps:
                update_ids[deviceid] = caps[cap_name]
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
                LOGGER.info("Updating id %s to %s", oldid, newid)
                return {"new_unique_id": newid}
            else:
                return None

        await er.async_migrate_entries(hass, config_entry.entry_id, update_unique_id)
        config_entry.version = 2

    if config_entry.version == 2:
        # delete switches that are lights, because they are now integrated as light devices
        switch_entries = []
        entity_registry = er.async_get(hass)

        @callback
        def find_light_switches(entity_entry):
            """Find light switches that are now integrated as light devices."""
            if entity_entry.unique_id in light_switches:
                switch_entries.append(entity_entry)

        await er.async_migrate_entries(hass, config_entry.entry_id, find_light_switches)
        for switch in switch_entries:
            entity_registry.async_remove(switch.entity_id)
        config_entry.version = 3

    if config_entry.version == 3:
        # update unique ids to just the capability id without the "/capability/" prefix
        @callback
        def simplify_unique_id(entity_entry):
            """Remove id prefix from url."""
            oldid = entity_entry.unique_id
            if "/capability/" in oldid:
                newid = oldid.replace("/capability/", "")
                LOGGER.info("Updating id %s to %s", oldid, newid)
                return {"new_unique_id": newid}
            else:
                LOGGER.info("Skipping %s", oldid)
                return None

        await er.async_migrate_entries(hass, config_entry.entry_id, simplify_unique_id)
        config_entry.version = 4

    LOGGER.info("Migration to version %s successful", config_entry.version)

    return True
