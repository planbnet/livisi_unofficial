"""Provides device triggers for LIVISI Smart Home."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_EVENT,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant

from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
)
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import (
    BUTTON_COUNT,
    CONF_SUBTYPE,
    EVENT_MOTION_DETECTED,
    EVENT_BUTTON_PRESSED,
    EVENT_BUTTON_LONG_PRESSED,
    MOTION_DEVICE_TYPES,
    LIVISI_EVENT,
)

from . import DOMAIN


BUTTON_TRIGGER_TYPES = {EVENT_BUTTON_PRESSED, EVENT_BUTTON_LONG_PRESSED}

MOTION_TRIGGER_TYPES = {
    EVENT_MOTION_DETECTED,
}

BUTTON_TRIGGER_SUBTYPES = {
    f"button_{idx}" for idx in range(0, max(BUTTON_COUNT.values()))
}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Optional(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(BUTTON_TRIGGER_TYPES | MOTION_TRIGGER_TYPES),
        vol.Optional(CONF_SUBTYPE): vol.In(BUTTON_TRIGGER_SUBTYPES),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """List device triggers for LIVISI Smart Home devices."""

    dev_reg: dr.DeviceRegistry = dr.async_get(hass)
    if (dev := dev_reg.async_get(device_id)) is None:
        raise ValueError(f"Device ID {device_id} is not valid")

    triggers = []

    buttons = BUTTON_COUNT.get(dev.model)
    if buttons is not None:
        triggers += [
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_TYPE: trigger_type,
                CONF_SUBTYPE: trigger_subtype,
            }
            for trigger_type in BUTTON_TRIGGER_TYPES
            for trigger_subtype in {f"button_{idx}" for idx in range(0, buttons)}
        ]

    if dev.model in MOTION_DEVICE_TYPES:
        triggers += [
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_TYPE: trigger_type,
            }
            for trigger_type in MOTION_TRIGGER_TYPES
        ]

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""

    trigger = config[CONF_TYPE]

    dev_reg: dr.DeviceRegistry = dr.async_get(hass)
    if (device := dev_reg.async_get(config[CONF_DEVICE_ID])) is None:
        return

    livisi_id = next(iter(device.identifiers))[1]

    event_data = {
        CONF_DEVICE_ID: livisi_id,
    }

    if trigger in BUTTON_TRIGGER_TYPES:
        event_data[CONF_TYPE] = EVENT_BUTTON_PRESSED
        event_data["button_index"] = int(config[CONF_SUBTYPE].split("_")[1])
        event_data["press_type"] = (
            "LongPress" if trigger.find("long_press") != -1 else "ShortPress"
        )
    elif trigger in MOTION_TRIGGER_TYPES:
        event_data[CONF_TYPE] = EVENT_MOTION_DETECTED
    else:
        return

    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: CONF_EVENT,
            event_trigger.CONF_EVENT_TYPE: LIVISI_EVENT,
            event_trigger.CONF_EVENT_DATA: event_data,
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
